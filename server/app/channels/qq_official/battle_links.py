"""QQ share-link normalization: extract report identity, never fetch the URL."""
from html import unescape
import re
from urllib.parse import parse_qsl, unquote, urlsplit


def fight_selector(value):
    value=value.strip().lower()
    if value in ('last','all'):
        return value
    parts=value.split(',')
    if not 1<=len(parts)<=50 or any(not re.fullmatch(r'[0-9]{1,9}',p) or int(p)<=0 for p in parts):
        raise ValueError('invalid fight selector')
    ids=list(dict.fromkeys(int(p) for p in parts))
    return ids[0] if len(ids)==1 else ','.join(map(str,ids))


def parse_report_link(value):
    value=unescape(value.strip()).rstrip('。，、；！')
    if len(value)>=2 and value[0] in ('"',"'") and value[-1]==value[0]:
        value=value[1:-1]
    markdown=re.fullmatch(r'\[[^\]\r\n]{1,150}\]\((https?://\S+)\)',value,re.I)
    if markdown:
        value=markdown[1]
    elif value.startswith('<') and value.endswith('>'):
        value=value[1:-1]
    if any(ord(c)<32 or c.isspace() for c in value):
        raise ValueError('invalid URL whitespace')
    if '://' not in value:
        value='https://'+value
    raw=urlsplit(value)
    host=(raw.hostname or '').lower().rstrip('.')
    if (raw.scheme.lower() not in ('http','https') or raw.username is not None or raw.password is not None or
        not re.fullmatch(r'(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*warcraftlogs\.com',host) or
        raw.port not in (None,443 if raw.scheme.lower()=='https' else 80)):
        raise ValueError('invalid WCL host')
    path=unquote(raw.path)
    match=re.fullmatch(r'/reports/([A-Za-z0-9]{16})(?:/[^\r\n]*)?',path,re.I)
    if not match:
        raise ValueError('invalid report path')
    # Graph/view/source/time/pin parameters describe the browser view. This
    # command analyzes a whole encounter/run and uses only the fight selector.
    selectors=[fight_selector(v) for k,v in parse_qsl(raw.query,keep_blank_values=True)+
               parse_qsl(raw.fragment.lstrip('?'),keep_blank_values=True) if k.lower()=='fight']
    if selectors and any(v!=selectors[0] for v in selectors):
        raise ValueError('conflicting fight selectors')
    return 'https://www.warcraftlogs.com/reports/'+match[1],selectors[0] if selectors else None
