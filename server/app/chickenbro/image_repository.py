"""Private Chat images; all serving and attachment operations are owner scoped."""
import hashlib
from datetime import timedelta
from uuid import uuid4
from server.app.chickenbro.images import ImageError, NormalizedImage


def unavailable():
    return ImageError('CHAT_IMAGE_UNAVAILABLE', '图片已失效或不可访问，请重新选择图片。')


class ChatImageRepository:
    def save_image(self, user_id, key, image, now):
        digest = hashlib.sha256(image.data).hexdigest()
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                # Per-owner serialization bounds concurrent uploads and makes retry atomic.
                cursor.execute('SELECT id FROM identity.users WHERE id=%s FOR UPDATE', (user_id,))
                if cursor.fetchone() is None:
                    raise unavailable()
                cursor.execute('SELECT id, sha256, mime_type, width, height, data IS NOT NULL, expires_at FROM chat.images WHERE user_id=%s AND upload_key=%s', (user_id, key))
                existing = cursor.fetchone()
                if existing:
                    if existing[1] != digest:
                        raise ImageError('IDEMPOTENCY_CONFLICT', '图片上传请求已用于另一张图片。')
                    if not existing[5] or (existing[6] is not None and existing[6] <= now):
                        raise unavailable()
                    return dict(id=str(existing[0]), mimeType=existing[2], width=existing[3], height=existing[4])
                cursor.execute('SELECT coalesce(sum(octet_length(data)),0), count(*) FILTER (WHERE data IS NOT NULL) FROM chat.images WHERE user_id=%s', (user_id,))
                size, count = cursor.fetchone()
                if size + len(image.data) > 100 * 1024 * 1024 or count >= 1000:
                    raise ImageError('CHAT_IMAGE_QUOTA', '图片空间已满，请删除不再需要的会话并等待清理。')
                identity = uuid4()
                cursor.execute('INSERT INTO chat.images (id,user_id,upload_key,sha256,mime_type,width,height,data,created_at,expires_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (identity,user_id,key,digest,image.mime_type,image.width,image.height,image.data,now,now+timedelta(hours=24)))
                return dict(id=str(identity), mimeType=image.mime_type, width=image.width, height=image.height)

    def read_image(self, user_id, image_id, now):
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute('''SELECT i.data,i.mime_type,i.width,i.height FROM chat.images i
                    WHERE i.id=%s AND i.user_id=%s AND i.data IS NOT NULL
                    AND (i.expires_at IS NULL OR i.expires_at>%s)
                    AND (i.message_id IS NULL OR EXISTS (
                        SELECT 1 FROM chat.messages m JOIN chat.conversations c ON c.id=m.conversation_id AND c.user_id=m.user_id
                        WHERE m.id=i.message_id AND m.user_id=i.user_id AND c.status='active'))''', (image_id,user_id,now))
                row=cursor.fetchone()
                return NormalizedImage(bytes(row[0]), row[1], row[2], row[3]) if row else None

    def image_metadata(self, user_id, image_ids):
        if not image_ids:
            return []
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT id,mime_type,width,height FROM chat.images WHERE user_id=%s AND id=ANY(%s::uuid[])', (user_id,list(image_ids)))
                by_id={str(row[0]): dict(id=str(row[0]),mimeType=row[1],width=row[2],height=row[3]) for row in cursor.fetchall()}
                return [by_id[str(identity)] for identity in image_ids if str(identity) in by_id]

    def remove_image(self, user_id, image_id, now):
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT message_id FROM chat.images WHERE user_id=%s AND id=%s FOR UPDATE', (user_id,image_id))
                row=cursor.fetchone()
                if row is None or row[0] is not None:
                    raise unavailable()
                cursor.execute('UPDATE chat.images SET data=NULL, expires_at=%s WHERE user_id=%s AND id=%s', (now,user_id,image_id))

    @staticmethod
    def bind_images(cursor, user_id, image_ids, message_id, now):
        if len(image_ids)>3 or len(set(map(str,image_ids))) != len(image_ids):
            raise ImageError()
        # Stable lock ordering prevents reverse-image-order deadlocks.
        cursor.execute('SELECT id FROM chat.images WHERE user_id=%s AND id=ANY(%s::uuid[]) ORDER BY id FOR UPDATE', (user_id,list(image_ids)))
        if len(cursor.fetchall()) != len(image_ids):
            raise unavailable()
        for identity in image_ids:
            cursor.execute('UPDATE chat.images SET message_id=%s, expires_at=NULL WHERE id=%s AND user_id=%s AND message_id IS NULL AND data IS NOT NULL AND expires_at>%s', (message_id,identity,user_id,now))
            if cursor.rowcount != 1:
                raise unavailable()

    def purge_expired_images(self, now):
        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute('UPDATE chat.images SET data=NULL WHERE data IS NOT NULL AND expires_at<=%s', (now,))
                return cursor.rowcount
