"""Conservative per-generation admission, before external work (including batches).

Unknown ranking identities reserve slots; successful receipts bind those slots to
characters so profile follow-ups do not consume a second slot. Failed/anonymous
samples retain reservations. Semantic continuation is governed by the agent policy.
"""
import copy
import json
from time import monotonic
from urllib.parse import urlparse, parse_qs, unquote
from server.app.simulation.sources import parse_character_source_url


def blocked(dimension):
    return {'status': 'blocked', 'errorCode': 'RESEARCH_BUDGET_EXCEEDED',
            'facts': [], 'evidence': [], 'evidenceRefs': [],
            'limitations': [f'Research {dimension} budget exhausted. Stop expanding the research; report only verified scope and gaps.'],
            'nextActions': ['Decline the oversized scope and offer a bounded alternative; do not split it into more calls.']}


def character_key(region, realm, name):
    return 'character:' + ':'.join(unquote(str(v)).strip().casefold().replace(' ', '-') for v in (region, realm, name))


def profile_key(url):
    parsed = parse_character_source_url(url)
    return character_key(parsed.region, parsed.realm, parsed.character_name)


def report_scope(url):
    parsed = urlparse(url)
    params = {**parse_qs(parsed.query), **parse_qs(parsed.fragment)}
    code = parsed.path.rstrip('/').split('/')[-1]
    fight = params.get('fight', ['selected'])[0]
    return code + ':' + fight, params.get('source', [''])[0]


class ResearchBudget:
    def __init__(self):
        self.started = monotonic()
        self.calls = 0
        self.events = 0
        self.players = set()
        self.groups = set()
        self.fights = set()
        self.slots = {}
        self.report_players = {}
        self.report_actors = {}
        self.pages = set()
        self.web_searches = 0

    def reserve(self, provider, target, options):
        if monotonic() - self.started >= 360:
            return blocked('time'), None
        # All mutations are committed together; caller holds the gateway lock.
        trial = copy.deepcopy(self)
        receipt = []
        error = trial._reserve(provider, target, options or {}, receipt)
        if error:
            return blocked(error), None
        self.__dict__.update(trial.__dict__)
        return None, receipt

    def _reserve(self, provider, target, options, receipt):
        if provider == 'warcraftlogs_batch':
            queries = options.get('queries', [])
            if not isinstance(queries, list) or not 1 <= len(queries) <= 3:
                return 'batch'
            for query in queries:
                error = self._reserve('warcraftlogs', query.get('target', ''), query.get('options') or {}, receipt)
                if error:
                    return error
            return None
        if provider == 'raiderio_batch':
            targets = options.get('targets', [])
            if not isinstance(targets, list) or not 1 <= len(targets) <= 10:
                return 'players (maximum 10)'
            for url in targets:
                error = self._reserve('raiderio', url, {}, receipt)
                if error:
                    return error
            return None
        self.calls += 1
        if self.calls > 48:
            return 'source calls (maximum 48 subqueries)'
        if provider in ('raiderio_rankings', 'warcraftlogs_rankings'):
            if provider == 'warcraftlogs_rankings' and 'encounterId' not in options:
                return None  # Catalog is metadata, not player sampling.
            limit = options.get('limit', 10)
            if type(limit) is not int or not 1 <= limit <= 10:
                return 'players (maximum 10)'
            group = provider + json.dumps({k:v for k,v in options.items() if k not in ('page','offset','limit')}, sort_keys=True)
            self.groups.add(group)
            if len(self.groups) > 3:
                return 'comparison groups (maximum 3)'
            page, offset = options.get('page', 0 if provider == 'raiderio_rankings' else 1), options.get('offset', 0)
            if type(page) is not int or type(offset) is not int:
                return 'ranking slice'
            slots = []
            for n in range(offset, offset + limit):
                slot = f'{group}:{page}:{n}'
                if slot in self.slots:
                    return 'ranking slice already sampled (reuse the existing receipt)'
                self.slots[slot] = 'slot:' + slot
                self.players.add(self.slots[slot])
                slots.append(slot)
            receipt.append((provider, slots))
        elif provider == 'raiderio':
            self.players.add(profile_key(target))
        elif provider == 'warcraftlogs_character':
            self.players.add(character_key(options.get('region'), options.get('realm'), options.get('name')))
        elif provider == 'warcraftlogs':
            scope, actor = report_scope(target)
            fight = scope.rsplit(':', 1)[-1]
            if not fight.isdigit() or int(fight) < 1:
                if 'startTime' in options or 'endTime' in options:
                    return 'fight scope (select a specific fight before reading events)'
                return None  # Report directory only; no event/table traversal.
            self.fights.add(scope)
            if len(self.fights) > 3:
                return 'fights (maximum 3)'
            if actor:
                actor_key = scope + ':' + actor
                self.players.add(self.report_actors.get(actor_key, 'actor:' + actor_key))
            if options.get('view', 'full') != 'overview':
                limit = options.get('limit', 300)
                pages = options.get('maxPages', 3) if options.get('view') == 'statistics' else 1
                if type(limit) is not int or type(pages) is not int or limit < 1 or pages < 1:
                    return 'events'
                self.events += limit * pages
                if self.events > 20000:
                    return 'events (maximum 20000 requested rows)'
        elif provider == 'public_web':
            if urlparse(target).scheme:
                self.pages.add(target.split('#')[0])
            else:
                # Search may fetch two pages. Reserve even on failure.
                self.web_searches += 1
            if len(self.pages) + self.web_searches * 2 > 5:
                return 'public sources (maximum 5)'
        if len(self.players) > 10:
            return 'players (maximum 10 across sources and pages)'
        return None

    def observe(self, receipt, result):
        for provider, slots in receipt or []:
            rows = result.get('rankings' if provider == 'warcraftlogs_rankings' else 'facts', [])
            for index, row in enumerate(rows):
                if index >= len(slots) or not isinstance(row, dict):
                    break
                if provider == 'raiderio_rankings':
                    character = row.get('character') or {}
                    if not character.get('url'):
                        continue
                    key = profile_key(character['url'])
                else:
                    server = row.get('server') or {}
                    if not row.get('name') or not server.get('name') or not row.get('reportUrl'):
                        continue
                    key = character_key(server.get('region'), server['name'], row['name'])
                    scope, _ = report_scope(row['reportUrl'])
                    self.report_players.setdefault(scope, {})[key] = row['name'].casefold()
                slot = slots[index]
                old = self.slots[slot]
                self.slots[slot] = key
                if old.startswith('slot:') and old not in self.slots.values():
                    self.players.discard(old)
                self.players.add(key)

        # Bind ranking identities only after the corresponding report exposes a
        # unique matching actor. A report URL alone never authorizes any actor.
        members = result.get('results', [result])
        for member in members:
            for fact in member.get('facts', []):
                if not isinstance(fact, dict):
                    continue
                scope = str(fact.get('reportCode', '')) + ':' + str(fact.get('fightId', ''))
                known = self.report_players.get(scope, {})
                actors = [a for a in fact.get('actors', []) if isinstance(a, dict) and type(a.get('id')) is int and isinstance(a.get('name'), str)]
                for actor in actors:
                    name = actor['name'].casefold()
                    matches = [key for key, value in known.items() if value == name]
                    if len(matches) == 1 and sum(a['name'].casefold() == name for a in actors) == 1:
                        alias = scope + ':' + str(actor['id'])
                        self.report_actors[alias] = matches[0]
                        self.players.discard('actor:' + alias)
