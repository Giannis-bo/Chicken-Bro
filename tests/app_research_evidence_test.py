from server.app.chickenbro.research_evidence import project_evidence
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

    def test_three_healing_tables_preserve_three_prior_stat_records(self):
        rows=[]
        for i in range(3):
            fact={'reportCode':'A','fightId':1,'sourceId':i+1,'view':'healing','healing':{'complete':True,'totals':{'raw':100,'effective':60},'entries':[{'guid':j,'name':'Spell','total':100,'hitdetails':[{'type':'Crit','total':100,'extra':'x'*200}]*8,'subentries':[{'total':100,'extra':'x'*200}]*16} for j in range(30)]}}
            rows.append(('r','c',{'status':'verified','facts':[fact]},'now'))
        for i in range(3):
            rows.append(('r','c',{'status':'verified','facts':[{'reportCode':'A','fightId':1,'sourceId':i+1,'view':'overview','players':[{'id':i+1,'combatantInfo':{'stats':{'Crit':622+i}}}]}]},'before'))
        result=project_evidence(rows)
        self.assertEqual(len(result['facts']),6)
        self.assertEqual(sum(bool(f['players']) for f in result['facts']),3)
        self.assertNotIn('hitdetails',result['facts'][0]['healing']['entries'][0])
