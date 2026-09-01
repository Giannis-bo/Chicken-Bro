from dataclasses import dataclass, field
from typing import Literal, Mapping


AppEnvironment = Literal["local", "test", "candidate", "production"]


@dataclass(frozen=True)
class AppSettings:
    environment: AppEnvironment
    database_url: str = field(repr=False)
    host: str = "127.0.0.1"
    port: int = 8790
    worker_poll_seconds: float = 1.0

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

        return cls(
            environment=environment,
            database_url=database_url,
            host=host,
            port=port,
            worker_poll_seconds=poll_seconds,
        )
