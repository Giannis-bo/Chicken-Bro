from server.app.chickenbro.wcl_healing import project_healing
import unittest
from unittest.mock import patch
from server.app.chickenbro import wcl_source

class HealingTest(unittest.TestCase):
    def test_compatibility_maps_old_overview_healing_to_aggregate(self):
        self.assertEqual(wcl_source.validate_wcl_options({'view':'overview','dataType':'Healing'}),{'view':'healing'})
    def test_aggregate_pairs_totals_without_double_counting_children(self):
        from server.app.chickenbro.wcl_healing import project_healing
        effective={'data':{'totalTime':10000,'entries':[{'guid':1,'name':'Spell','total':60,'subentries':[{'guid':2,'total':60}]}]}}
        raw={'data':{'totalTime':10000,'entries':[{'guid':1,'name':'Spell','total':100,'overheal':40,'subentries':[{'guid':2,'total':100}]}]}}
        result=project_healing(effective,raw)
        self.assertTrue(result['complete']);self.assertEqual(result['totals'],{'effective':60,'raw':100,'overheal':40,'grossEffective':60,'grossRaw':100,'signedAdjustments':{'effective':0,'raw':0},'effectiveHps':6.0,'rawHps':10.0})
    def test_missing_or_different_aggregate_coverage_is_not_complete(self):
        from server.app.chickenbro.wcl_healing import project_healing
        self.assertFalse(project_healing({}, {})['complete'])
        self.assertIsNone(project_healing({}, {})['totals'])
    def test_healing_read_has_no_events_and_reaches_gateway_fact(self):
        from server.app.chickenbro.source_gateway import ServerConfiguredSourceQuery
        report={'title':'Report','fights':[{'id':1,'name':'Boss','startTime':10,'endTime':1010,'kill':True}],
          'effectiveHealing':{'data':{'totalTime':1000,'entries':[{'guid':1,'total':60}]}},
          'rawHealing':{'data':{'totalTime':1000,'entries':[{'guid':1,'total':100}]}}}
        with patch.object(wcl_source,'_graphql',return_value={'reportData':{'report':report}}) as query, patch.object(wcl_source,'configured_warcraftlogs_credentials_state',return_value={'configured':True,'mode':'v2_oauth','api':'v2'}):
            result=ServerConfiguredSourceQuery().query('warcraftlogs','https://www.warcraftcraftlogs.com/reports/AAAAAAAAAAAAAAAA?fight=1&source=2'.replace('warcraftcraft','warcraft'),{'view':'healing'})
        self.assertEqual(result['facts'][0]['healing']['totals']['raw'],100)
        self.assertNotIn('events(',query.call_args.args[0])

class InvalidHealingPairsTest(unittest.TestCase):
    def test_duplicate_raw_and_per_spell_underflow_are_incomplete(self):
        effective={'data':{'totalTime':1000,'entries':[{'guid':1,'name':'a','total':10},{'guid':2,'name':'b','total':20}]}}
        for rows in [[{'guid':1,'name':'a','total':10},{'guid':2,'name':'b','total':20},{'guid':2,'name':'b','total':20}], [{'guid':1,'name':'a','total':9},{'guid':2,'name':'b','total':21}]]:
            result=project_healing(effective,{'data':{'totalTime':1000,'entries':rows}})
            self.assertFalse(result['complete']);self.assertIsNone(result['totals'])

    def test_signed_upstream_adjustments_are_not_overheal(self):
        def table(heal,adjustment):return {'data':{'totalTime':1000,'entries':[{'guid':1,'name':'Heal','total':heal},{'guid':2,'name':'Adjustment','total':adjustment}]}}
        result=project_healing(table(100,-20),table(150,-10))
        self.assertTrue(result['complete'])
        self.assertEqual(result['totals']['effective'],80)
        self.assertEqual(result['totals']['raw'],140)
        self.assertEqual(result['totals']['overheal'],50)
        self.assertEqual(result['totals']['signedAdjustments'],{'effective':-20,'raw':-10})
