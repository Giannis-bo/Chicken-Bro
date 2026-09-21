import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4
from server.app.identity.domain import Principal
from server.app.poe2.application import Poe2Error
from server.app.poe2.tools import Poe2ToolGateway, Poe2ToolUnauthorized
from server.app.poe2.imports.application import ImportApplication
from server.app.poe2.imports.domain import ImportPacket, ImportStatus, SourceProvider
from server import chickenbro_native_mcp as mcp

class CharacterToolsTest(unittest.TestCase):
    def test_dispatch_all_actions_with_trusted_owner_and_strict_arguments(self):
        app=Mock(); owner=Principal(uuid4(),'web_cookie'); import_id=uuid4()
        packet=ImportPacket(import_id,ImportStatus.NEEDS_INPUT,SourceProvider.NINJA,None,(), 'supply_pob',None,None,0,datetime.now(timezone.utc))
        for name in ('create','read','supply_source','retry','cancel'):getattr(app,name).return_value=packet
        gateway=Poe2ToolGateway(object(),import_application=app)
        token=gateway.issue_capability(SimpleNamespace(game='poe2',principal=owner))
        cases=[('character_create',{'provider':'ninja','url':'https://poe.ninja/poe2/profile/a/b/character/c','idempotencyKey':'key'},'create'),
            ('character_get',{'importId':str(import_id)},'read'),
            ('character_source',{'importId':str(import_id),'source':'<PathOfBuilding2/>','idempotencyKey':'key'},'supply_source'),
            ('character_retry',{'importId':str(import_id),'idempotencyKey':'key'},'retry'),
            ('character_cancel',{'importId':str(import_id)},'cancel')]
        for operation,args,method in cases:
            self.assertEqual(gateway.execute(token,operation,args)['id'],str(import_id))
            self.assertEqual(getattr(app,method).call_args.args[0],owner)
            with self.assertRaises(ValueError):gateway.execute(token,operation,{**args,'ownerId':str(uuid4())})
        gateway.revoke(token)
        with self.assertRaises(Poe2ToolUnauthorized):gateway.execute(token,'character_get',{'importId':str(import_id)})
        with self.assertRaises(ValueError):gateway.issue_capability(SimpleNamespace(game='wow',principal=owner))

    def test_other_owner_read_uses_application_404(self):
        repo=Mock();repo.read.return_value=None
        gateway=Poe2ToolGateway(object(),import_application=ImportApplication(repo))
        other=Principal(uuid4(),'web_cookie');token=gateway.issue_capability(SimpleNamespace(game='poe2',principal=other));import_id=uuid4()
        with self.assertRaises(Poe2Error) as caught:gateway.execute(token,'character_get',{'importId':str(import_id)})
        self.assertEqual(caught.exception.status,404);repo.read.assert_called_once_with(other.user_id,import_id)

    def test_mcp_schemas_match_capability_and_wow_cannot_dispatch(self):
        definitions={x['name']:x for x in mcp.POE2_TOOL_DEFINITIONS}
        self.assertEqual(set(mcp.POE2_OPERATIONS.values()),Poe2ToolGateway.OPERATIONS)
        for name,operation in mcp.POE2_OPERATIONS.items():
            if not operation.startswith('character_'):continue
            self.assertFalse(definitions[name]['inputSchema']['additionalProperties'])
            self.assertNotIn('ownerId',definitions[name]['inputSchema']['properties'])
            args={'importId':str(uuid4())}
            if name.endswith('_source'):args.update(source='<PathOfBuilding2/>',idempotencyKey='key')
            request={'id':1,'method':'tools/call','params':{'name':name,'arguments':args}}
            with patch.object(mcp,'query_poe2_gateway',return_value={'status':'needs_input'}) as query:
                denied=mcp.handle_rpc_request(request,game='wow');self.assertTrue(denied['result']['isError']);query.assert_not_called()
                mcp.handle_rpc_request(request,game='poe2');query.assert_called_once_with(operation,args)
