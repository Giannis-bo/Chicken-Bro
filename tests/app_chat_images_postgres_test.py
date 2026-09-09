import os
import unittest
from datetime import timedelta
from uuid import uuid4
from server.app.chickenbro.images import NormalizedImage, ImageError
from tests import app_chat_account_limit_postgres_test as fixture


@unittest.skipUnless(os.environ.get('WOW_PG_TEST_DSN_V2'), 'isolated PostgreSQL DSN is not configured')
class ChatImagesPostgresTest(unittest.TestCase):
    setUp = fixture.ChatAccountLimitPostgresTest.setUp
    application = fixture.ChatAccountLimitPostgresTest.application

    def upload(self, key='image-upload-1'):
        return self.repository.save_image(self.owner.user_id, key,
            NormalizedImage(b'pixels', 'image/png', 2, 3), self.now)

    def test_owner_read_idempotency_and_remove(self):
        image = self.upload()
        self.assertEqual(image, self.upload())
        self.assertIsNone(self.repository.read_image(self.other.user_id, image['id'], self.now))
        self.assertEqual(self.repository.read_image(self.web.user_id, image['id'], self.now).data, b'pixels')
        with self.assertRaises(ImageError):
            self.repository.save_image(self.owner.user_id, 'image-upload-1', NormalizedImage(b'other', 'image/png', 2, 3), self.now)
        self.repository.remove_image(self.owner.user_id, image['id'], self.now)
        self.assertIsNone(self.repository.read_image(self.owner.user_id, image['id'], self.now))

    def test_atomic_binding_busy_rejection_and_archived_access(self):
        image = self.upload()
        first, run = self.repository.start_message_run(self.owner.user_id, self.a, '',
            'image-message-1', 'image-message-1', self.now, runtime_revision='test', image_ids=(image['id'],))
        self.assertEqual([str(x) for x in self.repository.list_messages(self.owner.user_id, self.a)[0].image_ids], [str(image['id'])])
        other_image = self.upload('image-upload-2')
        with self.assertRaises(Exception):
            self.repository.start_message_run(self.owner.user_id, self.b, '', 'image-message-2',
                'image-message-2', self.now, runtime_revision='test', image_ids=(other_image['id'],))
        self.repository.remove_image(self.owner.user_id, other_image['id'], self.now)
        with self.assertRaises(ImageError):
            self.repository.remove_image(self.owner.user_id, image['id'], self.now)
        from server.app.chickenbro.domain import AgentRunStatus
        self.repository.finish_agent_run(self.owner.user_id, run.id, AgentRunStatus.FAILED, None, 'CODEX_TIMEOUT', self.now)
        self.app.delete_conversation(self.owner, self.a)
        self.assertIsNone(self.repository.read_image(self.owner.user_id, image['id'], self.now))

    def test_second_user_binding_and_expiry_are_rejected(self):
        image = self.upload()
        conversation = self.app.create_conversation(self.other, idempotency_key='other-conversation').id
        with self.assertRaises(ImageError):
            self.repository.start_message_run(self.other.user_id, conversation, '', 'other-message-1',
                'other-message-1', self.now, runtime_revision='test', image_ids=(image['id'],))
        self.assertEqual(self.repository.list_messages(self.other.user_id, conversation), [])
        future = self.now + timedelta(days=2)
        self.assertIsNone(self.repository.read_image(self.owner.user_id, image['id'], future))
        self.assertGreaterEqual(self.repository.purge_expired_images(future), 1)

    def test_application_replay_matches_ordered_images_and_vision_history(self):
        from server.app.chickenbro.application import ChatApplication, ChatApplicationError
        class Vision:
            runtime_revision='vision-test'
            def __init__(self): self.calls=[]
            def stream(self, **kwargs):
                self.calls.append(kwargs)
                yield {'type':'completed', 'text':'图片已读取'}
        vision=Vision()
        app=ChatApplication(repository=self.repository, codex=vision, images_enabled=True, clock=lambda:self.now)
        image=self.upload()
        args=dict(client_message_id='vision-message-1',idempotency_key='vision-message-1',image_ids=(image['id'],))
        self.assertEqual(list(app.stream_message(self.owner,self.a,'',**args))[-1].event_type,'completed')
        self.assertEqual(vision.calls[0]['images'], ['data:image/png;base64,cGl4ZWxz'])
        self.assertEqual(list(app.stream_message(self.web,self.a,'',**args))[-1].event_type,'completed')
        self.assertEqual(len(vision.calls),1)
        with self.assertRaises(ChatApplicationError):
            list(app.stream_message(self.owner,self.a,'different',**args))
        other_image=self.upload('vision-image-2')
        with self.assertRaises(ChatApplicationError):
            list(app.stream_message(self.owner,self.a,'',**{**args,'image_ids':(other_image['id'],)}))
        list(app.stream_message(self.web,self.a,'继续解释',client_message_id='vision-message-2',idempotency_key='vision-message-2'))
        self.assertEqual(vision.calls[-1]['images'],vision.calls[0]['images'])
        self.assertEqual(next(row for row in app.load_conversation(self.web,self.a)['messages'] if row.get('images'))['images'],[image])

    def test_image_delivery_survives_disconnect_and_replays_from_web(self):
        from threading import Event
        from server.app.chickenbro.application import ChatApplication
        release = Event()
        seen = []
        class Vision:
            runtime_revision = 'image-background-test'
            def stream(self, **kwargs):
                seen.append(kwargs.get('images'))
                if not release.wait(3):
                    raise AssertionError('generation was not released')
                yield {'type': 'completed', 'text': '断线后图片回答已保存'}
        app = ChatApplication(repository=self.repository, codex=Vision(), images_enabled=True, clock=lambda: self.now)
        image = self.upload()
        args = dict(client_message_id='image-disconnect-1', idempotency_key='image-disconnect-1', image_ids=(image['id'],))
        delivery = app.start_delivery(self.owner, self.a, '', **args)
        self.assertEqual(next(delivery).event_type, 'started')
        delivery.close()
        release.set()
        self.assertTrue(delivery.finished.wait(3))
        self.assertEqual(seen, [['data:image/png;base64,cGl4ZWxz']])
        history = app.load_conversation(self.web, self.a)['messages']
        self.assertTrue(any(row.get('images') == [image] for row in history))
        self.assertTrue(any(row['content'] == '断线后图片回答已保存' for row in history))
        replay = list(app.start_delivery(self.web, self.a, '', **args))
        self.assertEqual(replay[-1].event_type, 'completed')
        self.assertEqual(len(seen), 1)

    def test_api_authenticated_read_csrf_and_limits(self):
        from unittest.mock import patch
        from fastapi.testclient import TestClient
        from server.app.main import create_app
        from server.app.platform.config import AppSettings
        from server.app.platform.health import ReadinessRegistry
        from server.app.identity.domain import Principal
        owner,other=self.owner.user_id,self.other.user_id
        class Auth:
            def resolve_principal(self, credential, kind):
                return Principal(user_id=owner if credential=='owner' else other, session_kind=kind) if credential in {'owner','other'} else None
        self.app._images_enabled=True
        app=create_app(settings=AppSettings(environment='test',database_url='postgresql://redacted',web_origin='https://www.chickenbro.cloud'),
            readiness_registry=ReadinessRegistry({}),web_auth_application=Auth(),chat_application=self.app,simulation_application=object())
        with TestClient(app,base_url='https://www.chickenbro.cloud') as client:
            route='/api/v2/chat/images'
            self.assertEqual(client.post(route,json={'dataUrl':'x'}).status_code,401)
            headers={'Cookie': '__Host-chickenbro-session=owner; __Host-chickenbro-csrf=csrf', 'Origin': 'https://www.chickenbro.cloud', 'X-CSRF-Token': 'csrf', 'Idempotency-Key':'api-image-upload'}
            with patch('server.app.chickenbro.application.normalize_image',return_value=NormalizedImage(b'pixels','image/png',2,3)):
                response=client.post(route,headers=headers,json={'dataUrl':'test'})
            self.assertEqual(response.status_code,201,response.text)
            image=response.json()
            path=route+'/'+image['id']
            self.assertEqual(client.get(path,headers={'Cookie': '__Host-chickenbro-session=other; __Host-chickenbro-csrf=csrf', 'Origin': 'https://www.chickenbro.cloud', 'X-CSRF-Token': 'csrf'}).status_code,404)
            self.assertEqual(client.get(path).status_code,401)
            client.cookies.set('__Host-chickenbro-session','owner')
            response=client.get(path)
            self.assertEqual(response.json(),{'dataUrl':'data:image/png;base64,cGl4ZWxz'})
            self.assertIn('no-store',response.headers['cache-control'])
            self.assertEqual(client.delete(path,headers={'Origin':'https://www.chickenbro.cloud'}).status_code,403)
            client.cookies.clear()
            self.assertEqual(client.post(route,headers=headers,json={'dataUrl':'x','user_id':str(other)}).status_code,422)
            stream=f'/api/v2/chat/conversations/{self.a}/messages/stream'
            for images in [[image['id']]*4,[image['id']]*2]:
                response=client.post(stream,headers=headers,json={'content':'x','imageIds':images})
                self.assertEqual(response.status_code,422,response.text)
            self.assertEqual(client.post(route,headers=headers,content=b'x'*7_000_000).status_code,413)

    def test_legacy_history_has_nonempty_placeholder_for_image_only_message(self):
        from server.app.api.routes.chat import _detail_payload
        image=self.upload()
        self.repository.start_message_run(self.owner.user_id,self.a,'','legacy-image-1','legacy-image-1',self.now,
            runtime_revision='test',image_ids=(image['id'],))
        view=self.app.load_conversation(self.web,self.a)
        self.assertEqual(_detail_payload(view)['messages'][0]['content'],'[图片]')
        self.assertNotIn('images',_detail_payload(view)['messages'][0])
        self.assertEqual(_detail_payload(view,include_images=True)['messages'][0]['images'],[image])

    def test_quota_and_concurrent_uploads_are_bounded(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        barrier=Barrier(2)
        def upload():
            barrier.wait(timeout=3)
            return self.upload('racing-upload')
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(upload) for _ in range(2)]
            results=[future.result(timeout=5) for future in futures]
        self.assertEqual(results[0],results[1])
        with self.connect() as connection:
            connection.execute('''INSERT INTO chat.images(id,user_id,upload_key,sha256,mime_type,width,height,data,created_at,expires_at)
                SELECT gen_random_uuid(),%s,'quota-row-'||n,'digest','image/png',1,1,'x'::bytea,%s,%s
                FROM generate_series(1,999) n''',(self.owner.user_id,self.now,self.now+timedelta(days=1)))
        with self.assertRaisesRegex(ImageError,'空间已满'):
            self.upload('beyond-quota')
