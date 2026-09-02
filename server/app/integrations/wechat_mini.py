from collections.abc import Callable, Mapping
import time
from typing import Any

from server.app.identity.ports import (
    WechatAdapterError,
    WechatIdentity,
    WechatNotConfiguredError,
    WechatProviderError,
)
from server.app.platform.config import AppSettings


_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"


class WechatMiniClient:
    """Small, secret-free-in-output adapter for the WeChat mini-program APIs."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        http_client: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._settings = settings
        if http_client is None:
            try:
                import httpx
            except ModuleNotFoundError as error:
                raise RuntimeError("httpx is required for the WeChat provider client") from error
            http_client = httpx.Client(timeout=8.0)
        self._http_client = http_client
        self._clock = clock
        self._access_token: tuple[str, float] | None = None

    def exchange_code(self, code: str) -> WechatIdentity:
        self._ensure_configured()
        if not isinstance(code, str) or not code.strip() or len(code) > 512 or any(character.isspace() for character in code):
            raise WechatProviderError("WeChat authorization code is invalid")
        try:
            response = self._http_client.get(
                "https://api.weixin.qq.com/sns/jscode2session",
                params={
                    "appid": self._settings.wechat_appid,
                    "secret": self._settings.wechat_secret,
                    "js_code": code,
                    "grant_type": "authorization_code",
                },
            )
            payload = self._json_payload(response)
        except WechatAdapterError:
            raise
        except Exception:
            raise WechatProviderError("WeChat provider unavailable") from None

        openid = payload.get("openid")
        if not isinstance(openid, str) or not openid or len(openid) > 256:
            raise WechatProviderError("WeChat provider returned no usable identity")
        unionid = payload.get("unionid")
        return WechatIdentity(
            openid=openid,
            unionid=unionid if isinstance(unionid, str) and unionid else None,
        )

    def create_mini_code(self, *, scene: str, page: str, env_version: str) -> bytes:
        self._ensure_configured()
        if not isinstance(scene, str) or not 1 <= len(scene) <= 32 or any(character.isspace() for character in scene):
            raise WechatProviderError("WeChat scene is invalid")
        if not isinstance(page, str) or not page or page.startswith("/"):
            raise WechatProviderError("WeChat page is invalid")
        if env_version not in {"develop", "trial", "release"}:
            raise WechatProviderError("WeChat environment is invalid")

        access_token = self._get_access_token()
        try:
            response = self._http_client.post(
                "https://api.weixin.qq.com/wxa/getwxacodeunlimit",
                params={"access_token": access_token},
                json={
                    "scene": scene,
                    "page": page,
                    "env_version": env_version,
                    "check_path": self._settings.wechat_check_path,
                },
            )
        except Exception:
            raise WechatProviderError("WeChat provider unavailable") from None

        content = getattr(response, "content", b"")
        content_type = str(getattr(response, "headers", {}).get("content-type", "")).split(";", 1)[0].lower()
        if not isinstance(content, bytes):
            raise WechatProviderError("WeChat provider did not return an image")
        if content.startswith(_PNG_SIGNATURE):
            expected_content_type = "image/png"
        elif content.startswith(_JPEG_SIGNATURE):
            expected_content_type = "image/jpeg"
        else:
            raise WechatProviderError("WeChat provider did not return a supported image")
        if content_type not in {"", expected_content_type}:
            raise WechatProviderError("WeChat provider returned an image with an invalid MIME type")
        return content

    def _get_access_token(self) -> str:
        now = self._clock()
        if self._access_token is not None and self._access_token[1] > now + 60:
            return self._access_token[0]
        try:
            response = self._http_client.get(
                "https://api.weixin.qq.com/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": self._settings.wechat_appid,
                    "secret": self._settings.wechat_secret,
                },
            )
            payload = self._json_payload(response)
        except WechatAdapterError:
            raise
        except Exception:
            raise WechatProviderError("WeChat provider unavailable") from None
        token = payload.get("access_token")
        expires_in = payload.get("expires_in")
        if not isinstance(token, str) or not token or not isinstance(expires_in, (int, float)):
            raise WechatProviderError("WeChat provider returned no access token")
        self._access_token = (token, now + max(float(expires_in), 60.0))
        return token

    @staticmethod
    def _json_payload(response: Any) -> Mapping[str, Any]:
        status_code = getattr(response, "status_code", 200)
        if not isinstance(status_code, int) or not 200 <= status_code < 300:
            raise WechatProviderError("WeChat provider unavailable")
        try:
            payload = response.json()
        except Exception:
            raise WechatProviderError("WeChat provider returned malformed JSON") from None
        if not isinstance(payload, Mapping):
            raise WechatProviderError("WeChat provider returned malformed JSON")
        error_code = payload.get("errcode")
        if error_code not in (None, 0, "0"):
            raise WechatProviderError("WeChat provider rejected request")
        return payload

    def _ensure_configured(self) -> None:
        if not self._settings.wechat_appid or not self._settings.wechat_secret:
            raise WechatNotConfiguredError("WeChat mini-program credentials are not configured")
