"""Official QQ API client. Writes are never retried after ambiguous failures."""
import time
from urllib.parse import urlsplit

import httpx

from .policy import valid_id, valid_message_id

API = 'https://api.bot.qq.com'


class OfficialError(RuntimeError):
    def __init__(self, code='transport', *, definite=False):
        safe = str(code) if isinstance(code, int) else code if code in {
            'transport', 'invalid_response', 'invalid_token', 'invalid_gateway', 'missing_receipt'} else 'unknown'
        super().__init__('QQ official error code=' + safe)
        self.code, self.definite = code, definite


class OfficialClient:
    def __init__(self, app_id, app_secret, *, http=None, clock=time.monotonic, markdown=False):
        self.app_id = app_id
        self._secret = app_secret
        self.http = http or httpx.Client(timeout=10, follow_redirects=False, trust_env=False)
        self.clock = clock
        self.markdown = markdown
        self._token, self._expires = None, 0

    def close(self):
        self.http.close()

    def _request(self, method, path, *, body=None, authenticated=True):
        headers = {'Authorization': 'QQBot ' + self.access_token()} if authenticated else {}
        try:
            response = self.http.request(method, API + path, headers=headers, json=body)
            data = response.json()
        except (httpx.HTTPError, ValueError):
            raise OfficialError() from None
        if not isinstance(data, dict):
            raise OfficialError('invalid_response')
        code = data.get('code', data.get('err_code', 0))
        if response.status_code not in (200, 201, 202) or code not in (0, None):
            raise OfficialError(code if isinstance(code, int) else response.status_code, definite=True)
        return data

    def access_token(self):
        if self._token and self.clock() < self._expires:
            return self._token
        data = self._request('POST', '/app/getAppAccessToken', authenticated=False,
                             body={'appId': self.app_id, 'clientSecret': self._secret})
        token = data.get('access_token')
        try:
            ttl = int(data['expires_in'])
        except (KeyError, TypeError, ValueError):
            raise OfficialError('invalid_token') from None
        if not isinstance(token, str) or not token or any(c.isspace() for c in token) or not 60 <= ttl <= 7200:
            raise OfficialError('invalid_token')
        self._token, self._expires = token, self.clock() + ttl - 60
        return token

    def gateway_url(self):
        url = self._request('GET', '/gateway').get('url')
        if not isinstance(url, str):
            raise OfficialError('invalid_gateway')
        p = urlsplit(url)
        if p.scheme != 'wss' or p.hostname not in ('api.bot.qq.com', 'api.sgroup.qq.com') or p.port not in (None, 443) or p.username or p.password or p.fragment:
            raise OfficialError('invalid_gateway')
        return url

    def send_group(self, group, message_id, text, sequence):
        if not valid_id(group) or not valid_message_id(message_id) or not isinstance(text, str) or not 1 <= len(text) <= 1500:
            raise ValueError('invalid official reply')
        if type(sequence) is not int or not 1 <= sequence <= 5:
            raise ValueError('official reply limit exceeded')
        body = {'msg_type':2, 'markdown':{'content':text}} if self.markdown else {'msg_type':0,'content':text}
        body.update(msg_id=message_id,msg_seq=sequence)
        data = self._request('POST', f'/v2/groups/{group}/messages', body=body)
        receipt = data.get('id')
        if not valid_message_id(receipt):
            raise OfficialError('missing_receipt')
        return receipt
