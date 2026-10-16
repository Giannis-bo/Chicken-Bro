"""Compose the isolated runtime while preserving the current model connection."""
from urllib.parse import urlsplit, urlunsplit


def runtime_environment(source):
    permitted = {'PATH', 'CODEX_HOME', 'WOW_CHICKENBRO_CODEX_ENABLED',
                 'WOW_WARCRAFTLOGS_CLIENT_ID', 'WOW_WARCRAFTLOGS_CLIENT_SECRET',
                 'WOW_WARCRAFTLOGS_GRAPHQL_URL', 'WOW_WARCRAFTLOGS_TIMEOUT_SECONDS',
                 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
                 'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'}
    env = {k: v for k, v in source.items() if k in permitted or
           k.startswith(('WOW_CODEX_', 'WOW_SIMC_', 'SIMC_', 'POE2_'))}
    p = urlsplit(source['WOW_DATABASE_URL'])
    if p.scheme not in ('postgresql', 'postgres') or p.query or p.fragment:
        raise ValueError('invalid source database configuration')
    env.update({
        'WOW_DATABASE_URL': urlunsplit((p.scheme, p.netloc, '/chickenbro_qq_official_candidate', '', '')),
        'PGPASSFILE': '/var/lib/chickenbro/qq-official/pgpass',
        'WOW_APP_ENV': 'candidate', 'WOW_WORKER_V2_SCOPE': 'qq_official',
        'WOW_CHAT_DURABLE_ENABLED': '1',
        'WOW_CHAT_WORKER_TOOL_PORT': '18796',
        'WOW_CODEX_JOBS_DIR': '/var/lib/chickenbro/qq-official/codex-jobs',
    })
    return env


def character_query_credentials(source):
    """Copy only existing read-only WCL OAuth settings into the private runtime."""
    names = ('WOW_WARCRAFTLOGS_CLIENT_ID','WOW_WARCRAFTLOGS_CLIENT_SECRET',
             'WOW_WARCRAFTLOGS_GRAPHQL_URL','WOW_WARCRAFTLOGS_TIMEOUT_SECONDS')
    return {name:source[name] for name in names if source.get(name)}
