"""POE2 business contracts; metrics always originate from a recorded engine job."""

import hashlib
import json
import math
import os
from datetime import datetime, timezone
from uuid import UUID, uuid4

from server.app.identity.domain import Principal
from server.app.poe2.domain import Poe2Build, Poe2Job, Poe2JobStatus
from server.app.poe2.engine import decode_build, validate_changes, crafting_import_link
from server.app.poe2.repository import IdempotencyConflict
from server.app.poe2.tree_translation import translate_tree
from server.app.poe2.skill_setup import skill_setup


class Poe2Error(ValueError):
    def __init__(self, code: str, status: int = 422):
        self.code = code
        self.status = status
        super().__init__(code)


def validate_result(result: dict) -> None:
    if (not isinstance(result, dict) or not isinstance(result.get('stats'), dict)
            or not result.get('inputSha256') or not result.get('exportCode')
            or not result.get('engineVersion') or result['engineVersion'] == 'unverified'):
        raise Poe2Error('POE2_RESULT_PROVENANCE_MISSING')
    stats = result['stats']
    if any(type(value) not in (float, int) or not math.isfinite(value) for value in stats.values()):
        raise Poe2Error('POE2_RESULT_METRICS_INVALID')
    if not any(stats.get(key, 0) > 0 for key in ('Life', 'EnergyShield')):
        raise Poe2Error('POE2_RESULT_METRICS_INVALID')


def compare_results(jobs: list[dict]) -> dict:
    if len(jobs) != 2 or any(job.get('status') != 'succeeded' for job in jobs):
        raise Poe2Error('POE2_COMPARISON_NOT_READY', 409)
    a, b = jobs
    left, right = a['result'], b['result']
    if (a['buildId'] != b['buildId'] or
            any(not left.get(key) or left.get(key) != right.get(key)
                for key in ('inputSha256', 'engineVersion'))):
        raise Poe2Error('POE2_COMPARISON_BASELINE_MISMATCH', 409)
    metrics = {}
    for key in sorted(left['stats'].keys() & right['stats'].keys()):
        baseline, candidate = left['stats'][key], right['stats'][key]
        if type(baseline) not in (int, float) or type(candidate) not in (int, float):
            continue
        if not math.isfinite(baseline) or not math.isfinite(candidate):
            continue
        delta = candidate - baseline
        metrics[key] = {'baseline': baseline, 'candidate': candidate, 'delta': delta,
                        'percent': delta / abs(baseline) * 100 if baseline else None}
    return {'metrics': metrics, 'baselineChanges': left.get('changes', {}),
            'candidateChanges': right.get('changes', {}), 'engineVersion': left['engineVersion'],
            'scope': 'configured_theoretical_calculation'}


