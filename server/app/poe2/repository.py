import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from server.app.poe2.domain import Poe2Build, Poe2Job, Poe2JobStatus


def _v(row: Any, key: str, index: int):
    return row[key] if isinstance(row, Mapping) else row[index]


def _json(value):
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class IdempotencyConflict(Exception):
    pass


class LeaseLost(Exception):
    pass


class PostgresPoe2Repository:
    def __init__(self, connection_factory: Callable[[], Any]):
        self._connect = connection_factory

    def create_build(self, build: Poe2Build, *, baseline: Poe2Job | None = None) -> Poe2Build:
        if baseline is not None and (baseline.build_id != build.id or baseline.user_id != build.user_id
                or baseline.status != Poe2JobStatus.SUCCEEDED or baseline.changes or baseline.result is None):
            raise ValueError('POE2_IMPORT_BASELINE_INVALID')
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO poe2.builds
                    (id,user_id,title,source_xml,game_version,league,input_sha256,engine_version,export_code,summary_json,created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                    (build.id,build.user_id,build.title,build.source_xml,build.game_version,build.league,
                     build.input_sha256,build.engine_version,build.export_code,_json(build.summary),build.created_at))
                if baseline is not None:
                    cur.execute("""INSERT INTO poe2.jobs
                        (id,user_id,build_id,idempotency_key,request_hash,changes_json,status,result_json,
                         public_error_code,attempt_count,lease_owner,lease_expires_at,created_at,updated_at)
                        VALUES (%s,%s,%s,%s,%s,'{}'::jsonb,'succeeded',%s::jsonb,'',0,'',NULL,%s,%s)""",
                        (baseline.id,build.user_id,build.id,baseline.idempotency_key,baseline.request_hash,
                         _json(baseline.result),baseline.created_at,baseline.updated_at))
        return build

    def get_build(self, user_id: UUID, build_id: UUID) -> Poe2Build | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT id,user_id,title,source_xml,game_version,league,input_sha256,
                    engine_version,export_code,summary_json,created_at FROM poe2.builds
                    WHERE user_id=%s AND id=%s AND deleted_at IS NULL""", (user_id,build_id))
                row=cur.fetchone()
        return self._build(row) if row else None

    def list_builds(self, user_id: UUID, limit: int = 50):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT id,user_id,title,source_xml,game_version,league,input_sha256,
                    engine_version,export_code,summary_json,created_at FROM poe2.builds
                    WHERE user_id=%s AND deleted_at IS NULL ORDER BY created_at DESC,id DESC LIMIT %s""",(user_id,min(max(limit,1),100)))
                rows=cur.fetchall()
        return [self._build(row) for row in rows]

    def delete_build(self, user_id: UUID, build_id: UUID) -> bool:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE poe2.builds SET deleted_at=COALESCE(deleted_at,now())
                    WHERE user_id=%s AND id=%s RETURNING id""", (user_id,build_id))
                return cur.fetchone() is not None

    def reusable_job(self, user_id, build_id, changes, engine_version, request_hash=''):
        with self._connect() as conn:
            with conn.cursor() as cur:
                return self._reusable_job(cur, user_id, build_id, changes, engine_version, request_hash)

    def _reusable_job(self, cur, user_id, build_id, changes, engine_version, request_hash):
        cur.execute("""SELECT id,user_id,build_id,idempotency_key,request_hash,changes_json,status,
            result_json,public_error_code,attempt_count,lease_owner,lease_expires_at,created_at,updated_at
            FROM poe2.jobs WHERE user_id=%s AND build_id=%s AND changes_json=%s::jsonb
            AND EXISTS (SELECT 1 FROM poe2.builds b WHERE b.id=poe2.jobs.build_id AND b.deleted_at IS NULL)
            AND ((status='succeeded' AND result_json->>'engineVersion'=%s)
                OR (status IN ('queued','running') AND request_hash=%s))
            ORDER BY (status='succeeded') DESC,created_at DESC LIMIT 1""",
            (user_id,build_id,_json(changes),engine_version,request_hash))
        row=cur.fetchone()
        return self._job(row) if row else None

    def create_job(self, job: Poe2Job, *, reuse_engine=None, admit=None) -> Poe2Job:
        with self._connect() as conn:
            with conn.cursor() as cur:
                if reuse_engine is not None:
                    # Serialize matching submissions before reserving research budget.
                    cur.execute('SELECT id FROM poe2.builds WHERE id=%s AND user_id=%s AND deleted_at IS NULL FOR UPDATE',
                                (job.build_id,job.user_id))
                    if cur.fetchone() is None:raise KeyError('POE2_BUILD_NOT_FOUND')
                    cur.execute('''SELECT id,user_id,build_id,idempotency_key,request_hash,changes_json,status,
                        result_json,public_error_code,attempt_count,lease_owner,lease_expires_at,created_at,updated_at
                        FROM poe2.jobs WHERE user_id=%s AND idempotency_key=%s''',
                                (job.user_id,job.idempotency_key))
                    existing=cur.fetchone()
                    if existing is not None:
                        existing=self._job(existing)
                        if existing.request_hash != job.request_hash:raise IdempotencyConflict()
                        return existing
                    reused=self._reusable_job(cur,job.user_id,job.build_id,job.changes,reuse_engine,job.request_hash)
                    if reused is not None:return reused
                    # A failed request with the same key is an idempotent read, not a new attempt.
                    if admit is not None:admit(cur)
                cur.execute("""INSERT INTO poe2.jobs
                    (id,user_id,build_id,idempotency_key,request_hash,changes_json,status,result_json,
                     public_error_code,attempt_count,lease_owner,lease_expires_at,created_at,updated_at)
                    SELECT %s,%s,b.id,%s,%s,%s::jsonb,%s,NULL,'',0,'',NULL,%s,%s
                    FROM poe2.builds b WHERE b.id=%s AND b.user_id=%s AND b.deleted_at IS NULL
                    ON CONFLICT (user_id,idempotency_key) DO NOTHING RETURNING id""",
                    (job.id,job.user_id,job.idempotency_key,job.request_hash,_json(job.changes),job.status.value,
                     job.created_at,job.updated_at,job.build_id,job.user_id))
                inserted=cur.fetchone()
                if inserted is None:
                    cur.execute("""SELECT id,user_id,build_id,idempotency_key,request_hash,changes_json,status,
                        result_json,public_error_code,attempt_count,lease_owner,lease_expires_at,created_at,updated_at
                        FROM poe2.jobs WHERE user_id=%s AND idempotency_key=%s AND EXISTS
                        (SELECT 1 FROM poe2.builds b WHERE b.id=poe2.jobs.build_id AND b.deleted_at IS NULL) FOR SHARE""",
                        (job.user_id,job.idempotency_key))
                    existing=cur.fetchone()
                    if existing is None:
                        raise KeyError('POE2_BUILD_NOT_FOUND')
                    existing=self._job(existing)
                    if existing.request_hash != job.request_hash:
                        raise IdempotencyConflict()
                    return existing
        return job

    def get_job(self, user_id: UUID, job_id: UUID) -> Poe2Job | None:
        return self._get_job("user_id=%s AND id=%s AND EXISTS (SELECT 1 FROM poe2.builds b WHERE b.id=poe2.jobs.build_id AND b.deleted_at IS NULL)",(user_id,job_id))

    def get_job_internal(self, job_id: UUID) -> Poe2Job | None:
        return self._get_job("id=%s",(job_id,))

    def _get_job(self, where, params):
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT id,user_id,build_id,idempotency_key,request_hash,changes_json,status,
                    result_json,public_error_code,attempt_count,lease_owner,lease_expires_at,created_at,updated_at
                    FROM poe2.jobs WHERE """+where,params)
                row=cur.fetchone()
        return self._job(row) if row else None

    def list_jobs(self, user_id: UUID, build_id: UUID | None = None, limit: int = 50):
        with self._connect() as conn:
            with conn.cursor() as cur:
                query="""SELECT id,user_id,build_id,idempotency_key,request_hash,changes_json,status,
                    result_json,public_error_code,attempt_count,lease_owner,lease_expires_at,created_at,updated_at
                    FROM poe2.jobs WHERE user_id=%s AND EXISTS
                    (SELECT 1 FROM poe2.builds b WHERE b.id=poe2.jobs.build_id AND b.deleted_at IS NULL)"""
                params=[user_id]
                if build_id is not None:
                    query += " AND build_id=%s"; params.append(build_id)
                query += " ORDER BY created_at DESC,id DESC LIMIT %s"; params.append(min(max(limit,1),100))
                cur.execute(query,tuple(params)); rows=cur.fetchall()
        return [self._job(row) for row in rows]

    def claim_next(self, worker_id: str, now: datetime | None = None, lease_seconds: int = 60) -> Poe2Job | None:
        now=now or datetime.now(timezone.utc); expires=now+timedelta(seconds=lease_seconds)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE poe2.jobs SET status='failed',public_error_code='POE2_ATTEMPTS_EXHAUSTED',
                    lease_owner='',lease_expires_at=NULL,updated_at=%s
                    WHERE attempt_count >= 3 AND status IN ('queued','running')
                      AND (lease_expires_at IS NULL OR lease_expires_at <= %s)""",(now,now))
                cur.execute("""SELECT id FROM poe2.jobs
                    WHERE attempt_count < 3 AND (status='queued' OR (status='running' AND lease_expires_at <= %s))
                    ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1""",(now,))
                row=cur.fetchone()
                if not row:return None
                job_id=_v(row,'id',0)
                cur.execute("""UPDATE poe2.jobs SET status='running',attempt_count=attempt_count+1,
                    lease_owner=%s,lease_expires_at=%s,updated_at=%s WHERE id=%s
                    RETURNING id,user_id,build_id,idempotency_key,request_hash,changes_json,status,result_json,
                    public_error_code,attempt_count,lease_owner,lease_expires_at,created_at,updated_at""",
                    (worker_id,expires,now,job_id)); claimed=cur.fetchone()
        return self._job(claimed)

    def complete(self, job_id: UUID, worker_id: str, result: Mapping, now: datetime | None = None):
        return self._finish(job_id,worker_id,'succeeded',result,'',now)

    def fail(self, job_id: UUID, worker_id: str, error_code: str, now: datetime | None = None):
        return self._finish(job_id,worker_id,'failed',None,error_code,now)

    def _finish(self,job_id,worker_id,status,result,error_code,now):
        now=now or datetime.now(timezone.utc)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE poe2.jobs SET status=%s,result_json=%s::jsonb,public_error_code=%s,
                    lease_owner='',lease_expires_at=NULL,updated_at=%s
                    WHERE id=%s AND status='running' AND lease_owner=%s AND lease_expires_at>%s RETURNING id""",
                    (status,_json(result) if result is not None else None,error_code,now,job_id,worker_id,now))
                if cur.fetchone() is None: raise LeaseLost()

    @staticmethod
    def _build(r):
        summary=_v(r,'summary_json',9); summary=json.loads(summary) if isinstance(summary,str) else summary
        return Poe2Build(UUID(str(_v(r,'id',0))),UUID(str(_v(r,'user_id',1))),_v(r,'title',2),_v(r,'source_xml',3),
            _v(r,'game_version',4),_v(r,'league',5),_v(r,'input_sha256',6),_v(r,'engine_version',7),
            _v(r,'export_code',8),summary,_v(r,'created_at',10))

    @staticmethod
    def _job(r):
        changes=_v(r,'changes_json',5); result=_v(r,'result_json',7)
        if isinstance(changes,str):changes=json.loads(changes)
        if isinstance(result,str):result=json.loads(result)
        return Poe2Job(UUID(str(_v(r,'id',0))),UUID(str(_v(r,'user_id',1))),UUID(str(_v(r,'build_id',2))),
            _v(r,'idempotency_key',3),_v(r,'request_hash',4),changes,Poe2JobStatus(_v(r,'status',6)),result,
            _v(r,'public_error_code',8),int(_v(r,'attempt_count',9)),_v(r,'lease_owner',10),
            _v(r,'lease_expires_at',11),_v(r,'created_at',12),_v(r,'updated_at',13))
