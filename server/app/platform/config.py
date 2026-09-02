from dataclasses import dataclass, field
from typing import Literal, Mapping
from urllib.parse import urlparse


AppEnvironment = Literal["local", "test", "candidate", "production"]


@dataclass(frozen=True)
class AppSettings:
    environment: AppEnvironment
    database_url: str = field(repr=False)
    host: str = "127.0.0.1"
    port: int = 8790
    worker_poll_seconds: float = 1.0
    web_origin: str = "https://www.chickenbro.cloud"
    web_cookie_name: str = "__Host-wow_v2"
    web_login_ttl_seconds: int = 300
    web_session_ttl_seconds: int = 604800
    wechat_appid: str = ""
    wechat_secret: str = field(default="", repr=False)
    wechat_page: str = "pages/auth/web-login-confirm"
    wechat_env_version: str = "release"
    wechat_check_path: bool = True
    prototype_enabled: bool = False
    prototype_ttl_seconds: int = 3600

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppSettings":
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

        web_cookie_name = env.get("WOW_WEB_COOKIE_NAME", "__Host-wow_v2").strip()
        if not web_cookie_name.startswith("__Host-") or any(character.isspace() for character in web_cookie_name):
            raise ValueError("WOW_WEB_COOKIE_NAME must use the __Host- prefix")

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
        wechat_page = env.get("WOW_WECHAT_PAGE", "pages/auth/web-login-confirm").strip()
        if not wechat_page or wechat_page.startswith("/") or any(character.isspace() for character in wechat_page):
            raise ValueError("WOW_WECHAT_PAGE must be a non-empty page path without a leading slash")
        wechat_env_version = env.get("WOW_WECHAT_ENV_VERSION", "release").strip()
        if wechat_env_version not in {"develop", "trial", "release"}:
            raise ValueError("WOW_WECHAT_ENV_VERSION must be develop, trial or release")
        wechat_check_path_raw = env.get("WOW_WECHAT_CHECK_PATH", "1").strip()
        if wechat_check_path_raw not in {"0", "1"}:
            raise ValueError("WOW_WECHAT_CHECK_PATH must be 0 or 1")

        prototype_enabled_raw = env.get("WOW_WEB_PROTOTYPE_ENABLED", "0").strip()
        if prototype_enabled_raw not in {"0", "1"}:
            raise ValueError("WOW_WEB_PROTOTYPE_ENABLED must be 0 or 1")
        prototype_ttl_seconds = bounded_int("WOW_WEB_PROTOTYPE_TTL_SECONDS", "3600", 300, 86400)

        return cls(
            environment=environment,
            database_url=database_url,
            host=host,
            port=port,
            worker_poll_seconds=poll_seconds,
            web_origin=web_origin,
            web_cookie_name=web_cookie_name,
            web_login_ttl_seconds=web_login_ttl_seconds,
            web_session_ttl_seconds=web_session_ttl_seconds,
            wechat_appid=env.get("WOW_WECHAT_APPID", "").strip(),
            wechat_secret=env.get("WOW_WECHAT_SECRET", "").strip(),
            wechat_page=wechat_page,
            wechat_env_version=wechat_env_version,
            wechat_check_path=wechat_check_path_raw == "1",
            prototype_enabled=prototype_enabled_raw == "1",
            prototype_ttl_seconds=prototype_ttl_seconds,
        )
