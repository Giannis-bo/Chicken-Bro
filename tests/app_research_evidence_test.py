import unittest,json
class EvidenceTest(unittest.TestCase):
    def test_projection_recovers_actor_stats_without_event_dump(self):
        from server.app.chickenbro.research_evidence import project_evidence
        rows=[('run','call',{'status':'verified','facts':[{'reportCode':'AAAAAAAAAAAAAAAA','fightId':'1','sourceId':'7','fight':{'kill':True},'view':'overview','events':[{'timestamp':1}]*1000,'players':[{'id':7,'name':'Player','region':'US','server':'Realm','combatantInfo':{'stats':{'Crit':{'min':622,'max':622}},'gear':[{'id':1,'slot':0,'itemLevel':100}], 'talents':[{'id':2}]}}]}],'evidence':[{'sourceUrl':'https://www.warcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=7'}]},'2026-09-11')]
        out=project_evidence(rows)
        self.assertEqual(out['facts'][0]['players'][0]['combatantInfo']['stats']['Crit']['min'],622)
        self.assertNotIn('events',out['facts'][0]);self.assertLess(len(json.dumps(out)),10000)
    def test_projection_does_not_turn_failed_or_partial_data_into_verified(self):
        from server.app.chickenbro.research_evidence import project_evidence
        out=project_evidence([('r','c',{'status':'blocked','facts':[{'reportCode':'A','players':[{'secret':'bad'}]}]},'today')])
        self.assertEqual(out['facts'],[])
