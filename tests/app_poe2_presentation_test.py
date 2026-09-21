import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from server.app.poe2.presentation import build_skills, presentation, glossary
from server.app.poe2.tools import Poe2ToolGateway


class PresentationTest(unittest.TestCase):
    def test_extracts_only_active_skill_set_and_preserves_levels_enabled_and_tiers(self):
        xml = '<PathOfBuilding2><Skills activeSkillSet="2"><SkillSet id="1"><Skill><Gem nameSpec="Wrong"/></Skill></SkillSet><SkillSet id="2"><Skill enabled="false" label="My group"><Gem nameSpec="Shield Wall" level="20" quality="10" enabled="true"/><Gem nameSpec="Unknown III" level="3" enabled="false"/></Skill></SkillSet></Skills></PathOfBuilding2>'
        groups = build_skills(xml)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['enabled'], 'false')
        self.assertEqual(groups[0]['gems'][0]['level'], '20')
        self.assertEqual(groups[0]['gems'][0]['quality'], '10')
        display = presentation({'summary': {'ascendancy': 'Gemling Legionnaire'}}, skills=groups)
        self.assertIn('盾墙', [term['zhCN'] for term in display['terms']])
        self.assertIn('古灵使徒斗士', [term['zhCN'] for term in display['terms']])
        self.assertEqual(display['unknown'], [{'kind': 'gem', 'en': 'Unknown III', 'status': '国服名称待核实'}])
        self.assertEqual(display['skills'][0]['gems'][1]['enabled'], 'false')

    def test_export_keeps_original_code_and_uses_owner_scoped_xml(self):
        owner = object()
        build_id = uuid4()
        class App:
            def read_build(self, principal, identifier):
                self_outer.assertIs(principal, owner)
                self_outer.assertEqual(identifier, build_id)
                return SimpleNamespace(source_xml='<PathOfBuilding2><Skills><Skill><Gem nameSpec="Shield Wall" level="20"/></Skill></Skills></PathOfBuilding2>')
            def export(self, principal, identifier):
                return {'buildId': str(identifier), 'exportCode': 'original-code'}
        self_outer = self
        gateway = Poe2ToolGateway(App())
        token = gateway.issue_capability(SimpleNamespace(game='poe2', principal=owner))
        result = gateway.execute(token, 'export', {'buildId': str(build_id)})
        self.assertEqual(result['exportCode'], 'original-code')
        self.assertEqual(result['presentation']['terms'][0]['zhCN'], '盾墙')

    def test_glossary_provenance_and_default_prompt_rules(self):
        data = glossary()
        self.assertEqual(len({(row['kind'], row['en']) for row in data['terms']}), len(data['terms']))
        self.assertTrue(all(row['sourceUrl'].startswith('https://poe2db.tw/cn/') for row in data['terms']))
        root = Path(__file__).resolve().parents[1] / 'server/app/chickenbro/agent'
        prompt = (root / 'POE2.md').read_text()
        self.assertIn('所有游戏术语默认使用国服简体名称', prompt)
        self.assertIn('国服名称待核实', prompt)
        self.assertNotIn('粘贴或上传完整文件', prompt)
        self.assertIn('国服简体官方名称', (root / 'AGENTS.md').read_text())
