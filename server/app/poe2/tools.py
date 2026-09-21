import hashlib
import json
import secrets
import threading
import time
from dataclasses import dataclass, field
from uuid import UUID

from server.app.poe2.application import build_packet, job_packet
from server.app.poe2.imports.application import ImportApplication, packet_json
from server.app.poe2.imports.repository import PostgresImportRepository
from server.app.poe2.presentation import build_skills, presentation


class Poe2ToolUnauthorized(Exception): pass


class _BudgetBlocked(Exception):
    def __init__(self, result):self.result=result


@dataclass
class _Capability:
    context: object
    expires_at: float
    evidence: list = field(default_factory=list)
    budget: object = None


class Poe2ToolGateway:
    OPERATIONS=frozenset({'import','list','get','calculate','compare','job_get','export','crafting_import_link',
        'character_create','character_get','character_source','character_retry','character_cancel'})
    def __init__(self, application, clock=None, *, import_application=None, research_budget=None, research_budget_factory=None):
        self.application=application; self.clock=clock or time.monotonic
        connect=getattr(getattr(application,'repository',None),'_connect',None)
        self.import_application=import_application or (ImportApplication(PostgresImportRepository(connect)) if connect else None)
        self.lock=threading.RLock(); self.tokens={}
        self.research_budget=research_budget; self.research_budget_factory=research_budget_factory

    def issue_capability(self, context):
        if getattr(context,'game',None) != 'poe2' or getattr(context,'principal',None) is None:
            raise ValueError('trusted POE2 context required')
        token=secrets.token_urlsafe(32)
        budget=self.research_budget_factory(context) if self.research_budget_factory else self.research_budget
        with self.lock:self.tokens[hashlib.sha256(token.encode()).hexdigest()]=_Capability(context,self.clock()+900,budget=budget)
        return token

    def revoke(self, token):
        with self.lock:self.tokens.pop(hashlib.sha256(str(token).encode()).hexdigest(),None)

    revoke_capability=revoke

    def _cap(self,token):
        with self.lock:cap=self.tokens.get(hashlib.sha256(str(token).encode()).hexdigest())
        if cap is None or self.clock() >= cap.expires_at:raise Poe2ToolUnauthorized()
        return cap

    def execute(self,token,operation,arguments):
        cap=self._cap(token)
        if operation not in self.OPERATIONS or not isinstance(arguments,dict):raise ValueError('invalid POE2 operation')
        p=cap.context.principal; a=self.application
        if operation.startswith('character_'):
            required={'character_create':{'provider','url','idempotencyKey'}, 'character_get':{'importId'},
                'character_source':{'importId','source','idempotencyKey'}, 'character_retry':{'importId','idempotencyKey'},
                'character_cancel':{'importId'}}[operation]
            if set(arguments)!=required or self.import_application is None:raise ValueError('invalid character import arguments')
            imports=self.import_application
            if operation=='character_create':result=imports.create(p,arguments['provider'],arguments['url'],arguments['idempotencyKey'])
            elif operation=='character_get':result=imports.read(p,UUID(arguments['importId']))
            elif operation=='character_source':result=imports.supply_source(p,UUID(arguments['importId']),arguments['source'],arguments['idempotencyKey'])
            elif operation=='character_retry':result=imports.retry(p,UUID(arguments['importId']),arguments['idempotencyKey'])
            else:result=imports.cancel(p,UUID(arguments['importId']))
            result=packet_json(result)
        elif operation=='import':
            result=build_packet(a.import_build(p,arguments.get('source'),title=arguments.get('title') or 'Imported build',
                game_version=arguments.get('patch') or arguments.get('gameVersion') or '',league=arguments.get('league') or ''))
        elif operation=='list':result={'items':[build_packet(x) for x in a.list_builds(p)]}
        elif operation=='get':
            build_id=UUID(arguments['buildId'])
            result=build_packet(a.read_build(p,build_id))
            baseline=a.baseline_job(p,build_id) if hasattr(a,'baseline_job') else None
            result.update(baselineJobId=str(baseline.id) if baseline else None)
        elif operation=='calculate':
            admitted=False
            def admit(key, cursor):
                nonlocal admitted
                if cap.budget is not None:
                    error=cap.budget.reserve_poe2(key,cursor=cursor)
                    if error:raise _BudgetBlocked(error)
                admitted=True
            try:
                result=job_packet(a.submit_job(p,UUID(arguments['buildId']),arguments.get('changes'),
                    arguments['idempotencyKey'],reuse=True,admit=admit))
                result['reused']=not admitted
            except _BudgetBlocked as blocked:
                result=blocked.result
        elif operation=='job_get':result=job_packet(a.read_job(p,UUID(arguments['jobId'])))
        elif operation=='compare':result=a.compare(p,[UUID(x) for x in arguments['jobIds']])
        elif operation=='export':
            result=a.export(p,UUID(arguments['buildId']))
            size=len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())
            if size > 170_000:
                result={'buildId':result['buildId'],'status':'blocked','errorCode':'POE2_EXPORT_TOO_LARGE',
                    'exportBytes':size,'limitations':['Use the authenticated build export API to download this large share code.']}
        else:result=a.crafting_link(arguments['itemText'])
        if operation in {'import', 'list', 'get', 'calculate', 'job_get', 'compare', 'export'}:
            skills = None
            if operation in {'get', 'export'}:
                skills = build_skills(a.read_build(p, UUID(arguments['buildId'])).source_xml)
            result = dict(result, presentation=presentation(result, skills=skills))
        if cap.budget is not None:
            result=dict(result,researchBudget=cap.budget.poe2_status())
        cap.evidence.append({'operation':operation,'result':result})
        if len(cap.evidence)>32:cap.evidence=cap.evidence[-32:]
        return result

    def answer_evidence(self,token):return {'poe2':list(self._cap(token).evidence)}
