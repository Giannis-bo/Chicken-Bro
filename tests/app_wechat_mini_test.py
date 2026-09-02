import unittest

from server.app.integrations.wechat_mini import (
    WechatMiniClient,
    WechatNotConfiguredError,
    WechatProviderError,
)
from server.app.platform.config import AppSettings


class FakeResponse:
    def __init__(self, *, payload=None, content=b"", content_type="application/json", status_code=200):
        self._payload = payload
        self.content = content
        self.headers = {"content-type": content_type}
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        return self.responses.pop(0)

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)


def configured_settings():
    return AppSettings(
        environment="test",
        database_url="postgresql://redacted",
        wechat_appid="wx-test",
        wechat_secret="secret-must-not-leak",
        wechat_page="pages/auth/web-login-confirm",
        wechat_env_version="trial",
    )


class AppWechatMiniTest(unittest.TestCase):
    def test_code_exchange_returns_internal_adapter_identity_without_secret_in_repr(self):
        client = FakeHttpClient([FakeResponse(payload={
            "openid": "openid-main",
            "unionid": "union-main",
        })])
        adapter = WechatMiniClient(configured_settings(), http_client=client)

        identity = adapter.exchange_code("short-lived-code")

        self.assertEqual(identity.openid, "openid-main")
        self.assertEqual(identity.unionid, "union-main")
        self.assertNotIn("secret-must-not-leak", repr(adapter))
        self.assertNotIn("secret-must-not-leak", str(identity))

    def test_mini_code_rejects_json_provider_errors_and_accepts_png(self):
        json_error_client = FakeHttpClient([
            FakeResponse(payload={"access_token": "access-token", "expires_in": 7200}),
            FakeResponse(payload={"errcode": 40001, "errmsg": "bad token"}),
        ])
        adapter = WechatMiniClient(configured_settings(), http_client=json_error_client)
        with self.assertRaises(WechatProviderError):
            adapter.create_mini_code(
                scene="opaque-scene",
                page="pages/auth/web-login-confirm",
                env_version="trial",
            )

        png_client = FakeHttpClient([
            FakeResponse(payload={"access_token": "access-token", "expires_in": 7200}),
            FakeResponse(content=b"\x89PNG\r\n\x1a\nreal", content_type="image/png"),
        ])
        adapter = WechatMiniClient(configured_settings(), http_client=png_client)
        self.assertTrue(adapter.create_mini_code(
            scene="opaque-scene",
            page="pages/auth/web-login-confirm",
            env_version="trial",
        ).startswith(b"\x89PNG"))

    def test_candidate_can_disable_path_check_and_accepts_real_jpeg(self):
        settings = AppSettings(
            **{
                **configured_settings().__dict__,
                "wechat_check_path": False,
            },
        )
        client = FakeHttpClient([
            FakeResponse(payload={"access_token": "access-token", "expires_in": 7200}),
            FakeResponse(content=b"\xff\xd8\xffreal", content_type="image/jpeg"),
        ])
        adapter = WechatMiniClient(settings, http_client=client)

        image = adapter.create_mini_code(
            scene="opaque-scene",
            page="pages/auth/web-login-confirm",
            env_version="trial",
        )

        self.assertTrue(image.startswith(b"\xff\xd8\xff"))
        self.assertFalse(client.calls[1][2]["json"]["check_path"])

    def test_missing_wechat_config_fails_closed(self):
        settings = AppSettings(environment="test", database_url="postgresql://redacted")
        adapter = WechatMiniClient(settings, http_client=FakeHttpClient([]))
        with self.assertRaises(WechatNotConfiguredError):
            adapter.exchange_code("code")
