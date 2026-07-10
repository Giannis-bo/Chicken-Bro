#!/usr/bin/env python3
import json
import unittest


class PgGearReadModelSelectorsTest(unittest.TestCase):
    def test_build_websim_talent_authority_read_model_preserves_runtime_and_official_state(self):
        from server.pg_gear_read_model_selectors import build_websim_talent_authority_read_model

        payload = build_websim_talent_authority_read_model(
            "verified",
            {"seasonRevision": "midnight-1"},
            [{"id": "node-a"}, {"id": "node-b"}],
            {
                "checkedAt": "2026-07-10T01:00:00+00:00",
                "simc": {"build": "simc-dev", "traitEdgeSource": "simc-trait-data"},
            },
            schema_revision="talent-schema-v1",
        )

        self.assertEqual(
            payload,
            {
                "schemaRevision": "talent-schema-v1",
                "runtimeSource": "simc",
                "diffStatus": "verified",
                "checkedAt": "2026-07-10T01:00:00+00:00",
                "runtime": {
                    "status": "verified",
                    "source": "simc",
                    "simcBuild": "simc-dev",
                    "traitEdgeSource": "simc-trait-data",
                    "nodeCount": 2,
                },
                "official": {
                    "status": "pending_audit",
                    "revision": "midnight-1",
                    "source": "blizzard-game-data-api",
                },
            },
        )

        fallback_payload = build_websim_talent_authority_read_model(
            "fallback",
            {"revision": "legacy-revision"},
            None,
            {},
            schema_revision="talent-schema-v1",
            now="2026-07-10T02:00:00+00:00",
        )
        self.assertEqual(fallback_payload["runtimeSource"], "fallback")
        self.assertEqual(fallback_payload["diffStatus"], "pending_official_audit")
        self.assertEqual(fallback_payload["checkedAt"], "2026-07-10T02:00:00+00:00")
        self.assertEqual(fallback_payload["runtime"]["nodeCount"], 0)
        self.assertEqual(fallback_payload["official"]["revision"], "legacy-revision")

    def test_build_websim_loot_read_model_wraps_items_instances_and_season(self):
        from server.pg_gear_read_model_selectors import build_websim_loot_read_model

        payload = build_websim_loot_read_model(
            [{"id": "loot-a"}, {"id": "loot-b"}],
            [{"id": "instance-a"}],
            {"seasonId": "midnight-1", "dataStatus": "verified"},
            limit=1,
        )

        self.assertEqual(payload["items"], [{"id": "loot-a"}])
        self.assertEqual(payload["instances"], [{"id": "instance-a"}])
        self.assertEqual(payload["seasonId"], "midnight-1")
        self.assertEqual(payload["dataStatus"], "verified")

        legacy_slice_payload = build_websim_loot_read_model(
            [{"id": "loot-a"}, {"id": "loot-b"}],
            [],
            {"dataStatus": "verified"},
            limit=-1,
        )
        self.assertEqual(legacy_slice_payload["items"], [{"id": "loot-a"}])

        blocked_payload = build_websim_loot_read_model(
            None,
            None,
            {"dataStatus": "blocked", "errors": ["active season is not verified"]},
        )
        self.assertEqual(blocked_payload["items"], [])
        self.assertEqual(blocked_payload["instances"], [])
        self.assertEqual(blocked_payload["dataStatus"], "blocked")

    def test_build_websim_talent_import_template_read_model_maps_row(self):
        from server.pg_gear_read_model_selectors import build_websim_talent_import_template_read_model

        row = (
            "template-1",
            "mage",
            "frost",
            "frostfire",
            "mythic_plus",
            "Raider.IO Frostfire",
            "raiderio",
            "Raider.IO",
            "https://example.test/template",
            "CsbBAAAAAAAAAAAAAA",
            "synced",
            "verified",
            "12",
            "24",
            None,
            "2026-07-09T12:00:00+00:00",
        )

        self.assertEqual(
            build_websim_talent_import_template_read_model(row),
            {
                "id": "template-1",
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": "frostfire",
                "scenarioKey": "mythic_plus",
                "name": "Raider.IO Frostfire",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "sourceUrl": "https://example.test/template",
                "rawImportCode": "CsbBAAAAAAAAAAAAAA",
                "sourceStatus": "synced",
                "status": "verified",
                "sampleCount": 12,
                "maxKeyLevel": 24,
                "analysisWindow": "",
                "updatedAt": "2026-07-09T12:00:00+00:00",
                "canUseInSimc": True,
            },
        )
        self.assertIsNone(build_websim_talent_import_template_read_model(None))

    def test_build_admin_talent_records_read_model_filters_expired_templates(self):
        from server.pg_gear_read_model_selectors import build_admin_talent_records_read_model

        template_rows = [
            (
                "expired-template",
                "mage",
                "frost",
                "frostfire",
                "mythic_plus",
                "Expired template",
                "raiderio",
                "Raider.IO",
                "https://example.test/expired",
                "synced",
                "blocked",
                1,
                20,
                "old window",
                '{"errors":["expired"]}',
                "2026-07-01T00:00:00+00:00",
                "2026-07-02T00:00:00+00:00",
                "sig-expired",
                '[{"type":"raiderio"}]',
                "scan-expired",
            ),
            (
                "fresh-template",
                "mage",
                "frost",
                "frostfire",
                "mythic_plus",
                "Fresh template",
                "raiderio",
                "Raider.IO",
                "https://example.test/fresh",
                "synced",
                "verified",
                2,
                24,
                "fresh window",
                {"talentLoadout": "ok"},
                "2026-07-03T00:00:00+00:00",
                "2099-01-01T00:00:00+00:00",
                "sig-fresh",
                [{"type": "raiderio"}],
                "scan-fresh",
            ),
        ]
        tree_rows = [("mage", "frost", "110", "2026-07-03T01:00:00+00:00")]

        payload = build_admin_talent_records_read_model(
            template_rows,
            tree_rows,
            now="2026-07-03T00:00:00+00:00",
        )

        self.assertEqual([item["id"] for item in payload["communityTalentTemplates"]], ["fresh-template"])
        self.assertEqual(payload["communityTalentTemplates"][0]["payload"], {"talentLoadout": "ok"})
        self.assertEqual(payload["communityTalentTemplates"][0]["sourceRefs"], [{"type": "raiderio"}])
        self.assertEqual(payload["communityTalentTemplates"][0]["sampleCount"], 2)
        self.assertEqual(payload["communityTalentTemplates"][0]["maxKeyLevel"], 24)
        self.assertEqual(
            payload["talentTrees"],
            [{"classKey": "mage", "specKey": "frost", "nodeCount": 110, "updatedAt": "2026-07-03T01:00:00+00:00"}],
        )

    def test_build_websim_bootstrap_read_model_assembles_backend_owned_payload(self):
        from server.pg_gear_read_model_selectors import build_websim_bootstrap_read_model

        season_fields = {
            "locale": "zh_CN",
            "dataStatus": "verified",
            "seasonId": "midnight-1",
        }

        payload = build_websim_bootstrap_read_model(
            season_fields,
            locale_fallbacks=["zh_CN", "en_US"],
            classes=[{"key": "mage"}],
            gear_slots=[{"key": "head"}],
            scenarios=[{"key": "single"}],
            instances=[{"id": "dungeon-a"}],
            sync_state={"ok": True},
            default_selection={"classKey": "mage", "specKey": "arcane"},
            simcraft_version={"version": "simc-dev"},
        )

        self.assertEqual(payload["navTitle"], "WebSim")
        self.assertEqual(payload["title"], "SimC 构筑工坊")
        self.assertEqual(payload["region"], "us")
        self.assertEqual(payload["locale"], "zh_CN")
        self.assertEqual(payload["localeFallbacks"], ["zh_CN", "en_US"])
        self.assertEqual(payload["classes"], [{"key": "mage"}])
        self.assertEqual(payload["gearSlots"], [{"key": "head"}])
        self.assertEqual(payload["scenarios"], [{"key": "single"}])
        self.assertEqual(payload["instances"], [{"id": "dungeon-a"}])
        self.assertEqual(payload["syncState"], {"ok": True})
        self.assertEqual(payload["defaultSelection"], {"classKey": "mage", "specKey": "arcane"})
        self.assertEqual(payload["simcraftVersion"], {"version": "simc-dev"})
        self.assertEqual(payload["dataStatus"], "verified")
        self.assertEqual(payload["seasonId"], "midnight-1")

    def test_build_websim_default_selection_read_model_maps_row_and_fallback(self):
        from server.pg_gear_read_model_selectors import build_websim_default_selection_read_model

        self.assertEqual(
            build_websim_default_selection_read_model(("deathknight", "blood")),
            {"classKey": "deathknight", "specKey": "blood"},
        )
        self.assertEqual(
            build_websim_default_selection_read_model(None),
            {"classKey": "mage", "specKey": "arcane"},
        )

    def test_build_websim_profile_presets_read_model_maps_rows(self):
        from server.pg_gear_read_model_selectors import build_websim_profile_presets_read_model

        rows = [
            (
                "preset-arcane",
                "mage",
                "arcane",
                "Arcane Default",
                "mage=Arcane_Default",
                '{"source": "simc"}',
                "2026-07-09T12:00:00Z",
            ),
            (
                "preset-bad-payload",
                "mage",
                "fire",
                "Fire Default",
                "mage=Fire_Default",
                "{bad json",
                None,
            ),
        ]

        presets = build_websim_profile_presets_read_model(rows)

        self.assertEqual(
            presets,
            [
                {
                    "id": "preset-arcane",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "name": "Arcane Default",
                    "profile": "mage=Arcane_Default",
                    "payload": {"source": "simc"},
                    "updatedAt": "2026-07-09T12:00:00Z",
                },
                {
                    "id": "preset-bad-payload",
                    "classKey": "mage",
                    "specKey": "fire",
                    "name": "Fire Default",
                    "profile": "mage=Fire_Default",
                    "payload": {},
                    "updatedAt": "",
                },
            ],
        )
        self.assertEqual(build_websim_profile_presets_read_model([]), [])

    def test_build_websim_assets_read_model_counts_status_and_source(self):
        from server.pg_gear_read_model_selectors import build_websim_assets_read_model

        rows = [
            ("asset-a", "item", "item-a", "gear", "icon", "a.png", "icon_56", "blizzard", "verified"),
            ("asset-b", "spell", "spell-b", "talent", "icon", "b.png", "icon_56", "static_icon_name", "fallback"),
        ]
        asset_calls = []

        def asset_factory(row):
            asset_calls.append(row)
            return {"id": row[0], "source": row[7], "status": row[8]}

        payload = build_websim_assets_read_model(rows, asset_factory=asset_factory)

        self.assertEqual([asset["id"] for asset in payload["assets"]], ["asset-a", "asset-b"])
        self.assertEqual(payload["counts"]["byStatus"], {"verified": 1, "fallback": 1})
        self.assertEqual(payload["counts"]["bySource"], {"blizzard": 1, "static_icon_name": 1})
        self.assertEqual(payload["status"], "verified")
        self.assertEqual(payload["blockers"], [])
        self.assertEqual(asset_calls, rows)

        empty_payload = build_websim_assets_read_model([], asset_factory=asset_factory)
        self.assertEqual(empty_payload["assets"], [])
        self.assertEqual(empty_payload["counts"], {"byStatus": {}, "bySource": {}})
        self.assertEqual(empty_payload["status"], "empty")

    def test_build_websim_instances_read_model_groups_encounters_by_instance(self):
        from server.pg_gear_read_model_selectors import build_websim_instances_read_model

        instance_rows = [
            ("instance-b", "Dungeon B", "dungeon"),
            ("instance-a", "Raid A", "raid"),
        ]
        encounter_rows = [
            ("encounter-b1", "instance-b", "Boss B1"),
            ("encounter-b2", "instance-b", "Boss B2"),
            ("encounter-orphan", "missing-instance", "Ghost Boss"),
        ]

        instances = build_websim_instances_read_model(instance_rows, encounter_rows)

        self.assertEqual([instance["id"] for instance in instances], ["instance-b", "instance-a"])
        self.assertEqual(instances[0]["name"], "Dungeon B")
        self.assertEqual(instances[0]["category"], "dungeon")
        self.assertEqual(
            instances[0]["encounters"],
            [
                {"id": "encounter-b1", "instanceId": "instance-b", "name": "Boss B1"},
                {"id": "encounter-b2", "instanceId": "instance-b", "name": "Boss B2"},
            ],
        )
        self.assertEqual(instances[1]["encounters"], [])

    def test_build_websim_loot_items_read_model_maps_filters_and_limits_rows(self):
        from server.pg_gear_read_model_selectors import build_websim_loot_items_read_model

        normalizer_calls = []
        asset_calls = []

        def normalize_item(payload, default_source_type=""):
            normalizer_calls.append((payload, default_source_type))
            if payload.get("itemId") == "bad-item":
                return None
            return {
                "name": payload["name"],
                "displayName": payload["displayName"],
                "slot": payload["slot"],
                "source": payload["source"],
                "payload": payload["payload"],
                "simcReady": False,
            }

        def game_asset_factory(entity_type, entity_id, context_key, icon_url, **kwargs):
            asset_calls.append((entity_type, entity_id, context_key, icon_url, kwargs))
            return {
                "entityType": entity_type,
                "entityId": entity_id,
                "contextKey": context_key,
                "iconUrl": icon_url,
                "fallbackText": kwargs.get("fallback_text"),
                "semanticTags": kwargs.get("semantic_tags"),
            }

        rows = [
            (
                "loot-a",
                "1300",
                "Dungeon A",
                "9001",
                "Boss A",
                "item-a",
                "Flame Hood",
                "head",
                "Epic",
                "https://example.test/a.png",
                '{"source": "battle_net"}',
            ),
            (
                "loot-b",
                "1301",
                "Dungeon B",
                "9002",
                "Boss B",
                "item-b",
                "Frost Ring",
                "finger1",
                "Rare",
                "https://example.test/b.png",
                '{"source": "battle_net"}',
            ),
            (
                "loot-bad",
                "1301",
                "Dungeon B",
                "9003",
                "Boss C",
                "bad-item",
                "Skipped Trinket",
                "trinket1",
                "Rare",
                "https://example.test/c.png",
                "{}",
            ),
        ]

        items = build_websim_loot_items_read_model(
            rows,
            {"instanceId": "1301", "slot": "finger1", "q": "boss b"},
            limit=1,
            normalize_item=normalize_item,
            game_asset_factory=game_asset_factory,
            fallback_text=lambda value: f"fallback:{value}",
        )

        self.assertEqual([item["id"] for item in items], ["loot-b"])
        self.assertEqual(items[0]["itemId"], "item-b")
        self.assertEqual(items[0]["instanceName"], "Dungeon B")
        self.assertEqual(items[0]["encounterName"], "Boss B")
        self.assertEqual(items[0]["quality"], "Rare")
        self.assertEqual(items[0]["sourceType"], "verifiedLoot")
        self.assertEqual(items[0]["gameAsset"]["fallbackText"], "fallback:Frost Ring")
        self.assertIn("finger1", items[0]["gameAsset"]["semanticTags"])
        self.assertEqual(len(normalizer_calls), 3)
        self.assertEqual(normalizer_calls[0][0]["source"], "Boss A - Dungeon A")
        self.assertEqual(normalizer_calls[0][1], "verifiedLoot")
        self.assertEqual([call[1] for call in asset_calls], ["item-a", "item-b"])

    def test_build_admin_gear_variant_records_read_model_maps_variant_rows(self):
        from server.pg_gear_read_model_selectors import build_admin_gear_variant_records_read_model

        rows = [
            (
                501,
                "item-501",
                "Observed Blade",
                "main_hand",
                "Mythic 710",
                "raid",
                "mythic",
                "710",
                '{"bonus_id": "123", "gem_id": 213743}',
                "verified",
                '["missing_stats", ""]',
                '{"variantEvidence": {"source": "admin"}}',
                '{"displayName": "Observed Blade", "inventory_type": {"type": "weapon"}}',
                "Liberation of Undermine",
                "instance-11",
                "2026-07-09T12:34:56Z",
            ),
            (
                None,
                None,
                None,
                "",
                "",
                "",
                "",
                "not-a-number",
                "{bad json",
                "",
                "{bad json",
                "{bad json",
                "{bad json",
                None,
                None,
                None,
            ),
        ]

        records = build_admin_gear_variant_records_read_model(rows)

        self.assertEqual(
            records[0],
            {
                "id": "501",
                "itemId": "item-501",
                "itemName": "Observed Blade",
                "slot": "main_hand",
                "label": "Mythic 710",
                "sourceType": "raid",
                "difficultyKey": "mythic",
                "itemLevel": 710,
                "simcOptions": {"bonus_id": "123", "gem_id": 213743},
                "status": "verified",
                "blockers": ["missing_stats", ""],
                "payload": {"variantEvidence": {"source": "admin"}},
                "itemPayload": {"displayName": "Observed Blade", "inventory_type": {"type": "weapon"}},
                "sourceLabel": "Liberation of Undermine",
                "sourceInstanceId": "instance-11",
                "updatedAt": "2026-07-09T12:34:56Z",
            },
        )
        self.assertEqual(records[1]["id"], "")
        self.assertEqual(records[1]["itemId"], "")
        self.assertEqual(records[1]["itemLevel"], 0)
        self.assertEqual(records[1]["simcOptions"], {})
        self.assertEqual(records[1]["blockers"], [])
        self.assertEqual(records[1]["payload"], {})
        self.assertEqual(records[1]["itemPayload"], {})
        self.assertEqual(records[1]["sourceLabel"], "")
        self.assertEqual(records[1]["updatedAt"], "")

    def test_build_gear_mod_options_by_type_read_model_groups_option_types(self):
        from server.pg_gear_read_model_selectors import build_gear_mod_options_by_type_read_model

        rows = [
            (
                401,
                "socket",
                "quick-ruby",
                "Quick Ruby",
                '["head"]',
                '{"gem_id": 213743}',
                "verified",
                '{"displayLabel": "Quick Ruby"}',
                "2026-07-09T12:00:00Z",
            ),
            (
                402,
                "enchant",
                "any-slot-enchant",
                "Any Slot Enchant",
                '"*"',
                '{"enchant_id": "7418"}',
                "partial",
                '{"displayLabel": "Any Slot Enchant"}',
                None,
            ),
            (
                403,
                "unsupported",
                "ignored",
                "Ignored",
                '["head"]',
                "{}",
                "verified",
                "{}",
                None,
            ),
        ]

        read_model = build_gear_mod_options_by_type_read_model(rows)

        self.assertEqual(sorted(read_model.keys()), ["embellishment", "enchant", "socket"])
        self.assertEqual(read_model["socket"]["head"][0]["id"], "401")
        self.assertEqual(read_model["socket"]["head"][0]["simcOptions"], {"gem_id": "213743"})
        self.assertEqual(read_model["enchant"]["head"][0]["id"], "402")
        self.assertEqual(read_model["enchant"]["neck"][0]["id"], "402")
        self.assertTrue(all(not options for options in read_model["embellishment"].values()))

    def test_build_gear_catalog_items_read_model_enriches_item_rows(self):
        from server.pg_gear_read_model_selectors import build_gear_catalog_items_read_model

        item_payload = {
            "displayName": "Observed Hood",
            "quality": "epic",
            "iconUrl": "https://example.test/hood.png",
            "item_class": {"id": 4, "name": "Armor"},
            "item_subclass": {"id": 1, "name": "Cloth"},
            "inventory_type": {"type": "head", "name": "Head"},
            "_metadata": {"source": "battle_net_item_metadata", "metadataStatus": "verified"},
        }
        item_rows = [
            (
                "700001",
                "Prototype Hood",
                "head",
                678,
                json.dumps(item_payload),
                "verified",
            ),
            ("700002", "No Source Hood", "head", 650, "{}", "verified"),
        ]
        sources_by_item = {
            "700001": [
                {
                    "id": "source-1",
                    "itemId": "700001",
                    "sourceType": "observed_profile",
                    "sourceKey": "raiderio_observed_profile",
                    "label": "Observed profile",
                    "sourceLabel": "Observed profile",
                    "payload": {"observedProfileRefs": [{"characterName": "Tester"}]},
                    "recommendationScore": 99,
                }
            ]
        }
        variants_by_item = {
            "700001": [
                {
                    "id": "variant-1",
                    "itemId": "700001",
                    "slot": "head",
                    "variantKey": "observed",
                    "key": "observed",
                    "label": "Observed 684",
                    "sourceType": "observed_profile",
                    "difficultyKey": "",
                    "itemLevel": 684,
                    "ilevel": 684,
                    "simcOptions": {"bonus_id": "123"},
                    "status": "verified",
                    "payload": {"observedProfileRefs": [{"characterName": "Tester"}]},
                }
            ]
        }
        mod_options_by_slot = {
            "socket": {"head": []},
            "enchant": {"head": []},
            "embellishment": {"head": []},
        }

        catalog_items = build_gear_catalog_items_read_model(
            item_rows,
            sources_by_item,
            variants_by_item,
            mod_options_by_slot,
            "mage",
            "frost",
            {"seasonRevision": "s1"},
        )

        self.assertEqual([item["itemId"] for item in catalog_items], ["700001"])
        item = catalog_items[0]
        self.assertEqual(item["displayName"], "Observed Hood")
        self.assertEqual(item["slot"], "head")
        self.assertEqual(item["ilevel"], 684)
        self.assertEqual(item["armorType"], "Cloth")
        self.assertEqual(item["source"], "Observed profile")
        self.assertEqual(item["sourceRefs"][0]["sourceKey"], "raiderio_observed_profile")
        self.assertEqual(item["variants"][0]["id"], "variant-1")
        self.assertEqual(item["defaultVariantKey"], "observed")
        self.assertEqual(item["variantStatus"], "verified")
        self.assertEqual(item["recommendationScore"], 99)
        self.assertEqual(item["observedProfileRefs"], [{"characterName": "Tester"}])

    def test_build_gear_mod_options_by_slot_read_model_groups_option_rows(self):
        from server.pg_gear_read_model_selectors import build_gear_mod_options_by_slot_read_model
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        rows = [
            (
                301,
                "socket",
                "quick-ruby",
                "Quick Ruby",
                '["head", "neck"]',
                '{"gem_id": 213743, "ignored": "drop"}',
                "verified",
                '{"displayLabel": "Quick Ruby", "displayKind": "gem", "evidenceSource": "test", "iconUrl": "https://example.test/gem.png", "uniqueLimit": 1}',
                "2026-07-09T11:20:00Z",
            ),
            (
                302,
                "enchant",
                "any-slot-enchant",
                "Any Slot Enchant",
                '"*"',
                '{"enchant_id": "7418"}',
                "partial",
                '{"displayLabel": "Any Slot Enchant", "metadataStatus": "verified"}',
                None,
            ),
        ]

        read_model = build_gear_mod_options_by_slot_read_model(rows)

        self.assertEqual(sorted(read_model.keys()), sorted(CANONICAL_GEAR_SLOTS))
        socket_option = read_model["head"][0]
        self.assertEqual(socket_option["id"], "301")
        self.assertEqual(socket_option["type"], "socket")
        self.assertEqual(socket_option["optionType"], "socket")
        self.assertEqual(socket_option["rawName"], "Quick Ruby")
        self.assertEqual(socket_option["status"], "verified")
        self.assertEqual(socket_option["simcOptions"], {"gem_id": "213743"})
        self.assertEqual(socket_option["payload"]["displayLabel"], "Quick Ruby")
        self.assertEqual(socket_option["displayLabel"], "Quick Ruby")
        self.assertEqual(socket_option["displayKind"], "gem")
        self.assertEqual(socket_option["evidenceSource"], "test")
        self.assertEqual(socket_option["iconUrl"], "https://example.test/gem.png")
        self.assertEqual(socket_option["uniqueLimit"], 1)
        self.assertEqual(socket_option["updatedAt"], "2026-07-09T11:20:00Z")
        self.assertEqual(read_model["neck"][0]["id"], "301")

        enchant_option = next(option for option in read_model["head"] if option["id"] == "302")
        self.assertEqual(enchant_option["type"], "enchant")
        self.assertEqual(enchant_option["status"], "partial")
        self.assertEqual(enchant_option["simcOptions"], {"enchant_id": "7418"})
        self.assertEqual(enchant_option["metadataStatus"], "verified")
        self.assertEqual(enchant_option["updatedAt"], "")
        self.assertTrue(all(any(option["id"] == "302" for option in read_model[slot]) for slot in CANONICAL_GEAR_SLOTS))

    def test_build_gear_variants_by_item_read_model_groups_variant_rows(self):
        from server.pg_gear_read_model_selectors import build_gear_variants_by_item_read_model
        from server.websim_payload import localized_difficulty_label

        rows = [
            (
                201,
                19019,
                "head",
                "mythic-710",
                "Mythic 710",
                "raid",
                "mythic",
                "710",
                '{"bonus_id": "123", "gem_id": 213743}',
                "verified",
                '["missing_stats", ""]',
                '{"simcIlevelOnly": true, "statSummary": "kept"}',
                "2026-07-09T11:10:00Z",
            ),
            (
                202,
                19019,
                "finger1",
                "heroic-bad-ilvl",
                "Heroic Bad",
                "dungeon",
                "heroic",
                "not-a-number",
                "{bad json",
                "",
                '"blocked_by_source"',
                '["not", "a", "dict"]',
                None,
            ),
        ]

        read_model = build_gear_variants_by_item_read_model(rows)

        self.assertEqual(list(read_model.keys()), ["19019"])
        self.assertEqual(len(read_model["19019"]), 2)
        first_variant = read_model["19019"][0]
        self.assertEqual(first_variant["id"], "201")
        self.assertEqual(first_variant["itemId"], "19019")
        self.assertEqual(first_variant["slot"], "head")
        self.assertEqual(first_variant["key"], "mythic-710")
        self.assertEqual(first_variant["variantKey"], "mythic-710")
        self.assertEqual(first_variant["label"], "Mythic 710")
        self.assertEqual(first_variant["difficultyLabel"], localized_difficulty_label("mythic", "Mythic 710", "raid"))
        self.assertEqual(first_variant["sourceType"], "raid")
        self.assertEqual(first_variant["difficultyKey"], "mythic")
        self.assertEqual(first_variant["itemLevel"], 710)
        self.assertEqual(first_variant["ilevel"], 710)
        self.assertEqual(first_variant["simcOptions"], {"bonus_id": "123", "gem_id": 213743})
        self.assertEqual(first_variant["status"], "verified")
        self.assertEqual(first_variant["blockers"], ["missing_stats"])
        self.assertEqual(first_variant["payload"], {"simcIlevelOnly": True, "statSummary": "kept"})
        self.assertTrue(first_variant["simcIlevelOnly"])
        self.assertEqual(first_variant["updatedAt"], "2026-07-09T11:10:00Z")

        fallback_variant = read_model["19019"][1]
        self.assertEqual(fallback_variant["slot"], "finger1")
        self.assertEqual(fallback_variant["itemLevel"], 0)
        self.assertEqual(fallback_variant["ilevel"], 0)
        self.assertEqual(fallback_variant["simcOptions"], {})
        self.assertEqual(fallback_variant["status"], "blocked")
        self.assertEqual(fallback_variant["blockers"], ["blocked_by_source"])
        self.assertEqual(fallback_variant["payload"], {})
        self.assertNotIn("simcIlevelOnly", fallback_variant)
        self.assertEqual(fallback_variant["updatedAt"], "")

    def test_build_gear_sources_by_item_read_model_groups_source_rows(self):
        from server.pg_gear_read_model_selectors import build_gear_sources_by_item_read_model
        from server.websim_payload import localized_difficulty_label

        rows = [
            (
                101,
                19019,
                "dungeon",
                "the-stonevault",
                "The Stonevault",
                1278,
                2824,
                "mythic_plus",
                "season-1",
                '{"recommendationScore": 98, "observedProfiles": 40}',
                "2026-07-09T11:00:00Z",
            ),
            (
                102,
                19019,
                "raid",
                "liberation-of-undermine",
                "",
                None,
                None,
                "mythic",
                "season-1",
                "{bad json",
                None,
            ),
        ]

        read_model = build_gear_sources_by_item_read_model(rows)

        self.assertEqual(list(read_model.keys()), ["19019"])
        self.assertEqual(len(read_model["19019"]), 2)
        first_source = read_model["19019"][0]
        self.assertEqual(first_source["id"], "101")
        self.assertEqual(first_source["itemId"], "19019")
        self.assertEqual(first_source["sourceType"], "dungeon")
        self.assertEqual(first_source["sourceKey"], "the-stonevault")
        self.assertEqual(first_source["label"], "The Stonevault")
        self.assertEqual(first_source["sourceLabel"], "The Stonevault")
        self.assertEqual(first_source["instanceId"], 1278)
        self.assertEqual(first_source["encounterId"], 2824)
        self.assertEqual(first_source["difficultyKey"], "mythic_plus")
        self.assertEqual(
            first_source["difficultyLabel"],
            localized_difficulty_label("mythic_plus", "The Stonevault", "dungeon"),
        )
        self.assertEqual(first_source["seasonRevision"], "season-1")
        self.assertEqual(first_source["payload"], {"recommendationScore": 98, "observedProfiles": 40})
        self.assertEqual(first_source["recommendationScore"], 98)
        self.assertEqual(first_source["updatedAt"], "2026-07-09T11:00:00Z")

        fallback_source = read_model["19019"][1]
        self.assertEqual(fallback_source["label"], "liberation-of-undermine")
        self.assertEqual(fallback_source["sourceLabel"], "liberation-of-undermine")
        self.assertEqual(fallback_source["payload"], {})
        self.assertNotIn("recommendationScore", fallback_source)
        self.assertEqual(fallback_source["updatedAt"], "")

    def test_build_catalog_output_read_model_fragment_keeps_full_debug_fields_out_of_compact_payload(self):
        from server.pg_gear_read_model_selectors import build_catalog_output_read_model_fragment

        catalog_read_model = {
            "replacementCandidates": [{"slot": "head", "items": [{"itemId": "head-1"}]}],
            "catalogItems": [{"itemId": f"item-{idx}"} for idx in range(130)],
            "candidateLegalityAudit": {
                "excludedCandidateCount": 1,
                "excludedExamples": [{"itemId": "blocked-mail-head"}],
            },
        }

        compact_fragment = build_catalog_output_read_model_fragment(
            catalog_read_model,
            compact=True,
        )
        full_fragment = build_catalog_output_read_model_fragment(
            catalog_read_model,
            compact=False,
        )

        self.assertEqual(len(compact_fragment["catalogItems"]), 120)
        self.assertEqual(compact_fragment["catalogItems"][0]["itemId"], "item-0")
        self.assertEqual(compact_fragment["catalogItems"][-1]["itemId"], "item-119")
        self.assertNotIn("slotGroups", compact_fragment)
        self.assertNotIn("candidateLegalityAudit", compact_fragment)
        self.assertEqual(full_fragment["slotGroups"], catalog_read_model["replacementCandidates"])
        self.assertEqual(full_fragment["presets"], [])
        self.assertEqual(full_fragment["candidateItems"], [])
        self.assertEqual(full_fragment["candidateLegalityAudit"], catalog_read_model["candidateLegalityAudit"])
        self.assertEqual(len(full_fragment["catalogItems"]), 120)

    def test_build_common_gear_read_model_fragment_blocks_stat_snapshot(self):
        from server.pg_gear_read_model_selectors import build_common_gear_read_model_fragment

        readiness = {
            "status": "blocked",
            "selectedCount": 0,
            "itemLevel": {
                "key": "itemLevel",
                "label": "装备等级",
                "value": "0",
                "rawValue": 0,
                "selectedCount": 0,
                "source": "selected_gear",
            },
        }

        fragment = build_common_gear_read_model_fragment(
            "mage",
            "arcane",
            readiness,
            checked_at="2026-07-09T10:35:00Z",
        )

        self.assertEqual(fragment["weaponRule"]["mode"], "caster_1h_or_staff")
        self.assertEqual(len(fragment["slots"]), 16)
        self.assertEqual(fragment["slots"][0]["slot"], "head")
        self.assertIs(fragment["readiness"], readiness)
        self.assertEqual(fragment["maxLevel"], 90)
        self.assertEqual(fragment["checkedAt"], "2026-07-09T10:35:00Z")
        self.assertEqual(fragment["statSnapshot"]["statStatus"], "blocked")
        self.assertEqual(fragment["statSnapshot"]["classKey"], "mage")
        self.assertEqual(fragment["statSnapshot"]["specKey"], "arcane")
        self.assertEqual(
            fragment["statSnapshot"]["blockers"],
            ["Select complete SimC-ready gear and talents to calculate a verified stat snapshot."],
        )
        self.assertEqual(fragment["statSnapshot"]["gearReadiness"], readiness)

    def test_build_initial_gear_read_model_fragment_compacts_baseline_template(self):
        from server.pg_gear_read_model_selectors import build_initial_gear_read_model_fragment

        baseline_template = {
            "gearItems": [
                {
                    "id": "cloth-head",
                    "itemId": "cloth-head",
                    "slot": "head",
                    "simcSlot": "head",
                    "name": "Cloth Head",
                    "displayName": "Cloth Head",
                    "itemLevel": 707,
                    "ilevel": 707,
                    "bonusIds": [123],
                    "simcReady": True,
                    "socketOptions": [{"id": "socket-hidden"}],
                },
                {
                    "id": "duplicate-head",
                    "itemId": "duplicate-head",
                    "slot": "head",
                    "simcSlot": "head",
                    "name": "Duplicate Head",
                    "itemLevel": 700,
                    "simcReady": True,
                },
                {
                    "id": "bad-slot",
                    "itemId": "bad-slot",
                    "slot": "invalid",
                    "name": "Bad Slot",
                    "simcReady": True,
                },
            ]
        }

        read_model = build_initial_gear_read_model_fragment(
            baseline_template,
            "mage",
            "arcane",
            compact=True,
        )

        head_group = next(group for group in read_model["replacementCandidates"] if group["slot"] == "head")
        self.assertEqual(len(read_model["replacementCandidates"]), 16)
        self.assertEqual(head_group["label"], "头部")
        self.assertEqual(head_group["detailMode"], "partial")
        self.assertEqual(head_group["fullItemCount"], 1)
        self.assertEqual([item["itemId"] for item in head_group["items"]], ["cloth-head"])
        self.assertNotIn("socketOptions", head_group["items"][0])
        self.assertTrue(read_model["equippedSet"]["head"]["slotDetailAvailable"])
        self.assertEqual(read_model["equippedSet"]["head"]["detailMode"], "summary")
        self.assertEqual([item["itemId"] for item in read_model["baselineSet"]], ["cloth-head", "duplicate-head", "bad-slot"])
        self.assertEqual(read_model["catalogItems"], read_model["baselineSet"][:120])
        self.assertEqual(read_model["readiness"]["selectedCount"], 3)
        self.assertEqual(read_model["slotReadiness"]["head"]["status"], "verified")
        self.assertEqual(read_model["slotReadiness"]["neck"]["status"], "blocked")

    def test_build_catalog_state_read_model_fragment_exposes_health_and_coverage_envelope(self):
        from server.pg_gear_read_model_selectors import build_catalog_state_read_model_fragment

        catalog_state = {
            "schemaRevision": "catalog-rev-test",
            "status": "verified",
            "checkedAt": "2026-07-09T08:30:00Z",
            "updatedAt": "2026-07-09T08:00:00Z",
            "itemDatabaseRevision": "items-rev-test",
            "variantRevision": "variants-rev-test",
            "slotCoverage": {"head": {"verified": 3}},
            "sourceCoverage": {"raid": {"verified": 4}},
            "observedVariantCount": 40,
            "verifiedObservedVariantCount": 39,
            "verifiedCount": 120,
            "partialCount": 8,
            "blockedCount": 2,
            "blockers": ["state blocker"],
        }
        catalog_blockers = ["sample blocker"]

        read_model = build_catalog_state_read_model_fragment(catalog_state, catalog_blockers)

        self.assertEqual(read_model["gearSchemaRevision"], "websim-gear-simulator-v1")
        self.assertEqual(read_model["gearCatalogRevision"], "catalog-rev-test")
        self.assertEqual(read_model["catalogStatus"], "verified")
        self.assertEqual(read_model["catalogHealthSummary"]["status"], "verified")
        self.assertEqual(read_model["catalogHealthSummary"]["verifiedVariantCount"], 120)
        self.assertEqual(read_model["catalogHealthSummary"]["blockers"], ["state blocker"])
        self.assertEqual(
            read_model["catalogCoverage"],
            {
                "slotCoverage": {"head": {"verified": 3}},
                "sourceCoverage": {"raid": {"verified": 4}},
                "observedVariantCount": 40,
                "verifiedObservedVariantCount": 39,
                "verifiedVariantCount": 120,
                "partialVariantCount": 8,
                "blockedVariantCount": 2,
            },
        )
        self.assertEqual(read_model["itemDatabaseRevision"], "items-rev-test")
        self.assertEqual(read_model["variantRevision"], "variants-rev-test")
        self.assertEqual(read_model["catalogCheckedAt"], "2026-07-09T08:30:00Z")
        self.assertEqual(read_model["catalogBlockers"], ["sample blocker"])

    def test_build_catalog_gear_read_model_fragment_groups_candidates_and_audits_blocked_items(self):
        from server.pg_gear_read_model_selectors import build_catalog_gear_read_model_fragment

        legal_head = {
            "id": "cloth-head",
            "itemId": "cloth-head",
            "slot": "head",
            "simcSlot": "head",
            "name": "Cloth Head",
            "displayName": "Cloth Head",
            "sourceType": "raid",
            "itemLevel": 707,
            "ilevel": 707,
            "armorType": "Cloth",
            "simcReady": True,
        }
        blocked_head = {
            **legal_head,
            "id": "mail-head",
            "itemId": "mail-head",
            "name": "Mail Head",
            "displayName": "Mail Head",
            "armorType": "Mail",
        }
        raw_options_by_slot = {
            "socket": {
                "head": [
                    {
                        "id": "socket-head",
                        "optionType": "socket",
                        "name": "Head Socket",
                        "simcOptions": {"gem_id": "213743"},
                        "status": "verified",
                    }
                ]
            },
            "enchant": {},
            "embellishment": {},
        }

        read_model = build_catalog_gear_read_model_fragment(
            [legal_head, blocked_head],
            raw_options_by_slot,
            "mage",
            "arcane",
            compact=True,
        )

        head_group = next(group for group in read_model["replacementCandidates"] if group["slot"] == "head")
        self.assertEqual([item["itemId"] for item in head_group["items"]], ["cloth-head"])
        self.assertNotIn("socketOptions", head_group["items"][0])
        self.assertEqual(
            head_group["socketOptions"],
            [
                {
                    "id": "socket-head",
                    "optionType": "socket",
                    "name": "Head Socket",
                    "simcOptions": {"gem_id": "213743"},
                    "status": "verified",
                }
            ],
        )
        self.assertEqual(read_model["readiness"]["simcReadyCount"], 1)
        self.assertEqual(read_model["slotReadiness"]["head"]["status"], "partial")
        self.assertEqual(read_model["slotReadiness"]["head"]["missingFields"], ["bonus_id/gem_id/enchant_id"])
        self.assertEqual(read_model["catalogItems"][0]["itemId"], "cloth-head")
        self.assertEqual(read_model["candidateLegalityAudit"]["excludedCandidateCount"], 1)
        self.assertEqual(read_model["candidateLegalityAudit"]["excludedExamples"][0]["itemId"], "mail-head")

    def test_build_season_recommended_catalog_candidates_by_slot_read_model_filters_and_limits_candidates(self):
        from server.pg_gear_read_model_selectors import build_season_recommended_catalog_candidates_by_slot_read_model
        from server.websim_payload import CANONICAL_GEAR_SLOTS

        low_head = {
            "id": "cloth-head-low",
            "itemId": "cloth-head-low",
            "slot": "head",
            "simcSlot": "head",
            "name": "Low Cloth Head",
            "displayName": "Low Cloth Head",
            "sourceType": "raid",
            "variantStatus": "verified",
            "metadataStatus": "verified",
            "itemLevel": 700,
            "ilevel": 700,
            "armorType": "Cloth",
            "bonus_id": "1808",
            "simcReady": True,
            "itemStats": [{"key": "intellect", "value": 1000}],
        }
        high_head = {
            **low_head,
            "id": "cloth-head-high",
            "itemId": "cloth-head-high",
            "name": "High Cloth Head",
            "displayName": "High Cloth Head",
            "itemLevel": 710,
            "ilevel": 710,
        }
        blocked_mail_head = {
            **low_head,
            "id": "mail-head",
            "itemId": "mail-head",
            "name": "Mail Head",
            "displayName": "Mail Head",
            "itemLevel": 720,
            "ilevel": 720,
            "armorType": "Mail",
        }
        blocked_weapon = {
            **low_head,
            "id": "illegal-weapon",
            "itemId": "illegal-weapon",
            "slot": "main_hand",
            "simcSlot": "main_hand",
            "name": "Illegal Mace",
            "displayName": "Illegal Mace",
            "armorType": "",
            "weaponType": "Two-Handed Mace",
        }

        read_model = build_season_recommended_catalog_candidates_by_slot_read_model(
            [low_head, blocked_mail_head, high_head, dict(high_head), blocked_weapon],
            "mage",
            "arcane",
            candidate_limit=1,
        )

        self.assertEqual(sorted(read_model.keys()), sorted(CANONICAL_GEAR_SLOTS))
        self.assertEqual([item["itemId"] for item in read_model["head"]], ["cloth-head-high"])
        self.assertEqual(read_model["head"][0]["legalityStatus"], "legal")
        self.assertTrue(all(item["itemId"] != "mail-head" for items in read_model.values() for item in items))
        self.assertTrue(all(item["itemId"] != "illegal-weapon" for items in read_model.values() for item in items))


if __name__ == "__main__":
    unittest.main()
