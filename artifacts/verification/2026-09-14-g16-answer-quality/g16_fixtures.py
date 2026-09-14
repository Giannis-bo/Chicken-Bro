"""Read-only G16 replay corpus; never opens sockets or calls business providers."""
import copy
import json
from pathlib import Path
from server.chickenbro_native_mcp import TOOL_DEFINITIONS
from scripts.agent_benchmark_fixtures import validate, packet, native_packet

DATA = json.loads(Path(__file__).with_name('cases.json').read_text())
CASES = DATA['cases']
SCHEMAS = {d['name']: d['inputSchema'] for d in TOOL_DEFINITIONS}
FORUM = 'https://us.forums.blizzard.com/en/wow/t/holy-bulwark-macro-broken-after-1205/2294794'
CLIQUE = 'https://www.curseforge.com/wow/addons/clique'
KEYS = {FORUM: 'forum', CLIQUE: 'clique', 'https://fixture.invalid/wa-profile': 'variant', 'https://fixture.invalid/nameplate': 'holdout'}

class FixtureSession:
    def __init__(self, case_id):
        if case_id not in {c['id'] for c in CASES}: raise ValueError('Unknown case')
        self.case_id = case_id
        self.calls = 0

    def call(self, name, args):
        self.calls += 1
        if self.calls > 8:
            return {'status': 'error', 'errorCode': 'FIXTURE_BUDGET_EXHAUSTED'}
        try:
            validate(args, SCHEMAS[name])
            if name != 'research_public_web':
                return {'status': 'unavailable', 'errorCode': 'SOURCE_NOT_FOUND', 'facts': [], 'limitations': ['No owned business record exists in this isolated corpus.']}
            allowed = {'original': [FORUM, CLIQUE], 'variant': ['https://fixture.invalid/wa-profile'], 'holdout': ['https://fixture.invalid/nameplate'], 'normal': [CLIQUE], 'permission': []}[self.case_id]
            target = args['target'].rstrip('/')
            if target.startswith('https://'):
                if target not in allowed: raise ValueError('Page not present in fixed corpus')
                page = DATA['pages'][target]
                offset = args.get('start', 0)
                if offset not in (0, 1000): raise ValueError('Use returned nextStart')
                index = offset // 1000
                if args.get('match'):
                    matches = [i for i,c in enumerate(page['chunks']) if args['match'].lower() in c['text'].lower()]
                    if not matches: raise ValueError('No matching retained paragraph')
                    index = matches[0]
                if index >= len(page['chunks']): raise ValueError('No such retained page')
                chunk = page['chunks'][index]
                complete = index == len(page['chunks'])-1
                key = KEYS[target]+('.continuation' if index else '.document')
                fact = {'url': target, 'title': page['title'], 'text': chunk['text'], 'content': chunk['text'], 'complete': complete, 'nextStart': None if complete else 1000, 'provenance': page['provenance']}
                response = native_packet(name,args,packet([fact],[key]))
                response.update(complete=complete,nextStart=fact['nextStart'],readStart=index*1000)
                return response
            rows = [{'url':u,'title':DATA['pages'][u]['title'],'snippet':DATA['pages'][u]['chunks'][0]['text'][:70]} for u in allowed]
            return native_packet(name,args,packet([{'query':target,'results':rows}],['search']))
        except (ValueError,KeyError,TypeError) as exc:
            return {'status':'error','errorCode':'FIXTURE_UNAVAILABLE','message':str(exc)}