class Poe2Application:
    def __init__(self, repository, engine):
        self.repository=repository
        self.engine=engine

    def import_build(self, principal: Principal, source: str, *, title: str = 'Imported build',
                     game_version: str = '', league: str = '') -> Poe2Build:
        if not isinstance(title,str) or not 1 <= len(title.strip()) <= 128:
            raise Poe2Error('POE2_TITLE_INVALID')
        xml=decode_build(source)
        result=self.engine.calculate(xml,{})
        validate_result(result)
        now=datetime.now(timezone.utc)
        build=Poe2Build(uuid4(),principal.user_id,title.strip(),xml,str(game_version or result.get('summary',{}).get('treeVersion') or 'unknown')[:64],str(league or '')[:64],
            result['inputSha256'],result['engineVersion'],result['exportCode'],result.get('summary') or {},now)
        request_hash=hashlib.sha256(json.dumps({'buildId':str(build.id),'changes':{}},sort_keys=True,
            separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        baseline=Poe2Job(uuid4(),principal.user_id,build.id,'import:'+str(build.id),request_hash,{},
            Poe2JobStatus.SUCCEEDED,result,'',0,'',None,now,now)
        return self.repository.create_build(build, baseline=baseline)

    def list_builds(self, principal: Principal, limit: int = 50):
        return self.repository.list_builds(principal.user_id,limit)

    def read_build(self, principal: Principal, build_id: UUID) -> Poe2Build:
        build=self.repository.get_build(principal.user_id,build_id)
        if build is None: raise Poe2Error('POE2_BUILD_NOT_FOUND',404)
        return build

    def delete_build(self, principal: Principal, build_id: UUID):
        if not self.repository.delete_build(principal.user_id, build_id):
            raise Poe2Error('POE2_BUILD_NOT_FOUND',404)
        return {'deleted': True}

    def baseline_job(self, principal: Principal, build_id: UUID):
        build = self.read_build(principal, build_id)
        return self.repository.reusable_job(principal.user_id,build_id,{},
            os.environ.get('POE2_ENGINE_VERSION') or build.engine_version)

    def submit_job(self, principal: Principal, build_id: UUID, changes: dict | None, idempotency_key: str,
                   *, reuse=False, admit=None) -> Poe2Job:
        build = self.read_build(principal, build_id)
        if not isinstance(idempotency_key,str) or not 1 <= len(idempotency_key) <= 128:
            raise Poe2Error('POE2_IDEMPOTENCY_KEY_INVALID')
        normalized=validate_changes(changes)
        version=os.environ.get('POE2_ENGINE_VERSION') or build.engine_version
        identity={'buildId':str(build_id),'changes':normalized}
        if reuse:identity['engineVersion']=version
        request_hash=hashlib.sha256(json.dumps(identity,sort_keys=True,
            separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        now=datetime.now(timezone.utc)
        job=Poe2Job(uuid4(),principal.user_id,build_id,idempotency_key,request_hash,normalized,
            Poe2JobStatus.QUEUED,None,'',0,'',None,now,now)
        try:
            if reuse:
                key=hashlib.sha256(json.dumps({'source':build.input_sha256,'engine':version,'changes':normalized},
                    sort_keys=True,separators=(',',':')).encode()).hexdigest()
                return self.repository.create_job(job,reuse_engine=version,admit=lambda cursor:admit(key,cursor) if admit else None)
            return self.repository.create_job(job)
        except IdempotencyConflict:raise Poe2Error('POE2_IDEMPOTENCY_CONFLICT',409) from None
        except KeyError:raise Poe2Error('POE2_BUILD_NOT_FOUND',404) from None

    def read_tree(self, principal: Principal, build_id: UUID, job_id: UUID | None = None):
        build = self.read_build(principal, build_id)
        source, version = build.source_xml, build.engine_version
        if job_id is not None:
            job = self.read_job(principal, job_id)
            if job.build_id != build_id:
                raise Poe2Error('POE2_JOB_NOT_FOUND', 404)
            if not job.result or not job.result.get('exportCode'):
                raise Poe2Error('POE2_TREE_NOT_READY', 409)
            source, version = job.result['exportCode'], job.result['engineVersion']
        try:
            tree = self.engine.tree(source)
        except RuntimeError as exc:
            code = str(exc)
            raise Poe2Error(code if code.startswith('POE2_') else 'POE2_ENGINE_FAILED', 503) from None
        if tree.get('engineVersion') != version or version == 'unverified':
            raise Poe2Error('POE2_TREE_VERSION_MISMATCH', 409)
        return {**translate_tree(tree), 'buildId': str(build.id), 'jobId': str(job_id) if job_id else None}

    def read_job(self, principal: Principal, job_id: UUID) -> Poe2Job:
        job=self.repository.get_job(principal.user_id,job_id)
        if job is None: raise Poe2Error('POE2_JOB_NOT_FOUND',404)
        return job

    def list_jobs(self, principal: Principal, build_id: UUID | None = None, limit: int = 50):
        if build_id is not None:self.read_build(principal,build_id)
        return self.repository.list_jobs(principal.user_id,build_id,limit)

    def compare(self, principal: Principal, job_ids: list[UUID]):
        if not isinstance(job_ids,list) or len(job_ids)!=2 or job_ids[0]==job_ids[1]:
            raise Poe2Error('POE2_COMPARISON_INVALID')
        return compare_results([job_packet(self.read_job(principal,j)) for j in job_ids])

    def export(self, principal: Principal, build_id: UUID):
        build=self.read_build(principal,build_id)
        return {'buildId':str(build.id),'exportCode':build.export_code,'inputSha256':build.input_sha256,
                'engineVersion':build.engine_version}

    def crafting_link(self, item_text: str):
        return {'url':crafting_import_link(item_text),'source':'item_text','verifiedProbability':False}


def build_packet(build: Poe2Build, *, include_source=False):
    packet={'id':str(build.id),'title':build.title,'gameVersion':build.game_version,'league':build.league,
        'sourceType':'pob2','inputSha256':build.input_sha256,'engineVersion':build.engine_version,
        'summary':dict(build.summary),'createdAt':build.created_at.isoformat()}
    if include_source:packet['source']=build.source_xml
    return packet


def job_packet(job: Poe2Job):
    result = dict(job.result) if job.result is not None else None
    if result is not None:
        setup = skill_setup(result.get('exportCode'))
        if setup is not None:
            result['skillSetup'] = setup
    return {'id':str(job.id),'buildId':str(job.build_id),'status':job.status.value,'changes':dict(job.changes),
        'errorCode':job.public_error_code or None,'createdAt':job.created_at.isoformat(),
        'updatedAt':job.updated_at.isoformat(),'result':result}
