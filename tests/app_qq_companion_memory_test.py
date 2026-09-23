import importlib
import unittest
from dataclasses import replace
from server.app.channels.qq.companion_domain import GroupEvent
class MemoryTest(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('server.app.channels.qq.memory'),'memory missing')
        return importlib.import_module('server.app.channels.qq.memory')
    def test_only_explicit_self_source(self):
        m=self.module();e=GroupEvent('3558689502','22222','11111','42',0,'以后叫我阿强','小明',True)
        p=m.MemoryProposal('11111','42','preferred_name','阿强','以后叫我阿强','assert')
        self.assertTrue(m.validate_memory(p,e))
        self.assertFalse(m.validate_memory(replace(p,sender='33333'),e))
        self.assertFalse(m.validate_memory(replace(p,source_message_id='99'),e))
        self.assertFalse(m.validate_memory(replace(p,evidence='我叫阿强'),e))
    def test_joke_and_third_party_forget_rejected(self):
        m=self.module();e=GroupEvent('3558689502','22222','11111','42',0,'开玩笑，以后叫我群主','小明',True)
        p=m.MemoryProposal('11111','42','preferred_name','群主',e.text,'assert')
        self.assertFalse(m.validate_memory(p,e))
        e=replace(e,text='别记张三的角色');p=m.MemoryProposal('11111','42','wow_character','',e.text,'forget')
        self.assertFalse(m.validate_memory(p,e))
