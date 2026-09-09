"""Purge only expired chat image bytes; preview by default, no message deletion."""
import argparse
import os
from datetime import datetime, timezone
from server.app.platform.config import AppSettings
from server.app.platform.postgres import PostgresConnectionFactory
from server.app.chickenbro.repository import PostgresChatRepository


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    factory = PostgresConnectionFactory(AppSettings.from_env(os.environ))
    now = datetime.now(timezone.utc)
    if args.apply:
        count = PostgresChatRepository(factory.connection).purge_expired_images(now)
        print(f'Expired image payloads cleared: {count}')
    else:
        with factory.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT count(*),coalesce(sum(octet_length(data)),0) FROM chat.images WHERE data IS NOT NULL AND expires_at<=%s', (now,))
                count, size = cursor.fetchone()
        print(f'Dry-run: {count} expired image payloads, {size} bytes')


if __name__ == '__main__':
    main()
