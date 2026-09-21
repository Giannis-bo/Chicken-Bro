import unittest
from server.app.poe2.skill_setup import skill_setup


class SkillSetupTests(unittest.TestCase):
    def test_active_set_enabled_gems_and_sources(self):
        xml = '''<PathOfBuilding2><Build/><Skills activeSkillSet="2">
        <SkillSet id="1"><Skill enabled="true"><Gem nameSpec="Old"/></Skill></SkillSet>
        <SkillSet id="2">
        <Skill enabled="true"><Gem nameSpec="Bleed III" level="1" gemId="Metadata/Items/Gems/SupportGemBleed"/>
        <Gem nameSpec="Shield Wall" level="19" gemId="Metadata/Items/Gem/SkillGemShieldWall"/>
        <Gem nameSpec="Disabled" enabled="false"/><Gem nameSpec=""/></Skill>
        <Skill enabled="false"><Gem nameSpec="Inactive"/></Skill>
        <Skill enabled="true" source="Item:8:Private item" slot="Weapon 1 Swap"><Gem nameSpec="Spear Throw" level="1" gemId="Metadata/Items/Gem/SkillGemThrow"/></Skill>
        <Skill enabled="true" source="Tree:11641"><Gem nameSpec="Barrier" gemId="Metadata/Items/Gems/SkillGemBarrier"/></Skill>
        </SkillSet></Skills></PathOfBuilding2>'''
        result = skill_setup(xml)
        self.assertEqual(len(result), 3)
        self.assertEqual([g['name'] for g in result[0]['gems']], ['Bleed III', 'Shield Wall'])
        self.assertEqual([g['kind'] for g in result[0]['gems']], ['support', 'skill'])
        self.assertEqual(result[1]['source'], 'item')
        self.assertEqual(result[1]['slot'], 'Weapon 1 Swap')
        self.assertEqual(result[2]['source'], 'tree')
        self.assertNotIn('Private item', str(result))

    def test_invalid_or_missing_selection_is_not_guessed(self):
        self.assertIsNone(skill_setup('invalid'))
        self.assertIsNone(skill_setup('<PathOfBuilding2><Build/><Skills activeSkillSet="2"><SkillSet id="1"/></Skills></PathOfBuilding2>'))
        self.assertIsNone(skill_setup('<!DOCTYPE x><PathOfBuilding2><Build/></PathOfBuilding2>'))


if __name__ == '__main__': unittest.main()
