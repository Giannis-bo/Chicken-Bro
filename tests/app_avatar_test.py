import base64
import struct
import unittest
import zlib
from uuid import uuid4

from server.app.identity.avatar import normalize_avatar
from server.app.identity.application import AuthApplicationError, WebAuthApplication
from server.app.identity.domain import Principal
from server.app.platform.config import AppSettings


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def png(width=1, height=1, extra=b''):
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + extra + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00' * height)) + chunk(b'IEND', b''))


def data_url(data, kind='png'):
    return f'data:image/{kind};base64,' + base64.b64encode(data).decode()


class AvatarTest(unittest.TestCase):
    def test_png_metadata_removed_and_image_preserved(self):
        original = png(extra=chunk(b'tEXt', b'GPS\x00private metadata'))
        self.assertEqual(normalize_avatar(data_url(original)), data_url(png()))

    def test_rejects_non_image_corruption_oversize_and_excessive_dimensions(self):
        for value in ['https://example.com/avatar.png', 'data:image/svg+xml;base64,PHN2Zz4=',
                      data_url(b'not a png'), data_url(png()[:-1]), data_url(png(4096)),
                      data_url(png() + b'trailing'), data_url(b'x' * 262145)]:
            with self.subTest(value=value[:70]), self.assertRaises(ValueError):
                normalize_avatar(value)

    def test_bounded_png_inflation(self):
        bomb = png().split(chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00')))[0]
        bomb += chunk(b'IDAT', zlib.compress(b'\0' * 5000000)) + chunk(b'IEND', b'')
        with self.assertRaises(ValueError):
            normalize_avatar(data_url(bomb))

    def test_jpeg_strips_metadata_and_limits_dimensions(self):
        segment = lambda marker, value: b'\xff' + bytes([marker]) + struct.pack('>H', len(value) + 2) + value
        frame = segment(0xc0, b'\x08\x00\x01\x00\x01\x01\x01\x11\x00')
        scan = segment(0xda, b'\x01\x01\x00\x00\x3f\x00') + b'\x55\xff\x00\x66'
        clean = b'\xff\xd8' + frame + scan + b'\xff\xd9'
        dirty = b'\xff\xd8' + segment(0xe1, b'Exif private GPS') + clean[2:]
        largest = clean[:-2] + b'\x55' * (262144 - len(clean)) + clean[-2:]
        self.assertEqual(normalize_avatar(data_url(largest, 'jpeg')), data_url(largest, 'jpeg'))
        self.assertEqual(normalize_avatar(data_url(dirty, 'jpeg')), data_url(clean, 'jpeg'))
        with self.assertRaises(ValueError):
            normalize_avatar(data_url(clean[:-2], 'jpeg'))

    def test_avatar_shared_by_principal_owner_and_web_cannot_write(self):
        class Repo:
            def __init__(self): self.avatars = {}
            def get_avatar(self, user_id): return self.avatars.get(user_id)
            def set_avatar(self, user_id, avatar, *, now):
                self.avatars[user_id] = avatar
                return True
        repo = Repo()
        app = WebAuthApplication(repository=repo, wechat_gateway=None, settings=AppSettings(environment="test", database_url="postgresql://redacted"))
        user = uuid4()
        mini, web = Principal(user, 'mini_bearer'), Principal(user, 'web_cookie')
        self.assertIsNone(app.avatar(web))
        image = app.set_avatar(mini, data_url(png()))
        self.assertEqual(app.avatar(web), image)
        self.assertIsNone(app.avatar(Principal(uuid4(), 'web_cookie')))
        with self.assertRaises(AuthApplicationError): app.set_avatar(web, data_url(png()))
        with self.assertRaises(AuthApplicationError): app.set_avatar(mini, 'not an image')
        self.assertEqual(app.avatar(web), image)


class AvatarApiTest(unittest.TestCase):
    def setUp(self):
        from tests.app_test_login_test import TestLoginTest
        TestLoginTest.setUp(self)
        self.avatars = {}
        self.repository.get_avatar = lambda user: self.avatars.get(user)
        def save(user, avatar, *, now):
            self.avatars[user] = avatar
            return True
        self.repository.set_avatar = save

    def login(self, *args, **kwargs):
        from tests.app_test_login_test import TestLoginTest
        return TestLoginTest.login(self, *args, **kwargs)

    def test_authenticated_cross_client_avatar_and_other_user_isolation(self):
        from tests.app_test_login_test import KEY_B
        token = self.login().json()['accessToken']
        auth = {'Authorization': 'Bearer ' + token}
        value = data_url(png())
        result = self.client.put('/api/v2/me/avatar', headers=auth, json={'avatarDataUrl': value})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.client.get('/api/v2/me/avatar', headers=auth).json()['avatarDataUrl'], value)
        self.login('web')
        response = self.client.get('/api/v2/me/avatar')
        self.assertEqual(response.json()['avatarDataUrl'], value)
        self.assertEqual(response.headers['cache-control'], 'private, no-store')
        self.assertEqual(set(response.json()), {'avatarDataUrl', 'requestId'})
        self.assertEqual(self.client.put('/api/v2/me/avatar', json={'avatarDataUrl': value}).status_code, 401)
        self.client.cookies.clear()
        other = self.login(account='B', credential=KEY_B).json()['accessToken']
        self.assertIsNone(self.client.get('/api/v2/me/avatar', headers={'Authorization': 'Bearer ' + other}).json()['avatarDataUrl'])
        self.assertEqual(self.client.get('/api/v2/me/avatar').status_code, 401)

    def test_invalid_body_and_spoofed_owner_never_write(self):
        token = self.login().json()['accessToken']
        for body in [{'avatarDataUrl': 'data:image/svg+xml;base64,AAAA'},
                     {'avatarDataUrl': data_url(png()), 'userId': str(uuid4())},
                     {'avatarDataUrl': 'x' * 349552}]:
            result = self.client.put('/api/v2/me/avatar', headers={'Authorization': 'Bearer ' + token}, json=body)
            self.assertEqual(result.status_code, 422)
        self.assertEqual(self.avatars, {})

    def test_repository_is_owner_scoped_and_disabled_user_cannot_write(self):
        from tests.app_identity_repository_test import FakeConnection
        from server.app.identity.repository import PostgresIdentityRepository
        from datetime import datetime, timezone
        user = uuid4()
        connection = FakeConnection(rows=[('image-data',), None])
        repo = PostgresIdentityRepository(lambda: connection)
        self.assertEqual(repo.get_avatar(user), 'image-data')
        self.assertFalse(repo.set_avatar(user, data_url(png()), now=datetime.now(timezone.utc)))
        for sql, parameters in connection.cursor_value.statements:
            self.assertIn("WHERE id = %s AND status = 'active'", sql)
            self.assertIn(user, parameters)
