from contextlib import contextmanager
from typing import Any, Callable, Iterator

from server.app.platform.config import AppSettings


class PostgresConnectionFactory:
    """Create short-lived PostgreSQL transactions without exposing the DSN."""

    def __init__(self, settings: AppSettings, connector: Callable[..., Any] | None = None):
        self._settings = settings
        self._connector = connector

    @contextmanager
    def connection(self) -> Iterator[Any]:
        connector = self._connector
        if connector is None:
            try:
                import psycopg
            except ImportError as error:
                raise RuntimeError("psycopg is required for the v2 PostgreSQL runtime") from error
            connector = psycopg.connect

        connection = connector(self._settings.database_url, autocommit=False)
        try:
            yield connection
        except BaseException:
            connection.rollback()
            raise
        else:
            try:
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
        finally:
            connection.close()
