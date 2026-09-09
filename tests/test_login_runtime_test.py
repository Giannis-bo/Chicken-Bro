import unittest

from server.test_login_runtime import prepare_environment


class TestLoginRuntimeTest(unittest.TestCase):
    def test_reuses_existing_auth_in_memory_and_always_targets_test_database(self):
        source = {'WOW_DATABASE_URL': 'postgresql://wow_app@127.0.0.1:5432/chickenbro_prod',
                  'PGPASSFILE': '/existing/credentials', 'WOW_APP_ENV': 'production'}
        result = prepare_environment(source, lambda _: '127.0.0.1:5432:chickenbro_prod:wow_app:existing\\:password\n')
        self.assertEqual(result['WOW_DATABASE_URL'], 'postgresql://wow_app@127.0.0.1:5432/chickenbro_test')
        self.assertEqual(result['PGPASSWORD'], 'existing:password')
        self.assertEqual(result['WOW_APP_ENV'], 'test')
        self.assertEqual(source['WOW_APP_ENV'], 'production')

    def test_runtime_isolation_overrides_all_inherited_production_values(self):
        source = {'WOW_DATABASE_URL': 'postgresql://wow_app@localhost/chickenbro_prod', 'PGPASSFILE': '/existing',
                  'WOW_WEB_COOKIE_NAME': '__Host-production-session', 'WOW_WEB_CSRF_COOKIE_NAME': '__Host-production-csrf',
                  'WOW_WORKER_V2_HEARTBEAT_PATH': '/var/lib/chickenbro/production-worker-heartbeat.json',
                  'WOW_CODEX_JOBS_DIR': '/var/lib/chickenbro/codex-jobs', 'WOW_API_V2_PORT': '8790'}
        result = prepare_environment(source, lambda _: '*:*:chickenbro_prod:wow_app:fixture-password')
        self.assertEqual(result['WOW_WEB_COOKIE_NAME'], '__Host-chickenbro-test-session')
        self.assertEqual(result['WOW_WEB_CSRF_COOKIE_NAME'], '__Host-chickenbro-test-csrf')
        self.assertEqual(result['WOW_WORKER_V2_HEARTBEAT_PATH'], '/var/lib/chickenbro/test-worker-heartbeat.json')
        self.assertEqual(result['WOW_CODEX_JOBS_DIR'], '/var/lib/chickenbro/test-codex-jobs')
        self.assertEqual(result['WOW_API_V2_PORT'], '8792')

    def test_unexpected_source_and_missing_credentials_fail_closed(self):
        for url in ('postgresql://wow_app@localhost/other',
                    'postgresql://wow_app@localhost/chickenbro_prod?dbname=other'):
            with self.assertRaises(ValueError):
                prepare_environment({'WOW_DATABASE_URL': url}, lambda _: '')
        with self.assertRaises(ValueError):
            prepare_environment({'WOW_DATABASE_URL': 'postgresql://wow_app@localhost/chickenbro_prod',
                                 'PGPASSFILE': '/existing'}, lambda _: '')

    def test_qq_callback_is_fixed_to_test_without_fabricating_credentials(self):
        source = {'WOW_DATABASE_URL':'postgresql://wow_app:fixture@localhost/chickenbro_prod',
                  'WOW_QQ_APPID':'1905584243', 'WOW_QQ_APP_KEY':'fixture-key',
                  'WOW_QQ_REDIRECT_URI':'https://www.chickenbro.cloud/api/v2/auth/qq/callback'}
        env = prepare_environment(source)
        self.assertEqual(env['WOW_QQ_REDIRECT_URI'], 'https://www.chickenbro.cloud/test/api/v2/auth/qq/callback')
        self.assertEqual(env['WOW_QQ_APP_KEY'], 'fixture-key')
        del source['WOW_QQ_APP_KEY']
        self.assertNotIn('WOW_QQ_APP_KEY', prepare_environment(source))
        self.assertNotIn('WOW_QQ_REDIRECT_URI', prepare_environment({'WOW_DATABASE_URL':source['WOW_DATABASE_URL']}))
