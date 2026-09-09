import io
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.error import HTTPError, URLError
from server.app.integrations.warcraftlogs import ChatWarcraftLogsTokenCache, WarcraftLogsAccessError, WarcraftLogsProviderError, warcraftlogs_oauth_token

ENV={'WOW_WARCRAFTLOGS_CLIENT_ID':'id','WOW_WARCRAFTLOGS_CLIENT_SECRET':'secret'}
def response(token='token', expires=100):
    return io.BytesIO(json.dumps({'access_token':token,'expires_in':expires}).encode())

class CacheTests(unittest.TestCase):
    def test_expiry_rotation_endpoint_opener_and_legacy_uncached(self):
        now=[10.0];cache=ChatWarcraftLogsTokenCache(clock=lambda:now[0]);calls=[]
        def fetch(*a,**k):calls.append(k['timeout']);return response(str(len(calls)))
        self.assertEqual(cache.token(10,env=ENV,opener=fetch),'1')
        self.assertEqual(cache.token(10,env=ENV,opener=fetch),'1')
        now[0]+=100;self.assertEqual(cache.token(10,env=ENV,opener=fetch),'2')
        self.assertEqual(cache.token(10,env={**ENV,'WOW_WARCRAFTLOGS_CLIENT_SECRET':'rotated'},opener=fetch),'3')
        self.assertEqual(cache.token(10,env={**ENV,'WOW_WARCRAFTLOGS_TOKEN_URL':'https://alternate.invalid/token'},opener=fetch),'4')
        self.assertEqual(cache.token(10,env=ENV,opener=lambda *a,**k:response('isolated')),'isolated')
        warcraftlogs_oauth_token(10,env=ENV,opener=fetch);warcraftlogs_oauth_token(10,env=ENV,opener=fetch)
        self.assertEqual(len(calls),6)
    def test_rotation_invalidates_previous_secret_and_legacy_never_retries(self):
        cache=ChatWarcraftLogsTokenCache();calls=[]
        def fetch(*a,**k):calls.append(1);return response(str(len(calls)))
        cache.token(1,env=ENV,opener=fetch)
        cache.token(1,env={**ENV,'WOW_WARCRAFTLOGS_CLIENT_SECRET':'new'},opener=fetch)
        self.assertEqual(cache.token(1,env=ENV,opener=fetch),'3')
        calls.clear()
        def failed(*a,**k):calls.append(1);raise URLError('private upstream message')
        with self.assertRaises(WarcraftLogsProviderError) as error:warcraftlogs_oauth_token(1,env=ENV,opener=failed)
        self.assertEqual(len(calls),1);self.assertNotIn('private',str(error.exception))

    def test_auth_invalidation_is_exact_and_does_not_evict_new_token(self):
        cache=ChatWarcraftLogsTokenCache();calls=[]
        def fetch(*a,**k):calls.append(1);return response(str(len(calls)))
        other={**ENV,'WOW_WARCRAFTLOGS_CLIENT_ID':'other'}
        self.assertEqual(cache.token(1,env=ENV,opener=fetch),'1')
        self.assertEqual(cache.token(1,env=other,opener=fetch),'2')
        cache.invalidate('1',env=ENV,opener=fetch)
        self.assertEqual(cache.token(1,env=ENV,opener=fetch),'3')
        self.assertEqual(cache.token(1,env=other,opener=fetch),'2')
        cache.invalidate('1',env=ENV,opener=fetch)
        self.assertEqual(cache.token(1,env=ENV,opener=fetch),'3')

    def test_invalid_expiry_never_cached(self):
        for expiry in [None,False,0,-1,'100',float('inf')]:
            cache=ChatWarcraftLogsTokenCache();calls=[]
            def fetch(*a,**k):calls.append(1);return response(expires=expiry)
            cache.token(1,env=ENV,opener=fetch);cache.token(1,env=ENV,opener=fetch)
            self.assertEqual(len(calls),2)
    def test_singleflight(self):
        cache=ChatWarcraftLogsTokenCache();entered=threading.Event();release=threading.Event();calls=[]
        def fetch(*a,**k):calls.append(1);entered.set();release.wait(1);return response()
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(cache.token,2,env=ENV,opener=fetch) for _ in range(3)]
            self.assertTrue(entered.wait(1));release.set();self.assertEqual([f.result() for f in futures],['token']*3)
        self.assertEqual(len(calls),1)
    def test_retry_classification_no_failure_cache(self):
        for failure,retry in [(HTTPError('safe',429,'',{},None),True),(HTTPError('safe',503,'',{},None),True),(URLError('network'),True),(HTTPError('safe',401,'',{},None),False),(HTTPError('safe',403,'',{},None),False),(HTTPError('safe',400,'',{},None),False),(ValueError('invalid JSON'),False)]:
            cache=ChatWarcraftLogsTokenCache();calls=[]
            def fetch(*a,**k):
                calls.append(1)
                if len(calls)==1:raise failure
                return response()
            if retry:self.assertEqual(cache.token(2,env=ENV,opener=fetch),'token')
            else:
                with self.assertRaises((WarcraftLogsAccessError,WarcraftLogsProviderError)):cache.token(2,env=ENV,opener=fetch)
                self.assertEqual(len(calls),1)
                self.assertEqual(cache.token(2,env=ENV,opener=fetch),'token')
            self.assertEqual(len(calls),2)
    def test_retry_remaining_deadline_and_no_third_attempt(self):
        now=[0.0];cache=ChatWarcraftLogsTokenCache(clock=lambda:now[0]);timeouts=[]
        def fetch(*a,**k):timeouts.append(k['timeout']);now[0]+=0.75;raise URLError('network')
        with self.assertRaises(WarcraftLogsProviderError):cache.token(1,env=ENV,opener=fetch)
        self.assertEqual(timeouts,[1,0.25])
        now[0]=0;timeouts.clear()
        def exhausted(*a,**k):timeouts.append(k['timeout']);now[0]+=2;raise URLError('network')
        with self.assertRaises(WarcraftLogsProviderError):cache.token(1,env=ENV,opener=exhausted)
        self.assertEqual(timeouts,[1])
    def test_lock_wait_respects_budget_and_cache_bound(self):
        cache=ChatWarcraftLogsTokenCache(max_entries=2);calls=[]
        cache._lock.acquire()
        try:
            with self.assertRaises(WarcraftLogsProviderError):cache.token(0.01,env=ENV,opener=lambda *a,**k:calls.append(1))
        finally:cache._lock.release()
        self.assertEqual(calls,[])
        def fetch(*a,**k):return response()
        for n in range(4):cache.token(1,env={**ENV,'WOW_WARCRAFTLOGS_CLIENT_ID':str(n)},opener=fetch)
        self.assertLessEqual(len(cache._entries),2)

if __name__=='__main__':unittest.main()
