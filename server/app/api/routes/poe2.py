from typing import Any
from uuid import UUID
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from server.app.api.dependencies import require_mutating_principal, require_principal, poe2_application
from server.app.api.errors import ApiProblem
from server.app.identity.domain import Principal
from server.app.poe2.application import Poe2Application, Poe2Error, build_packet, job_packet
from server.app.poe2.tools import Poe2ToolUnauthorized

router=APIRouter(prefix='/api/v2/poe2',tags=['poe2'])
internal_router=APIRouter()

class Strict(BaseModel):model_config=ConfigDict(extra='forbid')
class ImportBody(Strict):
    source:str
    title:str='Imported build'
    gameVersion:str=''
    league:str=''
class JobBody(Strict):
    buildId:UUID
    changes:dict[str,Any]|None=None
    idempotencyKey:str=Field(min_length=1,max_length=128)
class CompareBody(Strict):jobIds:list[UUID]
class CraftBody(Strict):itemText:str
class ToolBody(Strict):operation:str; arguments:dict[str,Any]

def _call(fn):
    try:return fn()
    except Poe2Error as e:raise ApiProblem(status_code=e.status,code=e.code,message=e.code) from None
    except ValueError as e:
        code=str(e) if str(e).startswith('POE2_') else 'POE2_REQUEST_INVALID'
        raise ApiProblem(status_code=422,code=code,message=code) from None

@router.post('/builds',status_code=201)
def import_build(body:ImportBody,p:Principal=Depends(require_mutating_principal),a:Poe2Application=Depends(poe2_application)):
    return _call(lambda:build_packet(a.import_build(p,body.source,title=body.title,game_version=body.gameVersion,league=body.league),include_source=True))
@router.get('/builds')
def list_builds(limit:int=Query(50,ge=1,le=100),p:Principal=Depends(require_principal),a:Poe2Application=Depends(poe2_application)):
    return {'items':[build_packet(x) for x in a.list_builds(p,limit)]}
@router.get('/builds/{build_id}')
def get_build(build_id:UUID,p:Principal=Depends(require_principal),a:Poe2Application=Depends(poe2_application)):
    return _call(lambda:build_packet(a.read_build(p,build_id),include_source=True))
@router.post('/builds/{build_id}/delete')
def delete_build(build_id:UUID,p:Principal=Depends(require_mutating_principal),a:Poe2Application=Depends(poe2_application)):
    return _call(lambda:a.delete_build(p,build_id))
@router.get('/builds/{build_id}/export')
def export(build_id:UUID,p:Principal=Depends(require_principal),a:Poe2Application=Depends(poe2_application)):
    return _call(lambda:a.export(p,build_id))
@router.get('/builds/{build_id}/tree')
def tree(build_id:UUID,response:Response,jobId:UUID|None=None,p:Principal=Depends(require_principal),a:Poe2Application=Depends(poe2_application)):
    response.headers['Cache-Control']='private, no-store'
    return _call(lambda:a.read_tree(p,build_id,jobId))
@router.post('/jobs',status_code=202)
def submit(body:JobBody,p:Principal=Depends(require_mutating_principal),a:Poe2Application=Depends(poe2_application)):
    return _call(lambda:job_packet(a.submit_job(p,body.buildId,body.changes,body.idempotencyKey)))
@router.get('/jobs')
def list_jobs(buildId:UUID|None=None,limit:int=Query(50,ge=1,le=100),p:Principal=Depends(require_principal),a:Poe2Application=Depends(poe2_application)):
    return _call(lambda:{'items':[job_packet(x) for x in a.list_jobs(p,buildId,limit)]})
@router.get('/jobs/{job_id}')
def get_job(job_id:UUID,p:Principal=Depends(require_principal),a:Poe2Application=Depends(poe2_application)):
    return _call(lambda:job_packet(a.read_job(p,job_id)))
@router.post('/compare')
def compare(body:CompareBody,p:Principal=Depends(require_mutating_principal),a:Poe2Application=Depends(poe2_application)):
    return _call(lambda:a.compare(p,body.jobIds))
@router.post('/crafting/import-link')
def craft(body:CraftBody,p:Principal=Depends(require_mutating_principal),a:Poe2Application=Depends(poe2_application)):
    return _call(lambda:a.crafting_link(body.itemText))

@internal_router.post('/api/v2/internal/chickenbro/poe2-tool')
def tool(body:ToolBody,request:Request,x_chickenbro_poe2_gateway:str=Header(default='')):
    try:return request.app.state.chickenbro_poe2_gateway.execute(x_chickenbro_poe2_gateway,body.operation,body.arguments)
    except Poe2ToolUnauthorized:
        raise ApiProblem(status_code=401,code='CHAT_EXECUTION_INACTIVE',message='capability unavailable') from None
    except (Poe2Error,ValueError,KeyError,TypeError) as e:
        code=e.code if isinstance(e,Poe2Error) else 'CHAT_TOOL_UNAVAILABLE'
        raise ApiProblem(status_code=422,code=code,message=code) from None


from server.app.api.dependencies import poe2_import_application
from server.app.poe2.imports.application import ImportApplication, packet_json

class CharacterImportBody(Strict):
    provider:str
    url:str=Field(max_length=4096)
    idempotencyKey:str=Field(min_length=1,max_length=128)
class CharacterSourceBody(Strict):
    source:str=Field(max_length=2000000)
    idempotencyKey:str=Field(min_length=1,max_length=128)
class CharacterRetryBody(Strict):
    idempotencyKey:str=Field(min_length=1,max_length=128)

@router.post('/imports',status_code=202)
def create_character_import(body:CharacterImportBody,p:Principal=Depends(require_mutating_principal),a:ImportApplication=Depends(poe2_import_application)):
    return _call(lambda:packet_json(a.create(p,body.provider,body.url,body.idempotencyKey)))

@router.get('/imports/{import_id}')
def read_character_import(import_id:UUID,p:Principal=Depends(require_principal),a:ImportApplication=Depends(poe2_import_application)):
    return _call(lambda:packet_json(a.read(p,import_id)))

@router.post('/imports/{import_id}/source',status_code=202)
def supply_character_source(import_id:UUID,body:CharacterSourceBody,p:Principal=Depends(require_mutating_principal),a:ImportApplication=Depends(poe2_import_application)):
    return _call(lambda:packet_json(a.supply_source(p,import_id,body.source,body.idempotencyKey)))

@router.post('/imports/{import_id}/retry',status_code=202)
def retry_character_import(import_id:UUID,body:CharacterRetryBody,p:Principal=Depends(require_mutating_principal),a:ImportApplication=Depends(poe2_import_application)):
    return _call(lambda:packet_json(a.retry(p,import_id,body.idempotencyKey)))

@router.post('/imports/{import_id}/cancel')
def cancel_character_import(import_id:UUID,p:Principal=Depends(require_mutating_principal),a:ImportApplication=Depends(poe2_import_application)):
    return _call(lambda:packet_json(a.cancel(p,import_id)))
