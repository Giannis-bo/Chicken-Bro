import base64
import struct
import unittest
import zlib
from uuid import uuid4


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def png(width=1, height=1, extra=b''):
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + extra + chunk(b'IDAT', zlib.compress(b'\x00\xff\x00\x00' * height)) + chunk(b'IEND', b''))


def data_url(data, kind='png'):
    return f'data:image/{kind};base64,' + base64.b64encode(data).decode()


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

    def test_web_avatar_read_is_owner_scoped_and_mini_upload_is_retired(self):
        from tests.app_test_login_test import KEY_B
        from server.app.identity.test_accounts import TEST_ACCOUNT_IDS
        self.assertEqual(self.login().status_code, 200)
        value = data_url(png())
        self.avatars[TEST_ACCOUNT_IDS['A']] = value
        response = self.client.get('/api/v2/me/avatar')
        self.assertEqual(response.json()['avatarDataUrl'], value)
        self.assertEqual(response.headers['cache-control'], 'private, no-store')
        self.assertEqual(set(response.json()), {'avatarDataUrl', 'requestId'})
        self.assertEqual(self.client.put('/api/v2/me/avatar', json={'avatarDataUrl':value}).status_code, 405)
        self.assertEqual(self.login(account='B', credential=KEY_B).status_code, 200)
        self.assertIsNone(self.client.get('/api/v2/me/avatar').json()['avatarDataUrl'])
        self.client.cookies.clear()
        self.assertEqual(self.client.get('/api/v2/me/avatar').status_code, 401)

    def test_retired_avatar_upload_never_writes(self):
        self.login()
        for body in [{'avatarDataUrl':'data:image/svg+xml;base64,AAAA'},
                     {'avatarDataUrl':data_url(png()), 'userId':str(uuid4())}]:
            self.assertEqual(self.client.put('/api/v2/me/avatar', json=body).status_code, 405)
        self.assertEqual(self.avatars, {})
