import base64
import unittest
import zlib


class Poe2InputTests(unittest.TestCase):
    def decoder(self):
        from server.app.poe2.engine import decode_build
        return decode_build

    def test_share_code_restores_xml_without_changing_build(self):
        xml = '<PathOfBuilding2><Build level="90" className="Monk"/></PathOfBuilding2>'
        code = base64.urlsafe_b64encode(zlib.compress(xml.encode())).decode().rstrip('=')
        self.assertEqual(self.decoder()(code), xml)

    def test_rejects_url_and_non_build_xml(self):
        for value in ('https://example.com/build', '<root/>', '<PathOfBuilding2/>junk',
                      '<PathOfBuilding><Build level="90"/></PathOfBuilding>'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.decoder()(value)

    def test_entity_and_oversized_expansion_rejected(self):
        for xml in ('<!DOCTYPE x [<!ENTITY foo SYSTEM "file:///etc/passwd">]><PathOfBuilding>&foo;</PathOfBuilding>',
                    '<PathOfBuilding>' + 'x' * 2_100_000 + '</PathOfBuilding>'):
            code = base64.urlsafe_b64encode(zlib.compress(xml.encode())).decode()
            with self.assertRaises(ValueError):
                self.decoder()(code)

    def test_safe_changes_do_not_accept_paths_code_or_arbitrary_config(self):
        from server.app.poe2.engine import validate_changes
        for changes in ({'lua': 'os.execute("x")'}, {'items': [{'slot': '../x', 'text': 'x'}]},
                        {'config': {'customMods': '100000% more Damage'}}, {'level': 101}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_changes(changes)

    def test_crafting_link_encodes_item_without_executable_url(self):
        from server.app.poe2.engine import crafting_import_link
        from urllib.parse import parse_qs, urlsplit
        item = 'Rarity: Rare\n测试 & Sword\n--------\n+50 to maximum Life'
        link = crafting_import_link(item)
        url = urlsplit(link)
        self.assertEqual(url.scheme, 'https')
        self.assertEqual(url.netloc, 'beta.craftofexile.com')
        self.assertEqual(parse_qs(url.query), {'game': ['poe2'], 'eimport': [item]})


if __name__ == '__main__':
    unittest.main()
