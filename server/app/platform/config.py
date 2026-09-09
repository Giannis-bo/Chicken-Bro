from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping
import re
from urllib.parse import urlparse


AppEnvironment = Literal["local", "test", "candidate", "production"]


@dataclass(frozen=True)
class AppSettings:
    environment: AppEnvironment
    database_url: str = field(repr=False)
    host: str = "127.0.0.1"
    port: int = 8790
    worker_poll_seconds: float = 1.0
    worker_heartbeat_path: str = ""
    worker_heartbeat_ttl_seconds: int = 45
    web_origin: str = "https://www.chickenbro.cloud"
    web_cookie_name: str = "__Host-chickenbro-session"
    web_csrf_cookie_name: str = "__Host-chickenbro-csrf"
    web_login_ttl_seconds: int = 300
    web_session_ttl_seconds: int = 604800
    qq_appid: str = ""
    qq_app_key: str = field(default="", repr=False)
    qq_redirect_uri: str = ""
    wechat_appid: str = ""
    wechat_secret: str = field(default="", repr=False)
    wechat_page: str = "pages/auth/web-login-confirm"
    wechat_env_version: str = "release"
    wechat_check_path: bool = True
    test_login_enabled: bool = False
    test_login_a_sha256: str = field(default="", repr=False)
    test_login_b_sha256: str = field(default="", repr=False)

    @property
    def qq_callback_path(self) -> str:
        prefix = {"test": "/test/api/v2", "candidate": "/api/v2-candidate"}.get(self.environment, "/api/v2")
        return prefix + "/auth/qq/callback"

    @property
    def qq_landing_path(self) -> str:
        return {"test": "/test/", "candidate": "/web-candidate/"}.get(self.environment, "/")

    @property
    def qq_binding_cookie_name(self) -> str:
        return self.web_cookie_name + "-qq-login"

    def __post_init__(self) -> None:
        if self.qq_appid and re.fullmatch(r"[0-9]{1,32}", self.qq_appid) is None:
            raise ValueError("QQ appid must be numeric")
        if self.qq_redirect_uri or self.qq_appid or self.qq_app_key:
            origin = urlparse(self.web_origin)
            if (origin.scheme != "https" or not origin.netloc or origin.username or origin.password
                    or origin.path not in {"", "/"} or origin.query or origin.fragment
                    or self.qq_redirect_uri != self.web_origin.rstrip("/") + self.qq_callback_path):
                raise ValueError("QQ callback must be the exact HTTPS same-origin callback")
        if not self.test_login_enabled:
            return
        parsed = urlparse(self.database_url)
        if self.environment not in {"local", "test", "candidate"}:
            raise ValueError("test login is forbidden in production")
        if (parsed.path not in {"/chickenbro_test", "/chickenbro_candidate", "/chickenbro_dev"}
                or parsed.query or parsed.fragment or parsed.params):
            raise ValueError("test login requires a dedicated test database without URL overrides")
        if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in
               (self.test_login_a_sha256, self.test_login_b_sha256)):
            raise ValueError("test login requires two SHA256 credential hashes")
        if self.test_login_a_sha256 == self.test_login_b_sha256:
            raise ValueError("test accounts must use distinct credentials")

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppSettings":
        test_login = env.get("WOW_TEST_LOGIN_ENABLED", "0").strip()
        if test_login not in {"0", "1"}:
            raise ValueError("WOW_TEST_LOGIN_ENABLED must be 0 or 1")
        environment = env.get("WOW_APP_ENV", "").strip()
        if environment not in {"local", "test", "candidate", "production"}:
            raise ValueError("WOW_APP_ENV must name a supported environment")

        database_url = env.get("WOW_DATABASE_URL", "").strip()
        if not database_url.startswith(("postgresql://", "postgres://")):
            raise ValueError("WOW_DATABASE_URL must be a PostgreSQL URL")

        host = env.get("WOW_API_V2_HOST", "127.0.0.1").strip()
        try:
            port = int(env.get("WOW_API_V2_PORT", "8790"))
        except (TypeError, ValueError) as error:
            raise ValueError("WOW_API_V2_PORT must be an integer") from error
        try:
            poll_seconds = float(env.get("WOW_WORKER_V2_POLL_SECONDS", "1.0"))
        except (TypeError, ValueError) as error:
            raise ValueError("WOW_WORKER_V2_POLL_SECONDS must be a number") from error

        if environment in {"candidate", "production"} and host not in {"127.0.0.1", "::1", "localhost"}:
            raise ValueError("candidate and production API must bind to loopback")
        if not 1 <= port <= 65535:
            raise ValueError("WOW_API_V2_PORT is outside 1..65535")
        if not 0.1 <= poll_seconds <= 30:
            raise ValueError("WOW_WORKER_V2_POLL_SECONDS is outside 0.1..30")

        default_heartbeat_path = f"/var/lib/chickenbro/{environment}-worker-heartbeat.json"
        worker_heartbeat_path = env.get(
            "WOW_WORKER_V2_HEARTBEAT_PATH",
            default_heartbeat_path,
        ).strip()
        if not worker_heartbeat_path or not Path(worker_heartbeat_path).is_absolute():
            raise ValueError("WOW_WORKER_V2_HEARTBEAT_PATH must be an absolute path")
        if environment in {"candidate", "production"} and worker_heartbeat_path != default_heartbeat_path:
            raise ValueError("WOW_WORKER_V2_HEARTBEAT_PATH must use the environment-scoped managed path")

        web_origin = env.get("WOW_WEB_ORIGIN", "https://www.chickenbro.cloud").strip()
        parsed_origin = urlparse(web_origin)
        if environment in {"candidate", "production"} and (
            parsed_origin.scheme != "https"
            or not parsed_origin.netloc
            or parsed_origin.path not in {"", "/"}
            or parsed_origin.query
            or parsed_origin.fragment
        ):
            raise ValueError("candidate and production Web origin must be HTTPS and origin-only")

        web_cookie_name = env.get("WOW_WEB_COOKIE_NAME", "__Host-chickenbro-session").strip()
        if not web_cookie_name.startswith("__Host-") or any(character.isspace() for character in web_cookie_name):
            raise ValueError("WOW_WEB_COOKIE_NAME must use the __Host- prefix")
        web_csrf_cookie_name = env.get(
            "WOW_WEB_CSRF_COOKIE_NAME",
            "__Host-chickenbro-csrf",
        ).strip()
        if not web_csrf_cookie_name.startswith("__Host-") or any(
            character.isspace() for character in web_csrf_cookie_name
        ):
            raise ValueError("WOW_WEB_CSRF_COOKIE_NAME must use the __Host- prefix")
        if web_cookie_name == web_csrf_cookie_name:
            raise ValueError("Web session and CSRF cookie names must be distinct")

        def bounded_int(name: str, default: str, lower: int, upper: int) -> int:
            try:
                value = int(env.get(name, default))
            except (TypeError, ValueError) as error:
                raise ValueError(f"{name} must be an integer") from error
            if not lower <= value <= upper:
                raise ValueError(f"{name} is outside {lower}..{upper}")
            return value

        web_login_ttl_seconds = bounded_int("WOW_WEB_LOGIN_TTL_SECONDS", "300", 60, 900)
        web_session_ttl_seconds = bounded_int("WOW_WEB_SESSION_TTL_SECONDS", "604800", 300, 2592000)
        worker_heartbeat_ttl_seconds = bounded_int(
            "WOW_WORKER_V2_HEARTBEAT_TTL_SECONDS",
            "45",
            15,
            300,
        )
        wechat_page = env.get("WOW_WECHAT_PAGE", "pages/auth/web-login-confirm").strip()
        if not wechat_page or wechat_page.startswith("/") or any(character.isspace() for character in wechat_page):
            raise ValueError("WOW_WECHAT_PAGE must be a non-empty page path without a leading slash")
        wechat_env_version = env.get("WOW_WECHAT_ENV_VERSION", "release").strip()
        if wechat_env_version not in {"develop", "trial", "release"}:
            raise ValueError("WOW_WECHAT_ENV_VERSION must be develop, trial or release")
        wechat_check_path_raw = env.get("WOW_WECHAT_CHECK_PATH", "1").strip()
        if wechat_check_path_raw not in {"0", "1"}:
            raise ValueError("WOW_WECHAT_CHECK_PATH must be 0 or 1")

        return cls(
            test_login_enabled=test_login == "1",
            test_login_a_sha256=env.get("WOW_TEST_LOGIN_A_SHA256", "").strip(),
            test_login_b_sha256=env.get("WOW_TEST_LOGIN_B_SHA256", "").strip(),
            environment=environment,
            database_url=database_url,
            host=host,
            port=port,
            worker_poll_seconds=poll_seconds,
            worker_heartbeat_path=worker_heartbeat_path,
            worker_heartbeat_ttl_seconds=worker_heartbeat_ttl_seconds,
            web_origin=web_origin,
            web_cookie_name=web_cookie_name,
            web_csrf_cookie_name=web_csrf_cookie_name,
            web_login_ttl_seconds=web_login_ttl_seconds,
            web_session_ttl_seconds=web_session_ttl_seconds,
            qq_appid=env.get("WOW_QQ_APPID", "").strip(),
            qq_app_key=env.get("WOW_QQ_APP_KEY", "").strip(),
            qq_redirect_uri=env.get("WOW_QQ_REDIRECT_URI", "").strip(),
            wechat_appid=env.get("WOW_WECHAT_APPID", "").strip(),
            wechat_secret=env.get("WOW_WECHAT_SECRET", "").strip(),
            wechat_page=wechat_page,
            wechat_env_version=wechat_env_version,
            wechat_check_path=wechat_check_path_raw == "1",
        )
