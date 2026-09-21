"""Bounded import lane. Only this lane executes the PoB engine."""
from uuid import uuid4
from server.app.poe2.engine import decode_build
from server.app.poe2.application import Poe2Error
from .urls import parse_character_url
from .repository import issue

class ImportWorker:
    def __init__(self,repository,engine,*,worker_id=None,collect=None,map=None,convert=None):
        self.repository=repository;self.engine=engine
        self.worker_id=worker_id or f'poe2-import-{uuid4()}'
        self.collect=collect;self.map=map;self.convert=convert

    def run_once(self):
        row=self.repository.claim(self.worker_id)
        if row is None:return False
        try:
            xml=row.source_xml
            provenance={'provider':row.provider,'sourceRelation':row.source_relation} if xml else None
            issues=[]
            if xml is None:
                if row.provider=='ninja':
                    self.repository.complete(row.id,self.worker_id,row.attempt,{'status':'needs_input','next_action':'supply_pob'})
                    return True
                if self.collect is None or self.map is None or self.convert is None:
                    self.repository.complete(row.id,self.worker_id,row.attempt,{'status':'blocked','issues':issue('SOURCE_UNAVAILABLE')})
                    return True
                snapshot=self.collect(parse_character_url(row.canonical_url,row.provider), owner_id=row.user_id)
                if not self.repository.stage(row.id,self.worker_id,row.attempt,'mapping'):return True
                mapped=self.map(snapshot)
                issues=[{'code':i.code,'path':i.path,'severity':i.severity.value,'message':i.message} for i in mapped.issues]
                provenance={'provider':row.provider,'sourceRelation':'collected','mappingVersion':mapped.mapping_version,
                            'sourceHash':mapped.source_hash,'gameDataVersion':mapped.game_data_version}
                allowed={'character','league','level','class','ascendancy','fetchedAt','sourceUpdatedAt','completeness'}
                preview={k:v for k,v in mapped.preview.items() if k in allowed}
                preview.update(provenance)
                if not self.repository.stage(row.id,self.worker_id,row.attempt,'mapping',
                    snapshot={'data':snapshot,'provenance':provenance},preview=preview):return True
                if mapped.character is None or any(i['severity'] in ('error','blocking') for i in issues):
                    self.repository.complete(row.id,self.worker_id,row.attempt,{'status':'needs_input','next_action':'supply_pob','issues':issues})
                    return True
                xml=self.convert(mapped.character)
            xml=decode_build(xml)
            if not self.repository.stage(row.id,self.worker_id,row.attempt,'validating'):return True
            result=self.engine.calculate(xml,{})
            result=dict(result)
            result['sourceProvenance']=provenance
            result['summary']={**result.get('summary',{}),'sourceProvenance':provenance}
            self.repository.complete(row.id,self.worker_id,row.attempt,{'status':'ready','issues':issues},xml=xml,result=result)
        except (TimeoutError,ConnectionError):
            self.repository.complete(row.id,self.worker_id,row.attempt,{'status':'queued','issues':issue('POE2_IMPORT_INFRASTRUCTURE_FAILED')})
        except (ValueError,Poe2Error) as error:
            code=str(error)
            if code not in ('SOURCE_UNAVAILABLE','AUTH_REQUIRED','RATE_LIMITED','INCOMPLETE'):
                code='POE2_IMPORT_VALIDATION_FAILED'
            self.repository.complete(row.id,self.worker_id,row.attempt,{'status':'blocked','issues':issue(code)})
        except RuntimeError as error:
            retryable=str(error) in ('POE2_ENGINE_BUSY','POE2_ENGINE_TIMEOUT')
            code=str(error) if str(error) in ('SOURCE_UNAVAILABLE','AUTH_REQUIRED','RATE_LIMITED','INCOMPLETE') else 'POE2_IMPORT_ENGINE_FAILED'
            self.repository.complete(row.id,self.worker_id,row.attempt,{'status':'queued' if retryable else 'blocked','issues':issue(code)})
        except Exception:
            self.repository.complete(row.id,self.worker_id,row.attempt,{'status':'failed','issues':issue('POE2_IMPORT_FAILED')})
        return True
