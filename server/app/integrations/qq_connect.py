"""QQ Connect server-side OAuth. Credentials live only during one exchange."""
import re
from urllib.parse import urlencode
import httpx

from server.app.identity.ports import QqIdentity, QqProviderError
from server.app.platform.config import AppSettings


class QqConnectClient:
    def __init__(self, settings: AppSettings, *, transport: httpx.BaseTransport | None = None):
        self._settings = settings
        self._transport = transport

    def authorization_url(self, state: str) -> str:
        return 'https://graph.qq.com/oauth2.0/authorize?' + urlencode({
            'response_type': 'code', 'client_id': self._settings.qq_appid,
            'redirect_uri': self._settings.qq_redirect_uri, 'state': state,
            'scope': 'get_user_info',
        })

    def exchange_code(self, code: str) -> QqIdentity:
        # QQ documents GET for these endpoints. Do not use httpx's request logging:
        # its INFO event includes the credential-bearing URL.
        try:
            transport = self._transport or httpx.HTTPTransport(trust_env=False, retries=0)
            with httpx.Client(timeout=httpx.Timeout(8.0, connect=3.0), follow_redirects=False,
                              transport=transport, trust_env=False) as client:
                token_data = self._get(client, transport, '/token', {
                    'grant_type': 'authorization_code', 'client_id': self._settings.qq_appid,
                    'client_secret': self._settings.qq_app_key, 'code': code,
                    'redirect_uri': self._settings.qq_redirect_uri, 'fmt': 'json',
                })
                token = token_data.get('access_token')
                expires = token_data.get('expires_in')
                if (not isinstance(token, str) or re.fullmatch(r'[A-Za-z0-9_-]{16,512}', token) is None
                        or type(expires) is not int or expires <= 0):
                    raise QqProviderError('QQ provider unavailable')
                identity = self._get(client, transport, '/me', {'access_token': token, 'fmt': 'json'})
                appid, openid = identity.get('client_id'), identity.get('openid')
                if (appid != self._settings.qq_appid or not isinstance(openid, str)
                        or re.fullmatch(r'[A-Za-z0-9_-]{16,256}', openid) is None):
                    raise QqProviderError('QQ provider unavailable')
                profile = {}
                try:
                    data = self._get(client, transport, '/user/get_user_info', {
                        'access_token': token, 'oauth_consumer_key': appid, 'openid': openid, 'fmt': 'json'})
                    if type(data.get('ret')) is int and data['ret'] == 0:
                        profile = {'nickname': data.get('nickname'),
                                   'avatarUrl': data.get('figureurl_qq_2') or data.get('figureurl_qq_1')}
                except Exception:
                    pass  # Optional public profile cannot block identity authentication.
                return QqIdentity(client_id=appid, openid=openid, profile=profile)
        except Exception:
            raise QqProviderError('QQ provider unavailable') from None

    @staticmethod
    def _get(client: httpx.Client, transport: httpx.BaseTransport, path: str, params: dict) -> dict:
        # Send through the transport directly to avoid httpx INFO request URL logs.
        # The fixed graph.qq.com URL, TLS transport, timeout extensions and no
        # redirect handling are retained; no credential-bearing URL escapes here.
        request = client.build_request('GET', 'https://graph.qq.com' + (path if path.startswith('/user/') else '/oauth2.0' + path), params=params)
        response = transport.handle_request(request)
        try:
            if response.status_code != 200:
                raise QqProviderError('QQ provider unavailable')
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 16384:
                    raise QqProviderError('QQ provider unavailable')
                chunks.append(chunk)
            import json
            data = json.loads(b''.join(chunks))
        finally:
            response.close()
        if not isinstance(data, dict) or any(key in data for key in ('error', 'error_description', 'code')):
            raise QqProviderError('QQ provider unavailable')
        return data
