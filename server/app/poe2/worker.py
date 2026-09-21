import re
from uuid import uuid4

from server.app.poe2.application import validate_result


class Poe2Worker:
    def __init__(self, repository, engine, worker_id: str | None = None):
        self.repository=repository; self.engine=engine
        self.worker_id=(worker_id or 'poe2-'+str(uuid4()))[:128]

    def run_once(self) -> bool:
        job=self.repository.claim_next(self.worker_id)
        if job is None:return False
        try:
            build=self.repository.get_build(job.user_id,job.build_id)
            if build is None:raise RuntimeError('POE2_BUILD_NOT_FOUND')
            result=self.engine.calculate(build.source_xml,dict(job.changes))
            validate_result(result)
            if result.get('inputSha256') != build.input_sha256:
                raise RuntimeError('POE2_RESULT_BASELINE_MISMATCH')
            self.repository.complete(job.id,self.worker_id,result)
        except Exception as exc:
            code=str(exc)
            code=code if re.fullmatch(r'POE2_[A-Z0-9_]{1,80}',code) else 'POE2_CALCULATION_FAILED'
            self.repository.fail(job.id,self.worker_id,code)
        return True
