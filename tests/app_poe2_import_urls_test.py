import unittest
from datetime import datetime, timezone
from uuid import uuid4

from server.app.poe2.imports.domain import (
    ImportPacket,
    ImportStatus,
    Issue,
    IssueSeverity,
    SourceProvider,
)
from server.app.poe2.imports.urls import parse_character_url


class Poe2CharacterUrlTest(unittest.TestCase):
    def test_ninja_unicode_identity_and_canonical_encoding(self):
        ref = parse_character_url(
            " https://poe.ninja/poe2/profile/wuba-4006/forbiddenrites/character/玩個那個破大錘 \n",
            "ninja",
        )
        self.assertEqual(ref.provider, "ninja")
        self.assertEqual(ref.account, "wuba-4006")
        self.assertEqual(ref.league, "forbiddenrites")
        self.assertEqual(ref.character, "玩個那個破大錘")
        self.assertIsNone(ref.share_id)
        self.assertEqual(
            ref.canonical_url,
            "https://poe.ninja/poe2/profile/wuba-4006/forbiddenrites/character/"
            "%E7%8E%A9%E5%80%8B%E9%82%A3%E5%80%8B%E7%A0%B4%E5%A4%A7%E9%8C%98",
        )

    def test_ninja_percent_encoded_unicode_is_decoded_once(self):
        ref = parse_character_url(
            "https://poe.ninja/poe2/profile/%E7%8E%A9%E5%AE%B6/league/character/%E8%A7%92%E8%89%B2",
            "ninja",
        )
        self.assertEqual((ref.account, ref.character), ("玩家", "角色"))

    def test_wegame_share_fragment_is_the_only_identity(self):
        ref = parse_character_url(
            "https://www.wegame.com.cn/helper/poe2/#/share/Az_09-token",
            "wegame",
        )
        self.assertEqual(ref.provider, "wegame")
        self.assertEqual(ref.share_id, "Az_09-token")
        self.assertIsNone(ref.account)
        self.assertIsNone(ref.league)
        self.assertIsNone(ref.character)
        self.assertEqual(
            ref.canonical_url,
            "https://www.wegame.com.cn/helper/poe2/#/share/Az_09-token",
        )

    def test_provider_must_match_the_selected_entry(self):
        with self.assertRaisesRegex(ValueError, "POE2_SOURCE_PROVIDER_MISMATCH"):
            parse_character_url(
                "https://poe.ninja/poe2/profile/a/b/character/c", "wegame"
            )

    def test_rejects_deceptive_hosts_credentials_ports_queries_and_http(self):
        invalid = (
            "https://poe.ninja.evil.example/poe2/profile/a/b/character/c",
            "https://poe.ninja@evil.example/poe2/profile/a/b/character/c",
            "https://user:pass@poe.ninja/poe2/profile/a/b/character/c",
            "https://poe.ninja:444/poe2/profile/a/b/character/c",
            "https://poe.ninja/poe2/profile/a/b/character/c?q=1",
            "http://poe.ninja/poe2/profile/a/b/character/c",
        )
        for value in invalid:
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "POE2_SOURCE_URL_INVALID"
            ):
                parse_character_url(value, "ninja")

    def test_rejects_wrong_paths_fragments_and_double_encoding(self):
        invalid = (
            ("https://poe.ninja/poe2/profile/a/b/character/c#/share/token", "ninja"),
            ("https://poe.ninja/poe2/profile/a/b/character", "ninja"),
            ("https://poe.ninja/poe2/profile/a/b/character/c/extra", "ninja"),
            ("https://poe.ninja/poe2/profile/a/b/character/%252Fadmin", "ninja"),
            ("https://poe.ninja/poe2/profile/a/b/character/a%2Fb", "ninja"),
            ("https://www.wegame.com.cn/helper/poe2/share/token", "wegame"),
            ("https://www.wegame.com.cn/helper/poe2/#/wrong/token", "wegame"),
            ("https://www.wegame.com.cn/helper/poe2/#/share/a/b", "wegame"),
        )
        for value, provider in invalid:
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "POE2_SOURCE_URL_INVALID"
            ):
                parse_character_url(value, provider)

    def test_rejects_unknown_expected_provider(self):
        with self.assertRaisesRegex(ValueError, "POE2_SOURCE_PROVIDER_INVALID"):
            parse_character_url(
                "https://poe.ninja/poe2/profile/a/b/character/c", "other"
            )


class Poe2ImportPacketTest(unittest.TestCase):
    def packet(self, **changes):
        values = {
            "id": uuid4(),
            "status": ImportStatus.NEEDS_INPUT,
            "provider": SourceProvider.NINJA,
            "preview": {"character": "玩個那個破大錘", "level": 91},
            "issues": (
                Issue(
                    code="POB_REQUIRED",
                    path="source.pob",
                    severity=IssueSeverity.BLOCKING,
                    message="請貼上 PoB 代碼",
                ),
            ),
            "next_action": "supply_source",
            "build_id": None,
            "baseline_job_id": None,
            "attempt": 1,
            "updated_at": datetime(2026, 9, 20, tzinfo=timezone.utc),
        }
        values.update(changes)
        return ImportPacket(**values)

    def test_accepts_needs_input_with_nullable_result_ids(self):
        packet = self.packet()
        self.assertEqual(packet.status, ImportStatus.NEEDS_INPUT)
        self.assertIsNone(packet.build_id)
        self.assertIsNone(packet.baseline_job_id)
        with self.assertRaises(TypeError):
            packet.preview["level"] = 92

    def test_ready_requires_both_build_and_baseline_job_ids(self):
        with self.assertRaisesRegex(ValueError, "POE2_IMPORT_READY_RESULT_REQUIRED"):
            self.packet(status=ImportStatus.READY)
        with self.assertRaisesRegex(ValueError, "POE2_IMPORT_READY_RESULT_REQUIRED"):
            self.packet(status=ImportStatus.READY, build_id=uuid4())
        with self.assertRaisesRegex(ValueError, "POE2_IMPORT_READY_RESULT_REQUIRED"):
            self.packet(status=ImportStatus.READY, baseline_job_id=uuid4())

        packet = self.packet(
            status=ImportStatus.READY,
            build_id=uuid4(),
            baseline_job_id=uuid4(),
            next_action=None,
        )
        self.assertEqual(packet.status, ImportStatus.READY)

    def test_rejects_invalid_packet_members(self):
        invalid_changes = (
            {"provider": "ninja"},
            {"status": "needs_input"},
            {"issues": ({"code": "POB_REQUIRED"},)},
            {"attempt": -1},
            {"updated_at": datetime(2026, 9, 20)},
        )
        for changes in invalid_changes:
            with self.subTest(changes=changes), self.assertRaisesRegex(
                (TypeError, ValueError), "POE2_IMPORT_PACKET_INVALID"
            ):
                self.packet(**changes)


if __name__ == "__main__":
    unittest.main()
