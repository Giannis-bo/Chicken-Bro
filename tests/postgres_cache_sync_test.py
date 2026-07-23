import hashlib
import json
import os
import unittest
from unittest.mock import patch


def complete_simc_candidate(
    spec_pairs=("mage:frost",),
    hero_triplets=("mage:frost:spellslinger",),
    nodes_per_context=5,
):
    talents = []
    next_node_id = 90000
    for spec_pair in spec_pairs:
        class_key, spec_key = spec_pair.split(":", 1)
        contexts = [
            ("class", f"class:{class_key}", ""),
            ("spec", f"spec:{class_key}:{spec_key}", ""),
        ]
        contexts.extend(
            ("hero", f"hero:{hero_key}", hero_key)
            for hero_class, hero_spec, hero_key in (triplet.split(":", 2) for triplet in hero_triplets)
            if (hero_class, hero_spec) == (class_key, spec_key)
        )
        for tree_type, tree_id, hero_key in contexts:
            previous_id = ""
            for index in range(nodes_per_context):
                next_node_id += 1
                talent_id = f"simc-{tree_type}-{class_key}-{spec_key}-{hero_key or 'none'}-{index}"
                spell_id = next_node_id + 100000
                trait_id = next_node_id + 200000
                trait_definition_id = next_node_id + 300000
                payload = {
                    "treeType": tree_type,
                    "nodeId": next_node_id,
                    "traitId": trait_id,
                    "traitDefinitionId": trait_definition_id,
                    "heroKey": hero_key,
                    "parentIds": [previous_id] if previous_id else [],
                    "parentMode": "any",
                    "selectionIndex": 0,
                    "nodeType": 0,
                    "rank": 1,
                    "maxRank": 1,
                    "selectedRank": 0,
                    "grantedRank": 0,
                    "granted": False,
                    "choiceGroup": "",
                    "shape": "square",
                    "pointRequirement": 0,
                    "rankEntries": [
                        {
                            "rank": 1,
                            "points": 1,
                            "pointStart": 1,
                            "pointEnd": 1,
                            "traitId": trait_id,
                            "traitDefinitionId": trait_definition_id,
                            "spellId": spell_id,
                            "selectionIndex": 0,
                        }
                    ],
                }
                talents.append(
                    {
                        "id": talent_id,
                        "classKey": class_key,
                        "specKey": spec_key,
                        "treeId": tree_id,
                        "treeType": tree_type,
                        "row": index + 1,
                        "col": 1,
                        "spellId": spell_id,
                        "name": f"Fixture Talent {next_node_id}",
                        "payload": payload,
                    }
                )
                previous_id = talent_id
    return {
        "talents": talents,
        "presets": [
            {
                "id": f"preset-{spec_pair.replace(':', '-')}",
                "classKey": spec_pair.split(":", 1)[0],
                "specKey": spec_pair.split(":", 1)[1],
                "profile": (
                    f'{spec_pair.split(":", 1)[0]}="Fixture"\n'
                    f'spec={spec_pair.split(":", 1)[1]}'
                ),
            }
            for spec_pair in spec_pairs
        ],
        "spellDetails": [{"spellId": 123}],
        "source": "simc",
        "build": "simc-build",
        "dependencies": sum(
            len((talent.get("payload") or {}).get("parentIds") or []) for talent in talents
        ),
        "traitEdgeSource": "wago://TraitEdge",
    }


def simc_graph_baseline(candidate):
    from server.postgres_cache_store import simc_talent_persisted_content_identity

    contexts = {}
    for talent in candidate.get("talents") or []:
        payload = talent.get("payload") or {}
        tree_type = str(payload.get("treeType") or "")
        hero_key = str(payload.get("heroKey") or "") if tree_type == "hero" else ""
        key = (
            str(talent.get("classKey") or ""),
            str(talent.get("specKey") or ""),
            tree_type,
            hero_key,
        )
        counts = contexts.setdefault(
            key,
            {
                "classKey": key[0],
                "specKey": key[1],
                "treeType": key[2],
                "heroKey": key[3],
                "nodes": 0,
                "dependencyNodes": 0,
                "dependencies": 0,
                "graphEntries": [],
                "contentEntries": [],
                "visualSlots": {},
                "foreignSpecNodeIds": [],
            },
        )
        parent_ids = [parent_id for parent_id in (payload.get("parentIds") or []) if parent_id]
        counts["nodes"] += 1
        counts["dependencyNodes"] += int(bool(parent_ids))
        counts["dependencies"] += len(parent_ids)
        rank_entries = tuple(
            sorted(
                (
                    (
                        int(entry.get("traitId") or 0),
                        int(entry.get("traitDefinitionId") or 0),
                        int(entry.get("spellId") or 0),
                        int(entry.get("selectionIndex") or 0),
                        int(entry.get("rank") or 0),
                        int(entry.get("points") or 0),
                        int(entry.get("pointStart") or 0),
                        int(entry.get("pointEnd") or 0),
                    )
                    for entry in (payload.get("rankEntries") or [])
                ),
                key=lambda entry: (entry[3], entry[0], entry[2]),
            )
        )
        counts["graphEntries"].append(
            (
                str(talent.get("id") or ""),
                int(talent.get("row") or 0),
                int(talent.get("col") or 0),
                int(talent.get("spellId") or 0),
                int(payload.get("nodeId") or 0),
                int(payload.get("traitId") or 0),
                rank_entries,
                int(payload.get("selectionIndex") or 0),
                int(payload.get("nodeType") or 0),
                int(payload.get("rank") or 0),
                int(payload.get("maxRank") or 0),
                int(payload.get("selectedRank") or 0),
                int(payload.get("grantedRank") or 0),
                bool(payload.get("granted")),
                str(payload.get("choiceGroup") or ""),
                int(payload.get("pointRequirement") or 0),
                str(payload.get("parentMode") or "any").strip().lower(),
                str(payload.get("shape") or "").strip().lower(),
                sorted(parent_ids),
            )
        )
        counts["contentEntries"].append(
            simc_talent_persisted_content_identity(
                talent.get("id"),
                talent.get("classKey"),
                talent.get("specKey"),
                talent.get("treeId"),
                talent.get("row"),
                talent.get("col"),
                talent.get("spellId"),
                talent.get("name"),
                payload,
            )
        )
        if not payload.get("choiceGroup") and payload.get("shape") != "choice":
            counts["visualSlots"].setdefault((int(talent.get("row") or 0), int(talent.get("col") or 0)), []).append(
                str(talent.get("id") or "")
            )
    rows = list(contexts.values())
    for row in rows:
        entries = sorted(row.pop("graphEntries"))
        content_entries = sorted(row.pop("contentEntries"))
        visual_slots = row.pop("visualSlots")
        foreign_spec_node_ids = row.pop("foreignSpecNodeIds")
        row["nodeIds"] = [entry[0] for entry in entries]
        row["structureSignature"] = hashlib.sha256(
            json.dumps(content_entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        row["parentIdsByNode"] = [[entry[0], entry[-1]] for entry in entries]
        row["graphSignature"] = hashlib.sha256(
            json.dumps(entries, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        row["visualSlots"] = [
            {"row": row_index, "col": col_index, "nodeIds": sorted(node_ids)}
            for (row_index, col_index), node_ids in sorted(visual_slots.items())
        ]
        row["foreignSpecNodeIds"] = sorted(set(foreign_spec_node_ids))
    presets = [preset for preset in (candidate.get("presets") or []) if isinstance(preset, dict)]
    profile_specs = sorted(
        {
            f"{preset.get('classKey')}:{preset.get('specKey')}"
            for preset in presets
            if preset.get("classKey") and preset.get("specKey") and str(preset.get("profile") or "").strip()
        }
    )
    return {
        "contexts": rows,
        "talents": sum(row["nodes"] for row in rows),
        "dependencyNodes": sum(row["dependencyNodes"] for row in rows),
        "dependencies": sum(row["dependencies"] for row in rows),
        "profiles": len({str(preset.get("id") or "") for preset in presets if preset.get("id")}),
        "profileSpecCoverage": len(profile_specs),
        "profileSpecs": profile_specs,
        "profileContentSignatures": sorted(
            (
                str(preset.get("classKey") or ""),
                str(preset.get("specKey") or ""),
                hashlib.sha256(str(preset.get("profile") or "").strip().encode("utf-8")).hexdigest(),
            )
            for preset in presets
            if preset.get("classKey") and preset.get("specKey") and str(preset.get("profile") or "").strip()
        ),
    }


class FakePostgresSyncStore:
    def __init__(self):
        self.replaced_data = None
        self.saved_states = []
        self.stat_payloads = []
        self.stat_previous = {}
        self.raiderio_payload = {}
        self.community_talent_templates = []
        self.community_gear_templates = []
        self.observed_backfills = []
        self.crafted_backfills = []
        self.gear_template_candidates = []
        self.season_recommended_gear_templates = []
        self.recommended_bis_prototype_templates = []
        self.expired_talent_source_keys = []
        self.saved_raiderio_payloads = []
        self.coverage_rows = []
        self.talent_replace_target_slot_ids = None
        self.saved_item_metadata = []
        self.metadata_gaps = []
        self.item_metadata_gaps = []
        self.real_player_residue_cleanups = []
        self.websim_sync_state = {}
        self.simc_graph_baseline = {"contexts": []}

    def replace_simc_generated_data(self, data):
        self.replaced_data = data
        return {
            "talents": len(data.get("talents") or []),
            "profiles": len(data.get("presets") or []),
            "spellDetails": len(data.get("spellDetails") or []),
            "build": data.get("build") or "",
            "source": data.get("source") or "",
            "dependencies": int(data.get("dependencies") or 0),
            "dependencyNodes": int(data.get("dependencyNodes") or 0),
            "specCoverage": int(data.get("specCoverage") or 0),
            "heroCoverage": int(data.get("heroCoverage") or 0),
            "profileSpecCoverage": int(data.get("profileSpecCoverage") or 0),
            "traitEdgeSource": data.get("traitEdgeSource") or "",
        }

    def simc_talent_graph_baseline(self):
        return self.simc_graph_baseline

    def replace_websim_journal_data(self, data):
        self.journal_data = data
        return {
            "dungeons": len((data.get("season") or {}).get("dungeons") or []),
            "instances": len(data.get("instances") or []),
            "encounters": 1,
            "items": 1,
            "loot": 1,
        }

    def rebuild_websim_gear_catalog_from_loot(self, season):
        self.gear_catalog_season = season
        return {"runner": "postgres", "status": "partial", "sourceCount": 1, "variantCount": 1, "blockers": []}

    def get_active_season_payload(self):
        return {"dataStatus": "verified", "seasonRevision": "season-pg"}

    def get_sync_state(self, key):
        if key == "gearCatalog":
            return {"status": "verified", "blockers": []}
        if key == "websim_sync":
            return self.websim_sync_state
        return {}

    def community_talent_template_counts(self):
        return {"total": 2, "verified": 2, "partial": 0, "blocked": 0}

    def community_gear_template_counts(self):
        return {"total": 1, "verified": 0, "partial": 1, "blocked": 0}

    def replace_community_talent_templates(self, templates, scan_run_id="", include_details=False, target_slot_ids=None):
        self.community_talent_templates.extend(templates)
        self.talent_replace_target_slot_ids = list(target_slot_ids or [])
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        for template in templates:
            status = template.get("status") or "blocked"
            bucket = "verified" if status in {"verified", "complete"} else ("partial" if status == "partial" else "blocked")
            counts["total"] += 1
            counts[bucket] += 1
        if include_details:
            counts["validatedTemplates"] = [dict(template) for template in templates]
        return counts

    def community_talent_template_coverage_rows(self):
        return [dict(row) for row in self.coverage_rows]

    def replace_community_gear_templates(self, templates, scan_run_id=""):
        self.community_gear_templates.extend(templates)
        counts = {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        for template in templates:
            status = template.get("status") or "blocked"
            bucket = "verified" if status in {"verified", "complete"} else ("partial" if status == "partial" else "blocked")
            counts["total"] += 1
            counts[bucket] += 1
        return counts

    def expire_community_talent_template_sources(self, source_keys, expired_at=""):
        self.expired_talent_source_keys.extend(source_keys or [])
        return {"expired": len(source_keys or [])}

    def build_community_gear_templates(self, scan_run_id=""):
        return self.gear_template_candidates

    def build_season_recommended_gear_templates(self, scan_run_id=""):
        return list(self.season_recommended_gear_templates)

    def build_recommended_bis_prototype_templates(self, scan_run_id=""):
        return list(self.recommended_bis_prototype_templates)

    def cleanup_real_player_gear_template_pilot_residue(self, scan_run_id="", checked_at=""):
        self.real_player_residue_cleanups.append({"scanRunId": scan_run_id, "checkedAt": checked_at})
        return {"communityTemplateRowsDeleted": 0, "observedVariantRowsDeleted": 0}

    def backfill_observed_gear_from_raiderio(
        self,
        raiderio_payload,
        mode="scheduled",
        target_limit=None,
        profile_limit=None,
        timeout_seconds=None,
        enable_simc_stats=None,
        full_profile_gear=None,
        item_probe_limit=None,
    ):
        self.observed_backfills.append(
            {
                "payload": raiderio_payload,
                "mode": mode,
                "targetLimit": target_limit,
                "profileLimit": profile_limit,
                "timeoutSeconds": timeout_seconds,
                "enableSimcStats": enable_simc_stats,
                "fullProfileGear": full_profile_gear,
                "itemProbeLimit": item_probe_limit,
            }
        )
        return {
            "status": "verified",
            "sourceStatus": "verified",
            "observedProfileCount": 1,
            "processedProfileCount": 1,
            "variantCount": 2,
            "targetLimit": target_limit,
            "profileLimit": profile_limit,
            "timeoutSeconds": timeout_seconds,
            "itemProbeLimit": item_probe_limit,
            "simcItemProbeCount": item_probe_limit or 0,
            "simcItemProbeResolvedCount": 1 if item_probe_limit else 0,
            "errors": [],
        }

    def backfill_crafted_gear_from_seed(self, items, mode="scheduled"):
        self.crafted_backfills.append((items, mode))
        return {"status": "partial", "sourceStatus": "partial", "itemCount": len(items), "variantCount": 1, "errors": []}

    def get_raiderio_payload(self):
        return self.raiderio_payload

    def save_raiderio_payload(self, payload):
        self.saved_raiderio_payloads.append(dict(payload or {}))
        self.raiderio_payload = dict(payload or {})
        return {"ok": True, "cacheKey": "raiderio_payload_v1", "fetchedAt": (payload or {}).get("checkedAt") or ""}

    def get_stat_weight_payload(self, class_key, spec_key, scenario_key):
        return self.stat_previous.get((class_key, spec_key, scenario_key))

    def save_stat_weight_payload(self, payload):
        self.stat_payloads.append(payload)
        return {"ok": True}

    def save_sync_state(self, key, value, updated_at=""):
        self.saved_states.append((key, value, updated_at))
        return {"ok": True}

    def save_websim_item_metadata(
        self,
        item_id,
        item_payload,
        media_payload=None,
        *,
        fallback_slot="",
        fallback_name="",
        english_payload=None,
        locale="zh_CN",
        source="Battle.net Game Data API",
    ):
        saved = {
            "itemId": str(item_id),
            "displayName": item_payload.get("name") or fallback_name or f"Item {item_id}",
            "slot": fallback_slot,
            "iconUrl": ((media_payload or {}).get("assets") or [{}])[0].get("value") or "",
            "metadataSource": source,
            "metadataLocale": locale,
            "englishName": (english_payload or {}).get("name") or "",
        }
        self.saved_item_metadata.append(
            {
                "itemId": str(item_id),
                "itemPayload": dict(item_payload or {}),
                "mediaPayload": dict(media_payload or {}),
                "fallbackSlot": fallback_slot,
                "fallbackName": fallback_name,
                "englishPayload": dict(english_payload or {}),
                "locale": locale,
                "source": source,
            }
        )
        return saved

    def community_gear_template_item_metadata_gaps(self, limit=200):
        return list(self.metadata_gaps[:limit])

    def websim_item_metadata_gaps(self, limit=200):
        return list(self.item_metadata_gaps[:limit])


class PostgresCacheSyncTest(unittest.TestCase):
    def test_raiderio_postgres_sync_fetches_fresh_payload_before_saving(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "stale",
            "status": "stale",
            "checkedAt": "old-cache",
            "communityTemplates": [],
        }
        fresh_payload = {
            "sourceStatus": "synced",
            "status": "synced",
            "checkedAt": "fresh-cache",
            "runCount": 1,
            "profileCount": 1,
            "communityTemplates": [{"id": "fresh-template"}],
        }

        def fake_sync(conn, force=False, stage_callback=None):
            self.assertIsNotNone(conn)
            return fresh_payload

        with patch.object(postgres_cache_sync, "sync_raiderio_cache", side_effect=fake_sync, create=True):
            payload = postgres_cache_sync.sync_raiderio_cache_postgres(store=store)

        self.assertEqual(payload["checkedAt"], "fresh-cache")
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(store.saved_raiderio_payloads[-1]["checkedAt"], "fresh-cache")
        self.assertEqual(store.saved_raiderio_payloads[-1]["communityTemplates"][0]["id"], "fresh-template")

    def test_raiderio_targeted_sync_merges_without_dropping_other_specs(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "synced",
            "status": "synced",
            "seasonSlug": "season-midnight-1",
            "checkedAt": "full-cache",
            "profiles": [
                {
                    "sourceIdentity": "raiderio:us|realm|arcane",
                    "classKey": "mage",
                    "specKey": "arcane",
                    "itemLevel": 700,
                },
                {
                    "sourceIdentity": "raiderio:us|realm|unholy-old",
                    "classKey": "deathknight",
                    "specKey": "unholy",
                    "itemLevel": 700,
                },
            ],
            "communityTemplates": [
                {
                    "id": "arcane-template",
                    "classKey": "mage",
                    "specKey": "arcane",
                },
                {
                    "id": "unholy-old-template",
                    "classKey": "deathknight",
                    "specKey": "unholy",
                },
            ],
            "specAggregates": [
                {
                    "classKey": "mage",
                    "specKey": "arcane",
                    "role": "dps",
                },
                {
                    "classKey": "deathknight",
                    "specKey": "unholy",
                    "role": "dps",
                    "sampleCount": 2,
                },
            ],
        }
        targeted_payload = {
            "sourceStatus": "synced",
            "status": "synced",
            "seasonSlug": "season-midnight-1",
            "checkedAt": "targeted-cache",
            "profiles": [
                {
                    "sourceIdentity": "raiderio:us|realm|unholy-new",
                    "classKey": "deathknight",
                    "specKey": "unholy",
                    "itemLevel": 710,
                }
            ],
            "communityTemplates": [
                {
                    "id": "unholy-new-template",
                    "classKey": "deathknight",
                    "specKey": "unholy",
                }
            ],
            "specAggregates": [
                {
                    "classKey": "deathknight",
                    "specKey": "unholy",
                    "role": "dps",
                    "sampleCount": 8,
                }
            ],
        }

        with patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache",
            return_value=targeted_payload,
            create=True,
        ), patch.dict(
            os.environ,
            {
                "WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS":
                    "deathknight:unholy",
            },
            clear=False,
        ):
            payload = (
                postgres_cache_sync.sync_raiderio_cache_postgres(
                    store=store
                )
            )

        self.assertEqual(
            {
                profile["sourceIdentity"]
                for profile in payload["profiles"]
            },
            {
                "raiderio:us|realm|arcane",
                "raiderio:us|realm|unholy-old",
                "raiderio:us|realm|unholy-new",
            },
        )
        self.assertEqual(
            {
                template["id"]
                for template in payload["communityTemplates"]
            },
            {
                "arcane-template",
                "unholy-old-template",
                "unholy-new-template",
            },
        )
        self.assertEqual(
            next(
                row
                for row in payload["specAggregates"]
                if row["specKey"] == "unholy"
            )["sampleCount"],
            8,
        )
        self.assertEqual(
            payload["targetedMerge"]["targetSpecs"],
            ["deathknight:unholy"],
        )
        self.assertEqual(
            store.saved_raiderio_payloads[-1]["checkedAt"],
            "targeted-cache",
        )

    def test_raiderio_postgres_sync_keeps_last_success_when_collection_returns_blocked(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "synced",
            "status": "synced",
            "checkedAt": "last-success",
            "communityTemplates": [{"id": "last-success-template"}],
        }
        blocked_payload = {
            "sourceStatus": "blocked",
            "status": "blocked",
            "checkedAt": "failed-attempt",
            "errors": ["Raider.IO TLS connection failed"],
            "communityTemplates": [],
        }

        with patch.object(postgres_cache_sync, "sync_raiderio_cache", return_value=blocked_payload, create=True):
            payload = postgres_cache_sync.sync_raiderio_cache_postgres(store=store)

        self.assertEqual(payload["sourceStatus"], "stale")
        self.assertEqual(payload["status"], "stale")
        self.assertEqual(payload["checkedAt"], "last-success")
        self.assertEqual(payload["communityTemplates"][0]["id"], "last-success-template")
        self.assertIn("Raider.IO TLS connection failed", payload["errors"])
        self.assertEqual(store.saved_raiderio_payloads, [])

    def test_community_postgres_sync_refreshes_raiderio_before_loading_sources(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "stale",
            "status": "stale",
            "checkedAt": "old-cache",
            "communityTemplates": [],
        }
        fresh_template = {
            "id": "rio-fresh-rider",
            "classKey": "deathknight",
            "specKey": "unholy",
            "heroKey": "rider_of_the_apocalypse",
            "scenarioKey": "mythic_plus",
            "talentState": {"selectedNodes": [{"id": "node-rider", "rank": 1}]},
            "status": "verified",
        }

        def fake_refresh(force=False, stage_callback=None, store=None):
            self.assertTrue(force)
            store.raiderio_payload = {
                "sourceStatus": "synced",
                "status": "synced",
                "checkedAt": "fresh-cache",
                "communityTemplates": [fresh_template],
            }
            return store.raiderio_payload

        with patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            side_effect=fake_refresh,
        ) as refresh, patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_RANKINGS_DISABLED": "1",
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": "",
            },
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store)

        refresh.assert_called_once()
        self.assertEqual(len(store.community_talent_templates), 1)
        self.assertEqual(store.community_talent_templates[0]["id"], "rio-fresh-rider")

    def test_community_postgres_sync_captures_promoted_identity_outside_generic_profile_quota_before_gear_build(self):
        from server import postgres_cache_sync, raiderio_payload

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "synced",
            "status": "synced",
            "checkedAt": "generic-profile-cache",
            "profiles": [
                {
                    "name": "GenericQuotaWinner",
                    "region": "cn",
                    "realmSlug": "generic-realm",
                    "classKey": "mage",
                    "specKey": "frost",
                    "gear": [{"slot": "head", "itemId": 1}],
                }
            ],
            "profileCount": 1,
        }
        elected_identity = "raiderio:cn|isillien|electedwinner"
        promoted = {
            "id": "promoted-mage-frost-frostfire",
            "sourceKey": "raiderio",
            "sourceName": "Raider.IO",
            "classKey": "mage",
            "specKey": "frost",
            "heroKey": "frostfire",
            "scenarioKey": "mythic_plus",
            "status": "verified",
            "payload": {
                "gearProjectionCandidates": [
                    {
                        "candidateId": "elected-mage-frost-frostfire",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "sourceKey": "raiderio",
                        "sourceIdentity": elected_identity,
                        "talentCandidateRank": 1,
                    }
                ]
            },
        }
        fetch_calls = []
        build_observations = []

        def fake_replace(_templates, scan_run_id="", include_details=False, target_slot_ids=None):
            store.coverage_rows = [promoted]
            return {
                "total": 1,
                "verified": 1,
                "partial": 0,
                "blocked": 0,
                "promotedTemplates": [promoted],
            }

        def fake_fetch(character, fields):
            fetch_calls.append((dict(character), fields))
            return {
                "name": "ElectedWinner",
                "region": "cn",
                "realmSlug": "isillien",
                "classKey": "mage",
                "specKey": "frost",
                "profileUrl": "https://raider.io/characters/cn/isillien/electedwinner",
                "gear": [{"slot": "head", "itemId": 222001}],
            }

        def fake_build_gear_templates(scan_run_id=""):
            build_observations.append(
                {
                    "profiles": list(store.raiderio_payload.get("profiles") or []),
                    "backfillCount": len(store.observed_backfills),
                }
            )
            return []

        store.replace_community_talent_templates = fake_replace
        store.build_community_gear_templates = fake_build_gear_templates
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [promoted],
                "errors": [],
            },
            "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
        ), patch.object(
            raiderio_payload,
            "fetch_profile_for_character",
            side_effect=fake_fetch,
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(
                store=store,
                refresh_raiderio=False,
            )

        self.assertEqual(fetch_calls[0][0]["sourceIdentity"], elected_identity)
        self.assertEqual(fetch_calls[0][1], "gear")
        self.assertEqual(store.raiderio_payload["profiles"][0]["name"], "ElectedWinner")
        self.assertEqual(store.raiderio_payload["profileCount"], 2)
        self.assertEqual(store.raiderio_payload["gearProjectionProfileCapture"]["requestedIdentityCount"], 1)
        self.assertEqual(store.observed_backfills[0]["payload"]["profiles"][0]["name"], "ElectedWinner")
        self.assertEqual(store.observed_backfills[0]["targetLimit"], 1280)
        self.assertEqual(store.observed_backfills[0]["profileLimit"], 1)
        self.assertEqual(store.observed_backfills[0]["timeoutSeconds"], 600)
        self.assertEqual(build_observations, [{"profiles": store.raiderio_payload["profiles"], "backfillCount": 1}])
        self.assertEqual(payload["gearProfileCapture"]["capturedProfileCount"], 1)

    def test_community_postgres_missing_slots_captures_and_backfills_persisted_projection_identity(self):
        from server import postgres_cache_sync, raiderio_payload

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        identity = "raiderio:cn|isillien|missingwinner"
        promoted = {
            "id": "rio-frost-frostfire-new",
            "sourceKey": "raiderio",
            "sourceName": "Raider.IO",
            "classKey": "mage",
            "specKey": "frost",
            "heroKey": "frostfire",
            "scenarioKey": "mythic_plus",
            "talentState": {"selectedNodes": [{"id": "node-frostfire", "rank": 1}]},
            "status": "verified",
            "payload": {
                "gearProjectionCandidates": [{
                    "candidateId": "rio-frost-frostfire-new",
                    "sourceIdentity": identity,
                    "talentCandidateRank": 1,
                }]
            },
        }

        def fake_replace(_templates, scan_run_id="", include_details=False, target_slot_ids=None):
            store.coverage_rows = [promoted]
            store.talent_replace_target_slot_ids = list(target_slot_ids or [])
            return {
                "total": 1,
                "verified": 1,
                "partial": 0,
                "blocked": 0,
                "promotedTemplates": [promoted],
            }

        store.replace_community_talent_templates = fake_replace
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [promoted],
                "errors": [],
            },
            "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }

        def fake_fetch(character, fields):
            self.assertEqual(character["sourceIdentity"], identity)
            self.assertEqual(fields, "gear")
            return {
                "name": "MissingWinner",
                "region": "cn",
                "realmSlug": "isillien",
                "gear": [{"slot": "head", "itemId": 222001}],
            }

        with patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            return_value={"sourceStatus": "verified", "runCount": 1, "profileCount": 1},
        ), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
        ), patch.object(
            raiderio_payload,
            "fetch_profile_for_character",
            side_effect=fake_fetch,
        ) as fetch:
            payload = postgres_cache_sync.sync_community_template_cache_postgres(
                store=store,
                mode="missing_slots",
            )

        fetch.assert_called_once()
        self.assertIn("mage:frost:frostfire", store.talent_replace_target_slot_ids)
        self.assertEqual(store.raiderio_payload["profiles"][0]["sourceIdentity"], identity)
        self.assertEqual(len(store.observed_backfills), 1)
        self.assertEqual(store.observed_backfills[0]["payload"]["profiles"][0]["sourceIdentity"], identity)
        self.assertEqual(payload["gearProfileCapture"]["capturedProfileCount"], 1)


    def test_community_postgres_sync_records_raiderio_failure_without_replacing_winners(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        recorded = []
        store.record_community_talent_source_sync_failure = lambda source_key, checked_at="", errors=None, regions=None: recorded.append(
            {"sourceKey": source_key, "checkedAt": checked_at, "errors": list(errors or []), "regions": list(regions or [])}
        ) or {"updated": 1}
        successful = []
        store.record_community_talent_source_sync_success = lambda source_key, checked_at="", regions=None: successful.append(
            {"sourceKey": source_key, "checkedAt": checked_at, "regions": list(regions or [])}
        ) or {"updated": 1}

        with patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            return_value={"sourceStatus": "partial", "status": "partial"},
        ), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value={
                "raiderio": {
                    "status": "blocked",
                    "sourceName": "Raider.IO",
                    "templates": [],
                    "errors": ["kr: upstream timeout"],
                    "regions": ["kr", "us"],
                    "regionCoverage": {"kr": {"status": "blocked"}, "us": {"status": "verified"}},
                },
                "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
            },
            create=True,
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store)

        self.assertEqual(recorded[0]["sourceKey"], "raiderio")
        self.assertEqual(recorded[0]["errors"], ["kr: upstream timeout"])
        self.assertEqual(recorded[0]["regions"], ["kr"])
        self.assertEqual(successful[0]["regions"], ["us"])
        self.assertEqual(payload["talentFreshness"]["raiderio"]["status"], "failure_recorded")
        self.assertEqual(payload["talentFreshness"]["raiderio"]["regionCoverage"]["us"]["status"], "verified")

    def test_community_talent_freshness_does_not_refresh_when_collection_was_skipped(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        success_calls = []
        failure_calls = []
        store.record_community_talent_source_sync_success = lambda *args, **kwargs: success_calls.append((args, kwargs))
        store.record_community_talent_source_sync_failure = lambda *args, **kwargs: failure_calls.append((args, kwargs))

        freshness = postgres_cache_sync._community_talent_source_freshness_maintenance(
            store,
            {
                "raiderio": {
                    "status": "synced",
                    "regionCoverage": {"kr": {"status": "synced"}},
                }
            },
            "2026-07-20T00:00:00+00:00",
            collection_attempted=False,
        )

        self.assertEqual(success_calls, [])
        self.assertEqual(failure_calls, [])
        self.assertEqual(freshness["raiderio"]["status"], "not_attempted")

    def test_missing_slots_sync_does_not_refresh_freshness_when_every_slot_is_already_covered(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        success_calls = []
        failure_calls = []
        store.record_community_talent_source_sync_success = lambda *args, **kwargs: success_calls.append((args, kwargs))
        store.record_community_talent_source_sync_failure = lambda *args, **kwargs: failure_calls.append((args, kwargs))

        with patch.object(postgres_cache_sync, "_community_talent_missing_slot_ids", return_value=[]), patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            side_effect=AssertionError("complete coverage must skip Raider.IO collection"),
        ), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value={"raiderio": {"status": "synced", "templates": [], "regionCoverage": {"kr": {"status": "synced"}}}},
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, mode="missing_slots")

        self.assertEqual(success_calls, [])
        self.assertEqual(failure_calls, [])
        self.assertEqual(payload["talentFreshness"]["raiderio"]["status"], "not_attempted")

    def test_failed_raiderio_collection_keeps_existing_winners_and_records_failure(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.community_talent_templates = [{"id": "existing-winner"}]
        failures = []
        store.record_community_talent_source_sync_failure = lambda source_key, checked_at="", errors=None, regions=None: failures.append(
            {"sourceKey": source_key, "errors": list(errors or []), "regions": list(regions or [])}
        ) or {"updated": 1}

        with patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            return_value={"sourceStatus": "stale", "errors": ["all regions failed"]},
        ), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value={
                "raiderio": {
                    "status": "synced",
                    "templates": [{"id": "old-cache-template", "status": "verified"}],
                    "regionCoverage": {"kr": {"status": "synced"}},
                }
            },
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store)

        self.assertEqual(store.community_talent_templates, [{"id": "existing-winner"}])
        self.assertEqual(failures, [{"sourceKey": "raiderio", "errors": ["all regions failed"], "regions": []}])
        self.assertEqual(payload["talentFreshness"]["raiderio"]["status"], "failure_recorded")

    def test_websim_postgres_sync_replaces_simc_generated_data(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        simc_data = complete_simc_candidate()

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=simc_data), patch.object(
            postgres_cache_sync,
            "expected_spec_pairs",
            return_value=["mage:frost"],
        ), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIs(store.replaced_data, simc_data)
        self.assertEqual(payload["simc"]["talents"], 15)
        self.assertEqual(payload["simc"]["profiles"], 1)
        self.assertEqual(payload["simc"]["build"], "simc-build")
        self.assertEqual(store.saved_states[-1][0], "websim_sync")
        self.assertEqual(store.saved_states[-1][1]["runner"], "postgres")

    def test_websim_postgres_sync_preserves_current_talents_when_trait_edges_are_missing(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        edge_less_simc_data = complete_simc_candidate()
        for talent in edge_less_simc_data["talents"]:
            talent["payload"]["parentIds"] = []
        edge_less_simc_data.update(
            {
                "dependencies": 0,
                "traitEdgeSource": "",
                "traitEdgeError": "TimeoutError: TraitEdge request timed out",
            }
        )

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=edge_less_simc_data):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertEqual(payload["simc"]["talents"], 0)
        self.assertIn("talent dependency edges are unavailable", payload["simc"]["errors"][0])
        self.assertIn("TraitEdge request timed out", payload["simc"]["errors"][0])
        self.assertIn("talent dependency edges are unavailable", payload["errors"][0])

    def test_websim_postgres_sync_blocks_dependency_count_without_parent_ids(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        simc_data = complete_simc_candidate()
        for talent in simc_data["talents"]:
            talent["payload"]["parentIds"] = []
        simc_data["dependencies"] = 1

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=simc_data):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertEqual(
            payload["simc"]["errors"],
            [
                "SimulationCraft talent dependency edges are unavailable; "
                "preserving the current PostgreSQL talent tree"
            ],
        )

    def test_websim_postgres_sync_blocks_parent_ids_without_trait_edge_source(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        simc_data = complete_simc_candidate()
        simc_data["traitEdgeSource"] = ""

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=simc_data):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertIn("talent dependency edges are unavailable", payload["simc"]["errors"][0])

    def test_websim_postgres_sync_preserves_current_talents_when_simc_candidate_is_empty(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        empty_simc_data = {
            "talents": [],
            "presets": [],
            "spellDetails": [],
            "source": "simc",
            "build": "simc-build",
            "dependencies": 0,
            "traitEdgeSource": "",
        }

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=empty_simc_data):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertEqual(payload["simc"]["talents"], 0)
        self.assertIn("talent catalog is empty", payload["simc"]["errors"][0])
        self.assertIn("talent catalog is empty", payload["errors"][0])

    def test_websim_postgres_sync_blocks_empty_candidate_without_source(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        empty_simc_data = {
            "talents": [],
            "presets": [],
            "spellDetails": [],
            "source": "",
            "extractionError": "TimeoutError: SimulationCraft download timed out",
        }

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=empty_simc_data):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertFalse(payload["ok"])
        self.assertIn("talent catalog is empty", payload["simc"]["errors"][0])
        self.assertIn("SimulationCraft download timed out", payload["simc"]["errors"][0])

    def test_websim_postgres_sync_blocks_truncated_trait_edge_coverage(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        simc_data = complete_simc_candidate(nodes_per_context=100)
        for talent in simc_data["talents"]:
            talent["payload"]["parentIds"] = []
        simc_data["talents"][1]["payload"]["parentIds"] = [simc_data["talents"][0]["id"]]
        simc_data["dependencies"] = 1

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=simc_data), patch.object(
            postgres_cache_sync,
            "expected_spec_pairs",
            return_value=["mage:frost"],
        ), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertFalse(payload["ok"])
        self.assertIn("dependency coverage is incomplete", payload["simc"]["errors"][0])

    def test_websim_postgres_sync_blocks_missing_spec_coverage(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        simc_data = complete_simc_candidate()

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=simc_data), patch.object(
            postgres_cache_sync,
            "expected_spec_pairs",
            return_value=["mage:frost", "warrior:arms"],
        ), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger", "warrior:arms:slayer"],
        ):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertIn("specialization coverage is incomplete", payload["simc"]["errors"][0])

    def test_websim_postgres_sync_blocks_empty_profile_presets(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        simc_data = complete_simc_candidate()
        simc_data["presets"] = []

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=simc_data), patch.object(
            postgres_cache_sync,
            "expected_spec_pairs",
            return_value=["mage:frost"],
        ), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertIn("profile preset coverage is incomplete", payload["simc"]["errors"][0])

    def test_websim_postgres_sync_blocks_candidate_below_previous_baseline(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.websim_sync_state = {
            "simc": {
                "talents": 20,
                "profiles": 1,
                "dependencies": 12,
                "build": "previous-build",
            }
        }
        simc_data = complete_simc_candidate()

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=simc_data), patch.object(
            postgres_cache_sync,
            "expected_spec_pairs",
            return_value=["mage:frost"],
        ), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertIn("fell below the last-known-good baseline", payload["simc"]["errors"][0])

    def test_websim_postgres_sync_keeps_baseline_after_repeated_rejection(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.websim_sync_state = {
            "simc": {
                "talents": 20,
                "profiles": 1,
                "dependencies": 12,
                "build": "previous-build",
                "source": "previous-source",
                "traitEdgeSource": "previous-edges",
            }
        }
        simc_data = complete_simc_candidate()

        for _attempt in range(2):
            with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value=simc_data), patch.object(
                postgres_cache_sync,
                "expected_spec_pairs",
                return_value=["mage:frost"],
            ), patch.object(
                postgres_cache_sync,
                "expected_hero_tree_triplets",
                return_value=["mage:frost:spellslinger"],
            ):
                payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

            self.assertIsNone(store.replaced_data)
            self.assertEqual(payload["simc"]["talents"], 20)
            self.assertEqual(payload["simc"]["build"], "previous-build")
            self.assertIn("fell below the last-known-good baseline", payload["simc"]["errors"][0])
            store.websim_sync_state = payload

    def test_websim_postgres_sync_recovers_live_pg_baseline_when_sync_state_is_missing(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        good_candidate = complete_simc_candidate()
        store.simc_graph_baseline = simc_graph_baseline(good_candidate)
        rejected_candidate = complete_simc_candidate()
        rejected_candidate["presets"] = []

        with patch.object(
            postgres_cache_sync,
            "extract_simc_generated_data",
            return_value=rejected_candidate,
        ), patch.object(
            postgres_cache_sync,
            "expected_spec_pairs",
            return_value=["mage:frost"],
        ), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            payload = postgres_cache_sync.sync_websim_cache_postgres(store=store)

        self.assertIsNone(store.replaced_data)
        self.assertEqual(payload["simc"]["talents"], len(good_candidate["talents"]))
        self.assertEqual(payload["simc"]["dependencies"], good_candidate["dependencies"])
        self.assertEqual(payload["simc"]["dependencyNodes"], good_candidate["dependencies"])
        self.assertEqual(payload["simc"]["profiles"], 1)
        self.assertEqual(payload["simc"]["profileSpecCoverage"], 1)
        self.assertIn("profile preset coverage is incomplete", payload["simc"]["errors"][0])

    def test_simc_candidate_validation_accepts_complete_expected_matrix(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)

        counts = postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

        self.assertEqual(counts["specCoverage"], 40)
        self.assertEqual(counts["heroCoverage"], 80)
        self.assertEqual(counts["dependencies"], simc_data["dependencies"])
        self.assertEqual(counts["dependencyNodes"], simc_data["dependencies"])

    def test_simc_candidate_validation_accepts_profile_pack_with_known_spec_gaps(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)
        missing_profile_specs = set(spec_pairs[-7:])
        simc_data["presets"] = [
            preset
            for preset in simc_data["presets"]
            if f"{preset['classKey']}:{preset['specKey']}" not in missing_profile_specs
        ]
        while len(simc_data["presets"]) < 50:
            duplicate = dict(simc_data["presets"][len(simc_data["presets"]) % 10])
            duplicate["id"] = f"{duplicate['id']}-variant-{len(simc_data['presets'])}"
            simc_data["presets"].append(duplicate)

        counts = postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

        self.assertEqual(counts["profiles"], 50)

    def test_simc_candidate_validation_rejects_duplicate_single_spec_profiles(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)
        seed = dict(simc_data["presets"][0])
        simc_data["presets"] = [{**seed, "id": f"duplicate-{index}"} for index in range(50)]

        with self.assertRaisesRegex(RuntimeError, "profile preset coverage is incomplete"):
            postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_empty_profile_payload(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        simc_data["presets"][0]["profile"] = ""

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "profile preset payload is invalid"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_single_truncated_hero_context(self):
        from server import postgres_cache_sync

        heroes = ("mage:frost:spellslinger", "mage:frost:frostfire")
        simc_data = complete_simc_candidate(("mage:frost",), heroes, nodes_per_context=20)
        baseline = simc_graph_baseline(simc_data)
        truncated_hero = [
            talent
            for talent in simc_data["talents"]
            if (talent.get("payload") or {}).get("heroKey") == "frostfire"
        ]
        keep_ids = {talent["id"] for talent in truncated_hero[:5]}
        simc_data["talents"] = [
            talent
            for talent in simc_data["talents"]
            if (talent.get("payload") or {}).get("heroKey") != "frostfire" or talent["id"] in keep_ids
        ]
        simc_data["dependencies"] = sum(
            len((talent.get("payload") or {}).get("parentIds") or []) for talent in simc_data["talents"]
        )

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=list(heroes),
        ):
            with self.assertRaisesRegex(RuntimeError, "tree context fell below"):
                postgres_cache_sync.validate_simc_generated_data_candidate(
                    simc_data,
                    {"graphBaseline": baseline},
                )

    def test_simc_candidate_validation_allows_cross_source_legacy_visual_slot_deduplication(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        baseline_candidate = json.loads(json.dumps(simc_data))
        hero_nodes = [
            talent
            for talent in baseline_candidate["talents"]
            if talent.get("treeType") == "hero"
        ]
        root = hero_nodes[0]
        legacy_root = json.loads(json.dumps(root))
        legacy_root["id"] = f"{root['id']}-legacy-duplicate"
        legacy_root["spellId"] = 199001
        legacy_root["name"] = "Legacy duplicate root"
        legacy_payload = legacy_root["payload"]
        legacy_payload.update({"nodeId": 99001, "traitId": 99101, "traitDefinitionId": 99201})
        legacy_payload["rankEntries"] = [{
            **legacy_payload["rankEntries"][0],
            "traitId": 99101,
            "traitDefinitionId": 99201,
            "spellId": 199001,
        }]
        baseline_candidate["talents"].append(legacy_root)
        for talent in hero_nodes[1:]:
            talent["payload"]["parentIds"].append(legacy_root["id"])
        baseline_candidate["dependencies"] = sum(
            len((talent.get("payload") or {}).get("parentIds") or [])
            for talent in baseline_candidate["talents"]
        )
        baseline = simc_graph_baseline(baseline_candidate)
        baseline["dependencies"] = simc_data["dependencies"]
        hero_context = next(
            row for row in baseline["contexts"]
            if row["treeType"] == "hero" and row["heroKey"] == "spellslinger"
        )
        hero_context["visualSlots"] = [{
            "row": root["row"],
            "col": root["col"],
            "nodeIds": [root["id"], legacy_root["id"]],
        }]
        simc_data["source"] = "new-simc-source"

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            counts = postgres_cache_sync.validate_simc_generated_data_candidate(
                simc_data,
                {
                    "simc": {"source": "old-simc-source"},
                    "graphBaseline": baseline,
                },
            )

        self.assertEqual(counts["dependencies"], simc_data["dependencies"])

    def test_simc_candidate_validation_allows_legacy_foreign_hero_spec_cleanup(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        baseline_candidate = json.loads(json.dumps(simc_data))
        hero_nodes = [
            talent
            for talent in baseline_candidate["talents"]
            if talent.get("treeType") == "hero"
        ]
        root = hero_nodes[0]
        foreign_root = json.loads(json.dumps(root))
        foreign_root["id"] = f"{root['id']}-foreign-hero-variant"
        foreign_root["spellId"] = 199101
        foreign_root["name"] = "Foreign hero variant"
        foreign_payload = foreign_root["payload"]
        foreign_payload.update({
            "nodeId": 99101,
            "traitId": 99201,
            "traitDefinitionId": 99301,
            "choiceGroup": "legacy-foreign-variant",
            "shape": "choice",
        })
        foreign_payload["rankEntries"] = [{
            **foreign_payload["rankEntries"][0],
            "traitId": 99201,
            "traitDefinitionId": 99301,
            "spellId": 199101,
        }]
        baseline_candidate["talents"].append(foreign_root)
        for talent in hero_nodes[1:]:
            talent["payload"]["parentIds"].append(foreign_root["id"])
        baseline_candidate["dependencies"] = sum(
            len((talent.get("payload") or {}).get("parentIds") or [])
            for talent in baseline_candidate["talents"]
        )
        baseline = simc_graph_baseline(baseline_candidate)
        baseline["dependencies"] = simc_data["dependencies"]
        hero_context = next(
            row for row in baseline["contexts"]
            if row["treeType"] == "hero" and row["heroKey"] == "spellslinger"
        )
        hero_context["foreignSpecNodeIds"] = [foreign_root["id"]]
        simc_data["source"] = "new-simc-source"

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            counts = postgres_cache_sync.validate_simc_generated_data_candidate(
                simc_data,
                {
                    "simc": {"source": "old-simc-source"},
                    "graphBaseline": baseline,
                },
            )

        self.assertEqual(counts["dependencies"], simc_data["dependencies"])

    def test_simc_candidate_validation_rejects_tree_identity_mismatch(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        hero_talent = next(
            talent for talent in simc_data["talents"] if talent.get("treeType") == "hero"
        )
        hero_talent["payload"]["treeType"] = "spec"

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "tree identity is inconsistent"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_wrong_tree_id(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        simc_data["talents"][0]["treeId"] = "spec:mage:frost"

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "tree identity is inconsistent"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_empty_source(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        simc_data["source"] = ""

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "source identity is missing"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_duplicate_talent_id(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        simc_data["talents"][1]["id"] = simc_data["talents"][0]["id"]

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "talent identifiers are invalid"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_duplicate_preset_id(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        simc_data["presets"].append(dict(simc_data["presets"][0]))

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "profile preset payload is invalid"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_allows_same_build_growth(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        previous_state = {
            "simc": {
                "build": simc_data["build"],
                "source": simc_data["source"],
                "talents": len(simc_data["talents"]) - 1,
                "profiles": len(simc_data["presets"]),
                "dependencies": simc_data["dependencies"] - 1,
                "dependencyNodes": simc_data["dependencies"] - 1,
            }
        }

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            counts = postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

        self.assertEqual(counts["profileSpecCoverage"], 1)

    def test_simc_candidate_validation_rejects_same_build_decline(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        previous_state = {
            "simc": {
                "build": simc_data["build"],
                "source": simc_data["source"],
                "talents": len(simc_data["talents"]) + 1,
                "profiles": len(simc_data["presets"]),
                "dependencies": simc_data["dependencies"],
                "dependencyNodes": simc_data["dependencies"],
            }
        }

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "same-source baseline"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

    def test_simc_candidate_validation_rejects_same_build_profile_spec_decline(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)
        retained = list(simc_data["presets"][:32])
        while len(retained) < 40:
            duplicate = dict(retained[len(retained) % 8])
            duplicate["id"] = f"{duplicate['id']}-variant-{len(retained)}"
            retained.append(duplicate)
        simc_data["presets"] = retained
        previous_state = {
            "simc": {
                "build": simc_data["build"],
                "source": simc_data["source"],
                "talents": len(simc_data["talents"]),
                "profiles": 40,
                "profileSpecCoverage": 40,
                "dependencies": simc_data["dependencies"],
                "dependencyNodes": simc_data["dependencies"],
            }
        }

        with self.assertRaisesRegex(RuntimeError, "profileSpecCoverage declined from 40 to 32"):
            postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

    def test_simc_candidate_validation_rejects_same_source_profile_spec_swap(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)
        previous_profile_specs = list(spec_pairs[:32])
        candidate_profile_specs = set(spec_pairs[1:33])
        simc_data["presets"] = [
            preset
            for preset in simc_data["presets"]
            if f"{preset['classKey']}:{preset['specKey']}" in candidate_profile_specs
        ]
        previous_state = {
            "simc": {"source": simc_data["source"]},
            "graphBaseline": {
                "profileSpecCoverage": 32,
                "profileSpecs": previous_profile_specs,
                "contexts": [],
            },
        }

        with self.assertRaisesRegex(RuntimeError, "profile specialization set declined"):
            postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

    def test_simc_candidate_validation_rejects_same_source_live_profile_count_decline(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)
        retained_profile_specs = set(spec_pairs[:32])
        simc_data["presets"] = [
            preset
            for preset in simc_data["presets"]
            if f"{preset['classKey']}:{preset['specKey']}" in retained_profile_specs
        ]
        previous_state = {
            "simc": {"source": simc_data["source"]},
            "graphBaseline": {
                "profiles": 50,
                "profileSpecCoverage": 32,
                "profileSpecs": sorted(retained_profile_specs),
                "contexts": [],
            },
        }

        with self.assertRaisesRegex(RuntimeError, "profiles declined from 50 to 32"):
            postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

    def test_simc_candidate_validation_rejects_same_source_profile_content_replacement(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        baseline = simc_graph_baseline(simc_data)
        simc_data["presets"][0]["profile"] += "\n# replaced content"

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "profile content identities declined"):
                postgres_cache_sync.validate_simc_generated_data_candidate(
                    simc_data,
                    {
                        "simc": {"source": simc_data["source"]},
                        "graphBaseline": baseline,
                    },
                )

    def test_simc_candidate_validation_allows_same_source_profile_id_rekey_with_preserved_content(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        baseline = simc_graph_baseline(simc_data)
        simc_data["presets"][0]["id"] = "preset-mage-frost-content-hash"

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            counts = postgres_cache_sync.validate_simc_generated_data_candidate(
                simc_data,
                {
                    "simc": {"source": simc_data["source"]},
                    "graphBaseline": baseline,
                },
            )

        self.assertEqual(counts["profiles"], 1)

    def test_simc_candidate_validation_allows_same_source_profile_growth_with_rekeyed_ids(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        base_preset = simc_data["presets"][0]
        simc_data["presets"] = [
            {
                **base_preset,
                "id": f"preset-old-{index}",
                "profile": f"{base_preset['profile']}\n# variant {index}",
            }
            for index in range(49)
        ]
        baseline = simc_graph_baseline(simc_data)
        for index, preset in enumerate(simc_data["presets"]):
            preset["id"] = f"preset-rekeyed-{index}"
        simc_data["presets"].append(
            {
                **base_preset,
                "id": "preset-new-49",
                "profile": f"{base_preset['profile']}\n# variant 49",
            }
        )

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            counts = postgres_cache_sync.validate_simc_generated_data_candidate(
                simc_data,
                {
                    "simc": {"source": simc_data["source"]},
                    "graphBaseline": baseline,
                },
            )

        self.assertEqual(counts["profiles"], 50)

    def test_simc_candidate_validation_rejects_cross_source_profile_spec_retention_below_threshold(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)
        previous_profile_specs = list(spec_pairs[:32])
        candidate_profile_specs = set(spec_pairs[-32:])
        simc_data["source"] = "new-simc-source"
        simc_data["presets"] = [
            preset
            for preset in simc_data["presets"]
            if f"{preset['classKey']}:{preset['specKey']}" in candidate_profile_specs
        ]
        previous_state = {
            "simc": {"source": "old-simc-source"},
            "graphBaseline": {
                "profileSpecCoverage": 32,
                "profileSpecs": previous_profile_specs,
                "contexts": [],
            },
        }

        with self.assertRaisesRegex(RuntimeError, "profile specialization identities fell below"):
            postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

    def test_simc_candidate_validation_allows_cross_source_profile_spec_retention_at_threshold(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)
        candidate_profile_specs = set(spec_pairs[:32])
        simc_data["source"] = "new-simc-source"
        simc_data["presets"] = [
            preset
            for preset in simc_data["presets"]
            if f"{preset['classKey']}:{preset['specKey']}" in candidate_profile_specs
        ]
        previous_state = {
            "simc": {"source": "old-simc-source"},
            "graphBaseline": {
                "profileSpecCoverage": 40,
                "profileSpecs": list(spec_pairs),
                "contexts": [],
            },
        }

        counts = postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

        self.assertEqual(counts["profileSpecCoverage"], 32)

    def test_simc_candidate_validation_rejects_cross_source_live_profile_count_below_threshold(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)
        retained_profile_specs = set(spec_pairs[:32])
        simc_data["source"] = "new-simc-source"
        simc_data["presets"] = [
            preset
            for preset in simc_data["presets"]
            if f"{preset['classKey']}:{preset['specKey']}" in retained_profile_specs
        ]
        while len(simc_data["presets"]) < 39:
            duplicate = dict(simc_data["presets"][len(simc_data["presets"]) % 32])
            duplicate["id"] = f"{duplicate['id']}-variant-{len(simc_data['presets'])}"
            simc_data["presets"].append(duplicate)
        previous_state = {
            "simc": {"source": "old-simc-source"},
            "graphBaseline": {
                "profiles": 50,
                "profileSpecCoverage": 32,
                "profileSpecs": sorted(retained_profile_specs),
                "contexts": [],
            },
        }

        with self.assertRaisesRegex(RuntimeError, "profiles retained 39/50"):
            postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

    def test_simc_candidate_validation_allows_cross_source_live_profile_count_at_threshold(self):
        from server import postgres_cache_sync

        spec_pairs = tuple(postgres_cache_sync.expected_spec_pairs())
        hero_triplets = tuple(postgres_cache_sync.expected_hero_tree_triplets())
        simc_data = complete_simc_candidate(spec_pairs, hero_triplets)
        retained_profile_specs = set(spec_pairs[:32])
        simc_data["source"] = "new-simc-source"
        simc_data["presets"] = [
            preset
            for preset in simc_data["presets"]
            if f"{preset['classKey']}:{preset['specKey']}" in retained_profile_specs
        ]
        while len(simc_data["presets"]) < 40:
            duplicate = dict(simc_data["presets"][len(simc_data["presets"]) % 32])
            duplicate["id"] = f"{duplicate['id']}-variant-{len(simc_data['presets'])}"
            simc_data["presets"].append(duplicate)
        previous_state = {
            "simc": {"source": "old-simc-source"},
            "graphBaseline": {
                "profiles": 50,
                "profileSpecCoverage": 32,
                "profileSpecs": sorted(retained_profile_specs),
                "contexts": [],
            },
        }

        counts = postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

        self.assertEqual(counts["profiles"], 40)

    def test_simc_candidate_validation_allows_profile_variant_count_decline(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        previous_state = {
            "simc": {
                "build": simc_data["build"],
                "source": simc_data["source"],
                "talents": len(simc_data["talents"]),
                "profiles": len(simc_data["presets"]) + 1,
                "profileSpecCoverage": 1,
                "dependencies": simc_data["dependencies"],
                "dependencyNodes": simc_data["dependencies"],
            }
        }

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            counts = postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

        self.assertEqual(counts["profiles"], 1)

    def test_simc_candidate_validation_allows_same_source_monotonic_edge_recovery(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        incomplete = complete_simc_candidate()
        for talent in simc_data["talents"]:
            if talent["payload"]["parentIds"]:
                talent["payload"]["dependencySource"] = "wago-db2-traitedge"
        for talent in incomplete["talents"]:
            talent["payload"]["parentIds"] = []
            talent["payload"].pop("parentMode", None)
            talent["payload"].pop("dependencySource", None)
        incomplete["dependencies"] = 0
        baseline = simc_graph_baseline(incomplete)

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            counts = postgres_cache_sync.validate_simc_generated_data_candidate(
                simc_data,
                {
                    "simc": {"source": simc_data["source"], "build": simc_data["build"]},
                    "graphBaseline": baseline,
                },
            )

        self.assertEqual(counts["dependencies"], simc_data["dependencies"])

    def test_simc_candidate_validation_allows_same_source_self_override_node_recovery(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        baseline = simc_graph_baseline(simc_data)
        hero_nodes = [
            talent
            for talent in simc_data["talents"]
            if talent.get("treeType") == "hero"
        ]
        root = hero_nodes[0]
        recovered = json.loads(json.dumps(root))
        recovered["id"] = f"{root['id']}-self-override-recovery"
        recovered["row"] = 6
        recovered["spellId"] = 199201
        recovered["name"] = "Recovered self override"
        recovered_payload = recovered["payload"]
        recovered_payload.update({
            "nodeId": 99201,
            "traitId": 99301,
            "traitDefinitionId": 99401,
            "overrideSpellId": 199201,
            "parentIds": [root["id"]],
        })
        recovered_payload["rankEntries"] = [{
            **recovered_payload["rankEntries"][0],
            "traitId": 99301,
            "traitDefinitionId": 99401,
            "spellId": 199201,
        }]
        simc_data["talents"].append(recovered)
        hero_nodes[-1]["payload"]["parentIds"].append(recovered["id"])
        simc_data["dependencies"] = sum(
            len((talent.get("payload") or {}).get("parentIds") or [])
            for talent in simc_data["talents"]
        )

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            counts = postgres_cache_sync.validate_simc_generated_data_candidate(
                simc_data,
                {
                    "simc": {"source": simc_data["source"]},
                    "graphBaseline": baseline,
                },
            )

        self.assertEqual(counts["dependencies"], simc_data["dependencies"])

    def test_simc_candidate_validation_allows_source_unknown_monotonic_edge_recovery(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        incomplete = complete_simc_candidate()
        for talent in incomplete["talents"]:
            talent["payload"]["parentIds"] = []
            talent["payload"].pop("parentMode", None)
            talent["payload"].pop("dependencySource", None)
        incomplete["dependencies"] = 0
        baseline = simc_graph_baseline(incomplete)

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            counts = postgres_cache_sync.validate_simc_generated_data_candidate(
                simc_data,
                {"graphBaseline": baseline},
            )

        self.assertEqual(counts["dependencies"], simc_data["dependencies"])

    def test_simc_candidate_validation_rejects_non_edge_change_during_same_source_recovery(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        incomplete = complete_simc_candidate()
        for talent in incomplete["talents"]:
            talent["payload"]["parentIds"] = []
        incomplete["dependencies"] = 0
        baseline = simc_graph_baseline(incomplete)
        simc_data["talents"][0]["payload"]["pointRequirement"] = 1

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "graph structure changed"):
                postgres_cache_sync.validate_simc_generated_data_candidate(
                    simc_data,
                    {
                        "simc": {"source": simc_data["source"], "build": simc_data["build"]},
                        "graphBaseline": baseline,
                    },
                )

    def test_simc_candidate_validation_rejects_non_monotonic_edge_recovery(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        incomplete = complete_simc_candidate()
        for tree_type in ("class", "spec", "hero"):
            context_nodes = [talent for talent in incomplete["talents"] if talent["treeType"] == tree_type]
            for talent in context_nodes:
                talent["payload"]["parentIds"] = []
            context_nodes[2]["payload"]["parentIds"] = [context_nodes[0]["id"]]
        incomplete["dependencies"] = 3
        baseline = simc_graph_baseline(incomplete)

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency recovery is not monotonic"):
                postgres_cache_sync.validate_simc_generated_data_candidate(
                    simc_data,
                    {
                        "simc": {"source": simc_data["source"], "build": simc_data["build"]},
                        "graphBaseline": baseline,
                    },
                )

    def test_simc_candidate_validation_rejects_same_source_graph_rewire(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        baseline = simc_graph_baseline(simc_data)
        for tree_type in ("class", "spec", "hero"):
            context_nodes = [talent for talent in simc_data["talents"] if talent["treeType"] == tree_type]
            root_id = context_nodes[0]["id"]
            for talent in context_nodes[1:]:
                talent["payload"]["parentIds"] = [root_id]

        previous_state = {
            "simc": {
                "build": simc_data["build"],
                "source": simc_data["source"],
            },
            "graphBaseline": baseline,
        }
        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "graph signature changed"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

    def test_simc_candidate_validation_rejects_same_source_layout_collapse(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        baseline = simc_graph_baseline(simc_data)
        for talent in simc_data["talents"]:
            talent["row"] = 1
            talent["col"] = 1

        previous_state = {
            "simc": {"source": simc_data["source"]},
            "graphBaseline": baseline,
        }
        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "graph structure changed"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

    def test_simc_candidate_validation_rejects_same_source_encoding_field_change(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        baseline = simc_graph_baseline(simc_data)
        simc_data["talents"][0]["payload"]["pointRequirement"] = 1

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "graph structure changed"):
                postgres_cache_sync.validate_simc_generated_data_candidate(
                    simc_data,
                    {
                        "simc": {"source": simc_data["source"]},
                        "graphBaseline": baseline,
                    },
                )

    def test_simc_candidate_validation_rejects_same_source_persisted_content_changes(self):
        from server import postgres_cache_sync

        baseline_candidate = complete_simc_candidate()
        baseline = simc_graph_baseline(baseline_candidate)
        mutations = (
            ("name", lambda talent: talent.__setitem__("name", "Changed Talent Name")),
            (
                "traitDefinitionId",
                lambda talent: talent["payload"].__setitem__(
                    "traitDefinitionId",
                    int(talent["payload"]["traitDefinitionId"]) + 1,
                ),
            ),
            ("heroLabel", lambda talent: talent["payload"].__setitem__("heroLabel", "Changed Hero Label")),
            (
                "rankEntryName",
                lambda talent: talent["payload"]["rankEntries"][0].__setitem__(
                    "name",
                    "Changed Rank Entry Name",
                ),
            ),
        )

        for label, mutate in mutations:
            with self.subTest(field=label):
                simc_data = complete_simc_candidate()
                mutate(simc_data["talents"][0])
                with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
                    postgres_cache_sync,
                    "expected_hero_tree_triplets",
                    return_value=["mage:frost:spellslinger"],
                ):
                    with self.assertRaisesRegex(RuntimeError, "graph structure changed"):
                        postgres_cache_sync.validate_simc_generated_data_candidate(
                            simc_data,
                            {
                                "simc": {"source": simc_data["source"]},
                                "graphBaseline": baseline,
                            },
                        )

    def test_simc_candidate_validation_rejects_graph_rewire_when_source_state_is_missing(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        baseline = simc_graph_baseline(simc_data)
        for tree_type in ("class", "spec", "hero"):
            context_nodes = [talent for talent in simc_data["talents"] if talent["treeType"] == tree_type]
            root_id = context_nodes[0]["id"]
            for talent in context_nodes[1:]:
                talent["payload"]["parentIds"] = [root_id]

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "graph signature changed"):
                postgres_cache_sync.validate_simc_generated_data_candidate(
                    simc_data,
                    {"graphBaseline": baseline},
                )

    def test_simc_candidate_validation_rejects_cross_source_node_identity_collapse(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate(nodes_per_context=10)
        baseline = simc_graph_baseline(simc_data)
        class_nodes = [talent for talent in simc_data["talents"] if talent["treeType"] == "class"]
        id_map = {talent["id"]: f"replacement-{index}" for index, talent in enumerate(class_nodes[:3])}
        for talent in simc_data["talents"]:
            if talent["id"] in id_map:
                talent["id"] = id_map[talent["id"]]
            talent["payload"]["parentIds"] = [id_map.get(parent_id, parent_id) for parent_id in talent["payload"]["parentIds"]]
        simc_data["source"] = "new-simc-source"

        previous_state = {
            "simc": {"source": "old-simc-source"},
            "graphBaseline": baseline,
        }
        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "node identities fell below"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data, previous_state)

    def test_simc_candidate_validation_rejects_dependency_cycle(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        for tree_type in ("class", "spec", "hero"):
            context_nodes = [talent for talent in simc_data["talents"] if talent["treeType"] == tree_type]
            context_nodes[0]["payload"]["parentIds"] = [context_nodes[1]["id"]]
        simc_data["dependencies"] = sum(
            len((talent.get("payload") or {}).get("parentIds") or []) for talent in simc_data["talents"]
        )

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency cycle"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_noncanonical_identity_whitespace(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        for talent in simc_data["talents"]:
            talent["classKey"] = " mage "

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "identity is not canonical"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_non_array_parent_ids(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        class_root = simc_data["talents"][0]
        class_child = simc_data["talents"][1]
        old_root_id = class_root["id"]
        class_root["id"] = "x"
        class_child["payload"]["parentIds"] = "x"
        for talent in simc_data["talents"]:
            parent_ids = (talent.get("payload") or {}).get("parentIds")
            if isinstance(parent_ids, list):
                talent["payload"]["parentIds"] = ["x" if parent_id == old_root_id else parent_id for parent_id in parent_ids]

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "parentIds payload is invalid"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_empty_rank_entries(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        simc_data["talents"][0]["payload"]["rankEntries"] = []

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "rankEntries payload is invalid"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_invalid_rank_entry_identity(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        simc_data["talents"][0]["payload"]["rankEntries"][0]["spellId"] = 0

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "rankEntries payload is invalid"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_non_integer_rank_field_cleanly(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        simc_data["talents"][0]["payload"]["rank"] = "one"

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "rankEntries payload is invalid"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_unreadable_node_shape(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        talent = simc_data["talents"][0]
        talent["spellId"] = 0
        talent["row"] = 0
        talent["payload"]["nodeId"] = 0
        talent["payload"]["traitId"] = 0
        talent["payload"]["rankEntries"] = []

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "read-model shape is invalid"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_self_parent(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        simc_data["talents"][1]["payload"]["parentIds"] = [simc_data["talents"][1]["id"]]

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency references are invalid or duplicated"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_duplicate_parent(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        parent_id = simc_data["talents"][0]["id"]
        simc_data["talents"][1]["payload"]["parentIds"] = [parent_id, parent_id]
        simc_data["dependencies"] += 1

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency references are invalid or duplicated"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_simc_candidate_validation_rejects_cross_context_parent(self):
        from server import postgres_cache_sync

        simc_data = complete_simc_candidate()
        class_child = simc_data["talents"][1]
        spec_root = simc_data["talents"][5]
        class_child["payload"]["parentIds"] = [spec_root["id"]]

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "expected_hero_tree_triplets",
            return_value=["mage:frost:spellslinger"],
        ):
            with self.assertRaisesRegex(RuntimeError, "leave their tree context"):
                postgres_cache_sync.validate_simc_generated_data_candidate(simc_data)

    def test_websim_postgres_sync_writes_blizzard_journal_when_enabled(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        journal_data = {
            "season": {"seasonRevision": "season-pg-rev", "dataStatus": "verified", "dungeons": [{}]},
            "instances": [{"id": "1300", "encounters": [{"id": "9001", "items": [{"itemId": "111"}]}]}],
        }

        with patch.object(postgres_cache_sync, "extract_simc_generated_data", return_value={"talents": [], "presets": []}), patch.object(
            postgres_cache_sync,
            "fetch_websim_journal_data_postgres",
            return_value=journal_data,
        ):
            payload = postgres_cache_sync.sync_websim_cache_postgres(include_blizzard=True, store=store)

        self.assertIs(store.journal_data, journal_data)
        self.assertEqual(payload["blizzard"]["runner"], "postgres")
        self.assertEqual(payload["blizzard"]["loot"], 1)
        self.assertEqual(payload["gearCatalog"]["sourceCount"], 1)

    def test_refresh_websim_item_metadata_postgres_fetches_and_writes_item_ids(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        refs = [{"itemId": "249919", "name": "Sin'dorei Band of Hope", "slot": "finger2"}]

        def fake_fetch(token, item_id, region="us", locale="zh_CN", fallback_name="", fallback_slot=""):
            self.assertEqual(token, "token")
            self.assertEqual(item_id, "249919")
            self.assertEqual(fallback_name, "Sin'dorei Band of Hope")
            self.assertEqual(fallback_slot, "finger2")
            return {
                "itemId": "249919",
                "payload": {"id": 249919, "name": "辛多雷希望指环"},
                "media": {"assets": [{"key": "icon", "value": "https://render.worldofwarcraft.com/us/icons/56/inv_ring.jpg"}]},
                "englishPayload": {"name": "Sin'dorei Band of Hope"},
                "locale": "zh_CN",
                "fallbackName": fallback_name,
                "fallbackSlot": fallback_slot,
            }

        with patch.object(postgres_cache_sync, "fetch_blizzard_item_metadata", side_effect=fake_fetch):
            payload = postgres_cache_sync.refresh_websim_item_metadata_postgres(refs, token="token", store=store)

        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["requested"], 1)
        self.assertEqual(payload["items"], 1)
        self.assertEqual(payload["errors"], [])
        self.assertEqual(store.saved_item_metadata[0]["itemId"], "249919")
        self.assertEqual(store.saved_item_metadata[0]["fallbackSlot"], "finger2")
        self.assertEqual(store.saved_states[-1][0], "item_metadata_refresh")

    def test_refresh_websim_item_metadata_postgres_can_use_template_gap_audit(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.metadata_gaps = [
            {
                "itemId": "249343",
                "name": "Gaze of the Alnseer",
                "slot": "trinket1",
                "reasons": ["missing_icon"],
            }
        ]

        with patch.object(
            postgres_cache_sync,
            "fetch_blizzard_item_metadata",
            return_value={
                "itemId": "249343",
                "payload": {"id": 249343, "name": "艾尔西尔的凝视"},
                "media": {"assets": [{"key": "icon", "value": "https://render.worldofwarcraft.com/us/icons/56/inv_trinket.jpg"}]},
                "englishPayload": {"name": "Gaze of the Alnseer"},
                "locale": "zh_CN",
                "fallbackName": "Gaze of the Alnseer",
                "fallbackSlot": "trinket1",
            },
        ):
            payload = postgres_cache_sync.refresh_websim_item_metadata_gaps_postgres(limit=10, token="token", store=store)

        self.assertEqual(payload["gapCount"], 1)
        self.assertEqual(payload["items"], 1)
        self.assertEqual(store.saved_item_metadata[0]["itemId"], "249343")

    def test_refresh_websim_item_metadata_postgres_can_use_item_gap_audit(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.item_metadata_gaps = [
            {
                "itemId": "263193",
                "name": "Trollhunter's Bands",
                "slot": "wrist",
                "reasons": ["missing_icon", "missing_official_payload_shape"],
                "usageCount": 11,
            }
        ]

        with patch.object(
            postgres_cache_sync,
            "fetch_blizzard_item_metadata",
            return_value={
                "itemId": "263193",
                "payload": {"id": 263193, "name": "巨魔猎手腕带"},
                "media": {"assets": [{"key": "icon", "value": "https://render.worldofwarcraft.com/us/icons/56/inv_bracer.jpg"}]},
                "englishPayload": {"name": "Trollhunter's Bands"},
                "locale": "zh_CN",
                "fallbackName": "Trollhunter's Bands",
                "fallbackSlot": "wrist",
            },
        ):
            payload = postgres_cache_sync.refresh_websim_item_metadata_item_gaps_postgres(limit=10, token="token", store=store)

        self.assertEqual(payload["gapCount"], 1)
        self.assertEqual(payload["items"], 1)
        self.assertEqual(payload["gaps"][0]["usageCount"], 11)
        self.assertEqual(store.saved_item_metadata[0]["itemId"], "263193")

    def test_community_postgres_sync_saves_legacy_compatible_talent_state(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()

        with patch.object(postgres_cache_sync, "load_community_talent_sources_postgres", return_value={}):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        saved = {key: value for key, value, _updated_at in store.saved_states}

        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["runner"], "postgres")
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sourceStatus"], "partial")
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["templates"]["total"], 2)
        self.assertIn("checkedAt", saved[COMMUNITY_TALENT_SYNC_KEY])

    def test_community_postgres_sync_writes_talent_templates_from_sources(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-template-a",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "spellslinger",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {
                "status": "blocked",
                "sourceName": "Warcraft Logs",
                "templates": [
                    {
                        "id": "wcl-template-blocked",
                        "classKey": "mage",
                        "specKey": "frost",
                        "status": "blocked",
                        "payload": {"errors": ["missing report seed"]},
                    }
                ],
                "errors": ["missing report seed"],
            },
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        self.assertEqual(len(store.community_talent_templates), 2)
        self.assertEqual(
            {template["sourceKey"] for template in store.community_talent_templates},
            {"raiderio", "warcraftlogs"},
        )
        self.assertEqual(payload["talents"]["templates"]["verified"], 1)
        self.assertEqual(payload["talents"]["templates"]["blocked"], 1)
        self.assertEqual(payload["sourceStatus"], "partial")

    def test_community_postgres_sync_skips_stale_raiderio_spec_mismatch_templates(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-stale-mismatch",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAA",
                        "status": "verified",
                        "payload": {
                            "raiderio": {
                                "characterName": "Mageroysong",
                                "loadoutSpecId": 62,
                                "loadout": [{"traitId": 91001, "rank": 1}],
                            }
                        },
                    },
                    {
                        "id": "rio-frost-ok",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                        "status": "verified",
                        "payload": {"raiderio": {"characterName": "Frostok", "loadoutSpecId": 64}},
                    },
                ],
                "errors": [],
            }
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        self.assertEqual([template["id"] for template in store.community_talent_templates], ["rio-frost-ok"])
        self.assertEqual(payload["talents"]["templates"]["verified"], 1)
        self.assertEqual(payload["talents"]["templates"]["blocked"], 0)
        saved = {key: value for key, value, _updated_at in store.saved_states}
        self.assertIn("warnings", saved[COMMUNITY_TALENT_SYNC_KEY]["sources"]["raiderio"])
        self.assertIn("loadout spec id 62", saved[COMMUNITY_TALENT_SYNC_KEY]["sources"]["raiderio"]["warnings"][0])
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sources"]["raiderio"]["skippedCount"], 1)
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sources"]["raiderio"]["blockedCount"], 0)

    def test_community_postgres_sync_writes_full_hero_slot_coverage_matrix(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "regions": ["cn", "eu"],
                "regionCoverage": {
                    "cn": {
                        "specCoverage": {
                            "sampleCounts": {"deathknight:unholy": 4},
                        },
                    }
                },
                "specCoverage": {
                    "sampleCounts": {"deathknight:unholy": 4},
                },
                "runDetailCoverage": {"requestedRunCount": 1, "talentSnapshotCount": 5},
                "runCount": 10,
                "profileCount": 4,
                "templates": [
                    {
                        "id": "rio-unholy-rider",
                        "classKey": "deathknight",
                        "specKey": "unholy",
                        "heroKey": "rider_of_the_apocalypse",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-rider", "rank": 1}]},
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        saved = {key: value for key, value, _updated_at in store.saved_states}
        matrix = saved[COMMUNITY_TALENT_SYNC_KEY]["coverageMatrix"]
        by_slot = {row["slotId"]: row for row in matrix["rows"]}

        self.assertEqual(matrix["totalSpecCount"], 40)
        self.assertEqual(matrix["totalHeroSlotCount"], 80)
        self.assertEqual(len(matrix["rows"]), 80)
        self.assertEqual(matrix["verifiedHeroSlotCount"], 1)
        self.assertEqual(matrix["pendingCollectionHeroSlotCount"], 79)
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["scanCoverage"]["totalHeroSlotCount"], 80)
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["scanCoverage"]["coveredHeroSlotCount"], 1)
        self.assertEqual(by_slot["deathknight:blood:deathbringer"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:blood:sanlayn"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:frost:deathbringer"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:frost:rider_of_the_apocalypse"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:unholy:rider_of_the_apocalypse"]["status"], "verified")
        self.assertEqual(by_slot["deathknight:unholy:sanlayn"]["status"], "pending_collection")
        self.assertEqual(by_slot["deathknight:blood:deathbringer"]["attemptedRunCount"], 0)
        self.assertIn("expand Raider.IO target-matrix scan", by_slot["deathknight:blood:deathbringer"]["nextAction"])
        self.assertEqual(by_slot["deathknight:unholy:rider_of_the_apocalypse"]["attemptedRunCount"], 4)
        self.assertIn("promoted active template", by_slot["deathknight:unholy:rider_of_the_apocalypse"]["nextAction"])
        self.assertEqual(
            matrix["sourceSummary"]["raiderio"]["regionCoverage"]["cn"]["specCoverage"]["sampleCounts"]["deathknight:unholy"],
            4,
        )
        timings = saved[COMMUNITY_TALENT_SYNC_KEY]["stageTimings"]
        self.assertGreaterEqual(timings["totalDurationSeconds"], 0)
        self.assertEqual(timings["candidateCount"], 1)
        self.assertEqual(timings["verifiedCount"], 1)
        self.assertEqual(timings["pendingDelta"], 79)
        stage_names = [stage["stage"] for stage in timings["stages"]]
        self.assertIn("candidate_extraction", stage_names)
        self.assertIn("validation_promotion_db_write", stage_names)
        self.assertIn("coverage_report", stage_names)
        self.assertIn("sync_state_write", stage_names)

    def test_community_postgres_sync_summarizes_wcl_evidence_and_target_matrix(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "regions": ["cn"],
                "specCoverage": {"sampleCounts": {"mage:frost": 6}},
                "templates": [
                    {
                        "id": "rio-frost-wcl-backed",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-frostfire", "rank": 1}]},
                        "status": "verified",
                        "payload": {
                            "wclEvidence": {
                                "tier": "wcl_character_supported",
                                "reportCount": 2,
                            },
                            "rioEvidence": {"maxKeyLevel": 24, "sampleCount": 6},
                            "evidenceTier": "wcl_character_supported",
                            "qualityScore": 74,
                        },
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {
                "status": "partial",
                "sourceName": "Warcraft Logs",
                "templates": [],
                "errors": ["missing combatantinfo report extraction"],
            },
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        state = {key: value for key, value, _updated_at in store.saved_states}[COMMUNITY_TALENT_SYNC_KEY]
        raiderio = state["sources"]["raiderio"]
        matrix = state["coverageMatrix"]

        self.assertEqual(raiderio["wclEvidenceCount"], 1)
        self.assertEqual(raiderio["targetMatrix"]["totalHeroSlotCount"], 80)
        self.assertEqual(raiderio["targetMatrix"]["verifiedHeroSlotCount"], 1)
        self.assertEqual(raiderio["targetMatrix"]["pendingCollectionHeroSlotCount"], 79)
        self.assertEqual(raiderio["targetMatrix"]["attemptedRunCount"], 6)
        self.assertIn("fetch run-detail/profile", raiderio["targetMatrix"]["nextAction"])
        self.assertEqual(matrix["rows"][0]["targetCollection"]["attemptedRunCount"], 0)

    def test_community_postgres_missing_slots_mode_targets_only_unverified_slots(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        store.coverage_rows = [
            {
                "id": "existing-arcane-spellslinger",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": "spellslinger",
                "scenarioKey": "mythic_plus",
                "status": "verified",
            },
            {
                "id": "existing-arcane-sunfury",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": "sunfury",
                "scenarioKey": "mythic_plus",
                "status": "verified",
            },
            {
                "id": "existing-frost-spellslinger",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "classKey": "mage",
                "specKey": "frost",
                "heroKey": "spellslinger",
                "scenarioKey": "mythic_plus",
                "status": "verified",
            },
        ]
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-frost-frostfire-new",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-frostfire", "rank": 1}]},
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }
        captured_env = {}

        def fake_sync_raiderio_cache_postgres(**_kwargs):
            captured_env["targetSpecs"] = os.environ.get("WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS", "")
            captured_env["runPages"] = os.environ.get("WOW_RAIDERIO_RUN_PAGES", "")
            captured_env["runDetailLimit"] = os.environ.get("WOW_RAIDERIO_RUN_DETAIL_LIMIT", "")
            captured_env["runDetailLimitPerSpec"] = os.environ.get("WOW_RAIDERIO_RUN_DETAIL_LIMIT_PER_SPEC", "")
            return {"sourceStatus": "verified", "runCount": 1, "profileCount": 1}

        with patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            side_effect=fake_sync_raiderio_cache_postgres,
        ), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, mode="missing_slots")

        target_specs = set(filter(None, captured_env["targetSpecs"].split(",")))
        self.assertEqual(captured_env["runPages"], "0")
        self.assertEqual(captured_env["runDetailLimit"], "240")
        self.assertEqual(captured_env["runDetailLimitPerSpec"], "6")
        self.assertIn("mage:frost", target_specs)
        self.assertNotIn("mage:arcane", target_specs)
        self.assertIn("mage:frost:frostfire", set(store.talent_replace_target_slot_ids or []))
        self.assertNotIn("mage:arcane:spellslinger", set(store.talent_replace_target_slot_ids or []))

        state = {key: value for key, value, _updated_at in store.saved_states}[COMMUNITY_TALENT_SYNC_KEY]
        by_slot = {row["slotId"]: row for row in state["coverageMatrix"]["rows"]}
        self.assertEqual(by_slot["mage:arcane:spellslinger"]["status"], "verified")
        self.assertEqual(by_slot["mage:arcane:sunfury"]["status"], "verified")
        self.assertEqual(by_slot["mage:frost:frostfire"]["status"], "verified")

    def test_community_postgres_missing_slots_mode_refreshes_stale_verified_slots_without_marking_missing(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        store.coverage_rows = [
            {
                "id": "existing-arcane-spellslinger",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": "spellslinger",
                "scenarioKey": "mythic_plus",
                "status": "verified",
                "payload": {
                    "communityTemplateFreshness": {
                        "status": "fresh",
                        "checkedAt": "2026-07-04T00:00:00+00:00",
                        "freshUntil": "2026-07-05T00:00:00+00:00",
                    }
                },
            },
            {
                "id": "existing-arcane-sunfury",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": "sunfury",
                "scenarioKey": "mythic_plus",
                "status": "verified",
                "payload": {
                    "communityTemplateFreshness": {
                        "status": "fresh",
                        "checkedAt": "2026-07-06T00:00:00+00:00",
                        "freshUntil": "2999-01-01T00:00:00+00:00",
                    }
                },
            },
        ]
        captured_env = {}

        def fake_sync_raiderio_cache_postgres(**_kwargs):
            captured_env["targetSpecs"] = os.environ.get("WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS", "")
            return {"sourceStatus": "verified", "runCount": 1, "profileCount": 1}

        with patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            side_effect=fake_sync_raiderio_cache_postgres,
        ), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value={
                "raiderio": {
                    "status": "verified",
                    "sourceName": "Raider.IO",
                    "templates": [
                        {
                            "id": "rio-arcane-spellslinger-refresh",
                            "classKey": "mage",
                            "specKey": "arcane",
                            "heroKey": "spellslinger",
                            "scenarioKey": "mythic_plus",
                            "talentState": {"selectedNodes": [{"id": "node-refresh", "rank": 1}]},
                            "status": "verified",
                        }
                    ],
                    "errors": [],
                }
            },
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, mode="missing_slots")

        target_specs = set(filter(None, captured_env["targetSpecs"].split(",")))
        self.assertIn("mage:arcane", target_specs)
        self.assertIn("mage:arcane:spellslinger", set(store.talent_replace_target_slot_ids or []))

        state = {key: value for key, value, _updated_at in store.saved_states}[COMMUNITY_TALENT_SYNC_KEY]
        by_slot = {row["slotId"]: row for row in state["coverageMatrix"]["rows"]}
        self.assertEqual(by_slot["mage:arcane:spellslinger"]["status"], "verified")
        self.assertEqual(by_slot["mage:arcane:sunfury"]["status"], "verified")

    def test_community_postgres_targeted_slots_mode_replaces_only_requested_winner_slot(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        gear_build_calls = []
        store.build_community_gear_templates = lambda **kwargs: gear_build_calls.append(kwargs) or [
            {"id": "unrelated-gear-template", "status": "verified"}
        ]
        store.coverage_rows = [
            {
                "id": "existing-arcane-spellslinger",
                "sourceKey": "raiderio",
                "sourceName": "Raider.IO",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": "spellslinger",
                "scenarioKey": "mythic_plus",
                "status": "verified",
            },
            {
                "id": "existing-arcane-sunfury-wcl",
                "sourceKey": "warcraftlogs",
                "sourceName": "Warcraft Logs",
                "classKey": "mage",
                "specKey": "arcane",
                "heroKey": "sunfury",
                "scenarioKey": "mythic_plus",
                "status": "verified",
            },
        ]
        captured_env = {}

        def fake_sync_raiderio_cache_postgres(**_kwargs):
            captured_env["targetSpecs"] = os.environ.get("WOW_RAIDERIO_SPEC_RANKING_TARGET_SPECS", "")
            captured_env["runPages"] = os.environ.get("WOW_RAIDERIO_RUN_PAGES", "")
            return {"sourceStatus": "verified", "runCount": 1, "profileCount": 1}

        with patch.dict(
            os.environ,
            {"WOW_COMMUNITY_TEMPLATE_TARGET_SLOTS": "mage:arcane:sunfury,not:a:real-slot"},
            clear=False,
        ), patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            side_effect=fake_sync_raiderio_cache_postgres,
        ), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value={
                "raiderio": {
                    "status": "verified",
                    "sourceName": "Raider.IO",
                    "templates": [
                        {
                            "id": "rio-arcane-spellslinger-unrelated",
                            "classKey": "mage",
                            "specKey": "arcane",
                            "heroKey": "spellslinger",
                            "scenarioKey": "mythic_plus",
                            "talentState": {"selectedNodes": [{"id": "node-unrelated", "rank": 1}]},
                            "status": "verified",
                        },
                        {
                            "id": "rio-arcane-sunfury-refresh",
                            "classKey": "mage",
                            "specKey": "arcane",
                            "heroKey": "sunfury",
                            "scenarioKey": "mythic_plus",
                            "talentState": {"selectedNodes": [{"id": "node-refresh", "rank": 1}]},
                            "status": "verified",
                        },
                    ],
                    "errors": [],
                }
            },
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, mode="targeted_slots")

        self.assertEqual(captured_env["targetSpecs"], "mage:arcane")
        self.assertEqual(captured_env["runPages"], "0")
        self.assertEqual(store.talent_replace_target_slot_ids, ["mage:arcane:sunfury"])
        self.assertEqual([template["id"] for template in store.community_talent_templates], ["rio-arcane-sunfury-refresh"])
        self.assertEqual(gear_build_calls, [])
        self.assertEqual(store.community_gear_templates, [])

        state = {key: value for key, value, _updated_at in store.saved_states}[COMMUNITY_TALENT_SYNC_KEY]
        by_slot = {row["slotId"]: row for row in state["coverageMatrix"]["rows"]}
        self.assertEqual(by_slot["mage:arcane:spellslinger"]["verifiedTemplateIds"], ["existing-arcane-spellslinger"])
        self.assertEqual(by_slot["mage:arcane:sunfury"]["verifiedTemplateIds"], ["rio-arcane-sunfury-refresh"])

    def test_community_postgres_targeted_slots_mode_fails_closed_without_valid_slot_ids(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.community_talent_templates = [{"id": "existing-winner"}]
        refresh_calls = []

        with patch.dict(
            os.environ,
            {"WOW_COMMUNITY_TEMPLATE_TARGET_SLOTS": "not:a:real-slot"},
            clear=False,
        ), patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            side_effect=lambda **_kwargs: refresh_calls.append(True),
        ), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value={"raiderio": {"status": "verified", "sourceName": "Raider.IO", "templates": []}},
            create=True,
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, mode="targeted_slots")

        self.assertEqual(refresh_calls, [])
        self.assertEqual(store.community_talent_templates, [{"id": "existing-winner"}])
        source_stage = next(
            stage for stage in payload["stageTimings"]["stages"] if stage.get("stage") == "source_collection"
        )
        self.assertEqual(source_stage["targetMode"], "targeted_slots")
        self.assertEqual(source_stage["targetSlotCount"], 0)

    def test_community_postgres_sync_uses_promoted_templates_for_coverage(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}

        def fake_replace(templates, scan_run_id="", include_details=False, target_slot_ids=None):
            return {
                "total": 1,
                "verified": 1,
                "partial": 0,
                "blocked": 0,
                "promotedTemplates": [
                    {
                        "id": "promoted-rogue-deathstalker",
                        "sourceKey": "raiderio",
                        "sourceName": "Raider.IO",
                        "classKey": "rogue",
                        "specKey": "subtlety",
                        "heroKey": "deathstalker",
                        "scenarioKey": "mythic_plus",
                        "status": "verified",
                    }
                ],
                "validatedTemplates": [
                    {
                        "id": "blocked-rogue-deathstalker",
                        "sourceKey": "raiderio",
                        "sourceName": "Raider.IO",
                        "classKey": "rogue",
                        "specKey": "subtlety",
                        "heroKey": "deathstalker",
                        "scenarioKey": "mythic_plus",
                        "status": "blocked",
                        "payload": {
                            "talentLoadoutParse": {
                                "errors": ["unknown structured talent entry: spellId=381845"]
                            }
                        },
                    }
                ],
            }

        store.replace_community_talent_templates = fake_replace
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "candidate-placeholder",
                        "classKey": "rogue",
                        "specKey": "subtlety",
                        "heroKey": "deathstalker",
                        "scenarioKey": "mythic_plus",
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {"status": "partial", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        state = {key: value for key, value, _updated_at in store.saved_states}[COMMUNITY_TALENT_SYNC_KEY]
        by_slot = {row["slotId"]: row for row in state["coverageMatrix"]["rows"]}
        self.assertEqual(by_slot["rogue:subtlety:deathstalker"]["status"], "verified")

    def test_community_postgres_sync_records_stage_root_causes(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-frost-authority-failure",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "frostfire",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "missing-authority-node", "rank": 1}]},
                        "status": "blocked",
                        "payload": {"talentEncoding": {"errors": ["unknown talent node: missing-authority-node"]}},
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {
                "status": "partial",
                "sourceName": "Warcraft Logs",
                "templates": [],
                "errors": ["Warcraft Logs v2 credentials are configured, but no combatantinfo template seed/report extraction is available for this sync run."],
            },
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        saved = {key: value for key, value, _updated_at in store.saved_states}
        state = saved[COMMUNITY_TALENT_SYNC_KEY]
        by_slot = {row["slotId"]: row for row in state["coverageMatrix"]["rows"]}

        blocked = by_slot["mage:frost:frostfire"]
        pending = by_slot["mage:frost:spellslinger"]
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["blockers"][0]["stage"], "authority_encoding")
        self.assertIn("unknown talent node", blocked["blockers"][0]["reason"])
        self.assertEqual(pending["status"], "pending_collection")
        self.assertEqual(pending["blockers"][0]["stage"], "source_collection")
        self.assertIn("missing verified community talent template", pending["blockers"][0]["reason"])
        self.assertEqual(state["sources"]["raiderio"]["blockedCount"], 1)
        self.assertEqual(state["sources"]["warcraftlogs"]["candidateCount"], 0)
        self.assertEqual(state["sources"]["warcraftlogs"]["errorCount"], 1)
        self.assertEqual(state["sources"]["warcraftlogs"]["gaps"][0]["stage"], "template_extraction")

    def test_community_coverage_maps_structured_loadout_parse_to_authority_validation(self):
        from server.postgres_cache_sync import build_community_talent_coverage_matrix

        matrix = build_community_talent_coverage_matrix(
            [
                {
                    "id": "rio-frost-unknown-structured-entry",
                    "sourceKey": "raiderio",
                    "sourceName": "Raider.IO",
                    "sourceStatus": "synced",
                    "classKey": "mage",
                    "specKey": "frost",
                    "heroKey": "frostfire",
                    "scenarioKey": "mythic_plus",
                    "status": "blocked",
                    "payload": {
                        "talentLoadoutParse": {
                            "status": "blocked",
                            "source": "structured_loadout",
                            "errors": ["unknown structured talent entry: nodeId=81002, spellId=391002"],
                        }
                    },
                }
            ],
            sources={"raiderio": {"status": "synced", "sourceName": "Raider.IO", "candidateCount": 1}},
        )

        row = next(item for item in matrix["rows"] if item["slotId"] == "mage:frost:frostfire")
        self.assertEqual(row["status"], "blocked")
        self.assertEqual(row["stage"], "authority_validation")
        self.assertEqual(row["blockers"][0]["stage"], "authority_validation")
        self.assertIn("nodeId=81002", row["blockers"][0]["reason"])

    def test_community_postgres_source_loader_excludes_non_community_fixtures_by_default(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {"sourceStatus": "verified", "communityTemplates": [], "errors": []}

        with patch.dict("os.environ", {"WOW_INCLUDE_MANUAL_FIXTURES": "", "WOW_INCLUDE_WEBSIM_BASELINE_TALENTS": ""}), patch(
            "server.community_talent_sources.manual_fixture.load_templates",
            side_effect=AssertionError("manual fixtures should not load in default PG sync"),
        ), patch(
            "server.community_talent_sources.warcraftlogs.load_templates",
            return_value={"status": "missing_credentials", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        ), patch(
            "server.websim_payload.load_websim_baseline_talent_templates",
            side_effect=AssertionError("WebSim baseline should not load in default PG sync"),
        ):
            sources = postgres_cache_sync.load_community_talent_sources_postgres(store)

        self.assertNotIn("manual_fixture", sources)
        self.assertNotIn("websim_baseline", sources)
        self.assertEqual(set(sources), {"raiderio", "warcraftlogs"})

    def test_community_postgres_source_loader_preserves_wcl_skip_warning(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {"sourceStatus": "verified", "communityTemplates": [], "errors": []}

        with patch(
            "server.community_talent_sources.warcraftlogs.load_templates",
            return_value={
                "status": "synced",
                "sourceName": "Warcraft Logs",
                "templates": [],
                "warnings": ["Warcraft Logs ranking extraction skipped: no target slots for this sync run."],
                "errors": [],
            },
        ):
            sources = postgres_cache_sync.load_community_talent_sources_postgres(store)

        self.assertEqual(sources["warcraftlogs"]["status"], "synced")
        self.assertEqual(
            sources["warcraftlogs"]["warnings"],
            ["Warcraft Logs ranking extraction skipped: no target slots for this sync run."],
        )

    def test_community_postgres_sync_expires_disabled_non_community_sources(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-template-a",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "spellslinger",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {"status": "missing_credentials", "sourceName": "Warcraft Logs", "templates": [], "errors": []},
        }

        with patch.dict("os.environ", {"WOW_INCLUDE_WEBSIM_BASELINE_TALENTS": ""}), patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        self.assertEqual(store.expired_talent_source_keys, ["manual_fixture", "websim_baseline"])

    def test_community_postgres_sync_keeps_source_errors_partial_when_rows_are_verified(self):
        from server import postgres_cache_sync
        from server.websim_payload import COMMUNITY_TALENT_SYNC_KEY

        store = FakePostgresSyncStore()
        store.community_gear_template_counts = lambda: {"total": 0, "verified": 0, "partial": 0, "blocked": 0}
        source_results = {
            "raiderio": {
                "status": "verified",
                "sourceName": "Raider.IO",
                "templates": [
                    {
                        "id": "rio-template-a",
                        "classKey": "mage",
                        "specKey": "frost",
                        "heroKey": "spellslinger",
                        "scenarioKey": "mythic_plus",
                        "talentState": {"selectedNodes": [{"id": "node-a", "rank": 1}]},
                        "status": "verified",
                    }
                ],
                "errors": [],
            },
            "warcraftlogs": {
                "status": "blocked",
                "sourceName": "Warcraft Logs",
                "templates": [],
                "errors": ["missing combatantinfo report extraction"],
            },
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value=source_results,
            create=True,
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)
        saved = {key: value for key, value, _updated_at in store.saved_states}

        self.assertEqual(payload["talents"]["templates"]["verified"], 1)
        self.assertEqual(payload["talents"]["templates"]["blocked"], 0)
        self.assertEqual(payload["sourceStatus"], "partial")
        self.assertIn("warcraftlogs: missing combatantinfo report extraction", payload["errors"])
        self.assertEqual(saved[COMMUNITY_TALENT_SYNC_KEY]["sourceStatus"], "partial")

    def test_warcraftlogs_seed_templates_normalize_evidence_tiers(self):
        from server.community_talent_sources import warcraftlogs

        with patch.object(
            warcraftlogs,
            "warcraftlogs_credentials_state",
            return_value={"configured": True, "api": "warcraftlogs-v2-graphql", "mode": "oauth"},
        ), patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": json.dumps(
                    {
                        "templates": [
                            {
                                "id": "wcl-exact",
                                "classKey": "mage",
                                "specKey": "frost",
                                "heroKey": "frostfire",
                                "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAA",
                                "payload": {
                                    "warcraftlogs": {
                                        "reportCode": "abc123",
                                        "combatantInfo": {"talents": "CAEAAAAAAAAAAAAAAAAAAAAA"},
                                        "templateSignature": "talent:m:f:f",
                                    },
                                    "normalizedPerformance": {"score": 91.5},
                                },
                            },
                            {
                                "id": "wcl-supported",
                                "classKey": "mage",
                                "specKey": "frost",
                                "heroKey": "spellslinger",
                                "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAB",
                                "payload": {
                                    "warcraftlogs": {
                                        "reportCode": "def456",
                                        "characterMatched": True,
                                    },
                                    "normalizedPerformance": {"score": 72},
                                },
                            },
                            {
                                "id": "wcl-conflict",
                                "classKey": "mage",
                                "specKey": "frost",
                                "heroKey": "frostfire",
                                "rawImportCode": "CAEAAAAAAAAAAAAAAAAAAAAC",
                                "status": "verified",
                                "payload": {
                                    "warcraftlogs": {
                                        "reportCode": "ghi789",
                                        "conflictReason": "combatantinfo talents differ from Raider.IO loadout",
                                    }
                                },
                            },
                        ]
                    }
                )
            },
        ):
            result = warcraftlogs.load_templates()

        by_id = {template["id"]: template for template in result["templates"]}
        self.assertEqual(by_id["wcl-exact"]["payload"]["wclEvidence"]["tier"], "wcl_exact_template")
        self.assertEqual(by_id["wcl-exact"]["payload"]["evidenceTier"], "wcl_exact_template")
        self.assertEqual(by_id["wcl-exact"]["payload"]["qualityScore"], 91.5)
        self.assertEqual(by_id["wcl-supported"]["payload"]["wclEvidence"]["tier"], "wcl_character_supported")
        self.assertEqual(by_id["wcl-conflict"]["payload"]["wclEvidence"]["tier"], "wcl_conflict")
        self.assertEqual(by_id["wcl-conflict"]["status"], "blocked")

    def test_warcraftlogs_no_target_slots_is_a_synced_skip(self):
        from server.community_talent_sources import warcraftlogs

        with patch.object(
            warcraftlogs,
            "warcraftlogs_credentials_state",
            return_value={"configured": True, "api": "warcraftlogs-v2-graphql", "mode": "oauth"},
        ), patch.object(warcraftlogs, "target_slots_for_run", return_value=[]):
            result = warcraftlogs.load_templates()

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["templates"], [])
        self.assertEqual(result["errors"], [])
        self.assertEqual(
            result["warnings"],
            ["Warcraft Logs ranking extraction skipped: no target slots for this sync run."],
        )

    def test_warcraftlogs_rankings_extract_wcl_exact_template_candidates(self):
        from server.community_talent_sources import warcraftlogs

        calls = []

        def fake_graphql(_query, variables=None, token=None):
            calls.append(variables or {})
            return {
                "worldData": {
                    "encounter": {
                        "id": 3176,
                        "name": "Imperator Averzian",
                        "characterRankings": {
                            "count": 1,
                            "hasMorePages": False,
                            "page": 1,
                            "rankings": [
                                {
                                    "name": "Runeathon",
                                    "class": "Mage",
                                    "spec": "Arcane",
                                    "amount": 149208.58,
                                    "duration": 281166,
                                    "report": {"code": "jVgTrRX3vp6DfWZw", "fightID": 28},
                                    "server": {"name": "Stormrage", "region": "US"},
                                    "talents": [
                                        {"talentID": 80141, "points": 1},
                                        {"talentID": 117247, "points": 1},
                                    ],
                                }
                            ],
                        },
                    }
                }
            }

        with patch.object(
            warcraftlogs,
            "warcraftlogs_credentials_state",
            return_value={"configured": True, "api": "warcraftlogs-v2-graphql", "mode": "oauth"},
        ), patch.object(
            warcraftlogs,
            "warcraftlogs_graphql",
            side_effect=fake_graphql,
            create=True,
        ), patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": "",
                "WOW_WARCRAFTLOGS_TEMPLATE_TARGET_SLOTS": "mage:arcane:sunfury",
                "WOW_WARCRAFTLOGS_RANKING_ENCOUNTERS": "3176",
                "WOW_WARCRAFTLOGS_RANKING_PARTITION": "3",
                "WOW_WARCRAFTLOGS_RANKING_PAGES": "1",
            },
        ):
            result = warcraftlogs.load_templates()

        self.assertEqual(result["status"], "partial")
        self.assertEqual(calls[0]["className"], "Mage")
        self.assertEqual(calls[0]["specName"], "Arcane")
        self.assertEqual(calls[0]["encounterId"], 3176)
        template = result["templates"][0]
        self.assertEqual(template["sourceName"], "Warcraft Logs")
        self.assertEqual(template["classKey"], "mage")
        self.assertEqual(template["specKey"], "arcane")
        self.assertEqual(template["heroKey"], "sunfury")
        self.assertEqual(template["playerId"], "Runeathon")
        self.assertEqual(template["payload"]["wclEvidence"]["tier"], "wcl_exact_template")
        self.assertEqual(template["payload"]["evidenceTier"], "wcl_exact_template")
        self.assertEqual(template["payload"]["warcraftlogs"]["reportCode"], "jVgTrRX3vp6DfWZw")
        self.assertEqual(template["payload"]["warcraftlogs"]["fightId"], 28)
        self.assertEqual(template["payload"]["warcraftlogs"]["loadout"][0]["talentID"], 80141)
        self.assertEqual(template["payload"]["normalizedPerformance"]["score"], 149208.58)

    def test_warcraftlogs_rankings_skip_non_target_hero_candidates(self):
        from server.community_talent_sources import warcraftlogs

        class AuthorityStore:
            def __init__(self):
                self.requested = None

            def community_talent_authority_index(self, class_key, spec_key):
                self.requested = (class_key, spec_key)
                return {
                    80141: [{"id": "simc-class-80141-mage-arcane", "treeType": "class"}],
                    117267: [
                        {
                            "id": "simc-hero-117267-mage-arcane-spellslinger",
                            "treeType": "hero",
                            "heroKey": "spellslinger",
                        }
                    ],
                    117247: [
                        {
                            "id": "simc-hero-117247-mage-arcane-sunfury",
                            "treeType": "hero",
                            "heroKey": "sunfury",
                        }
                    ],
                }

        store = AuthorityStore()

        def fake_graphql(_query, variables=None, token=None):
            return {
                "worldData": {
                    "encounter": {
                        "id": 3176,
                        "name": "Imperator Averzian",
                        "characterRankings": {
                            "rankings": [
                                {
                                    "name": "Wronghero",
                                    "class": "Mage",
                                    "spec": "Arcane",
                                    "amount": 199208.58,
                                    "duration": 281166,
                                    "report": {"code": "WrongHeroReport", "fightID": 1},
                                    "server": {"name": "Stormrage", "region": "US"},
                                    "talents": [
                                        {"talentID": 80141, "points": 1},
                                        {"talentID": 123344, "points": 1},
                                        {"talentID": 117267, "points": 1},
                                    ],
                                },
                                {
                                    "name": "Righthero",
                                    "class": "Mage",
                                    "spec": "Arcane",
                                    "amount": 149208.58,
                                    "duration": 281166,
                                    "report": {"code": "RightHeroReport", "fightID": 2},
                                    "server": {"name": "Stormrage", "region": "US"},
                                    "talents": [
                                        {"talentID": 80141, "points": 1},
                                        {"talentID": 123341, "points": 1},
                                        {"talentID": 117247, "points": 1},
                                    ],
                                },
                            ],
                        },
                    }
                }
            }

        with patch.object(
            warcraftlogs,
            "warcraftlogs_credentials_state",
            return_value={"configured": True, "api": "warcraftlogs-v2-graphql", "mode": "oauth"},
        ), patch.object(
            warcraftlogs,
            "warcraftlogs_graphql",
            side_effect=fake_graphql,
            create=True,
        ), patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": "",
                "WOW_WARCRAFTLOGS_TEMPLATE_TARGET_SLOTS": "mage:arcane:sunfury",
                "WOW_WARCRAFTLOGS_RANKING_ENCOUNTERS": "3176",
                "WOW_WARCRAFTLOGS_RANKING_PARTITION": "3",
                "WOW_WARCRAFTLOGS_RANKING_PAGES": "1",
                "WOW_WARCRAFTLOGS_RANKING_TEMPLATE_LIMIT_PER_SLOT": "4",
            },
        ):
            result = warcraftlogs.load_templates(store)

        self.assertEqual(store.requested, ("mage", "arcane"))
        self.assertEqual([template["playerId"] for template in result["templates"]], ["Righthero"])
        self.assertEqual(result["templates"][0]["heroKey"], "sunfury")

    def test_warcraftlogs_rankings_respects_start_and_end_page_window(self):
        from server.community_talent_sources import warcraftlogs

        pages = []

        def fake_graphql(_query, variables=None, token=None):
            pages.append((variables or {}).get("page"))
            return {
                "worldData": {
                    "encounter": {
                        "id": 3176,
                        "name": "Imperator Averzian",
                        "characterRankings": {"rankings": []},
                    }
                }
            }

        with patch.object(
            warcraftlogs,
            "warcraftlogs_credentials_state",
            return_value={"configured": True, "api": "warcraftlogs-v2-graphql", "mode": "oauth"},
        ), patch.object(
            warcraftlogs,
            "warcraftlogs_graphql",
            side_effect=fake_graphql,
            create=True,
        ), patch.dict(
            "os.environ",
            {
                "WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON": "",
                "WOW_WARCRAFTLOGS_TEMPLATE_TARGET_SLOTS": "mage:arcane:sunfury",
                "WOW_WARCRAFTLOGS_RANKING_ENCOUNTERS": "3176",
                "WOW_WARCRAFTLOGS_RANKING_PARTITION": "3",
                "WOW_WARCRAFTLOGS_RANKING_START_PAGE": "9",
                "WOW_WARCRAFTLOGS_RANKING_END_PAGE": "10",
            },
        ):
            result = warcraftlogs.load_templates()

        self.assertEqual(result["templates"], [])
        self.assertEqual(pages, [9, 10])

    def test_community_postgres_sync_writes_gear_templates_when_candidates_exist(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.gear_template_candidates = [
            {
                "id": "gear-template-a",
                "classKey": "mage",
                "specKey": "frost",
                "status": "complete",
                "gearItems": [{"slot": "head", "itemId": "190001", "ilevel": 707, "simcReady": True}],
            }
        ]

        with patch.object(postgres_cache_sync, "load_community_talent_sources_postgres", return_value={}):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        self.assertEqual(len(store.community_gear_templates), 1)
        self.assertEqual(payload["gear"]["templates"]["verified"], 1)
        self.assertEqual(payload["sourceStatus"], "partial")

    def test_community_postgres_sync_reports_gear_template_preflight_matrix(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.gear_template_candidates = [
            {
                "id": "observed-mage-frost",
                "classKey": "mage",
                "specKey": "frost",
                "sourceKey": "raiderio_observed_profile",
                "sourceName": "Raider.IO observed gear",
                "sourceStatus": "partial",
                "status": "partial",
                "signature": "sig-observed-mage-frost",
                "gearItems": [{"slot": "head", "itemId": "190001", "ilevel": 707, "simcReady": True}],
                "missingSlots": ["neck"],
                "readySlotCount": 1,
            },
            {
                "id": "baseline-mage-frost",
                "classKey": "mage",
                "specKey": "frost",
                "sourceKey": "default_template",
                "sourceName": "默认模板",
                "sourceStatus": "verified",
                "status": "complete",
                "signature": "sig-baseline-mage-frost",
                "gearItems": [
                    {"slot": "head", "itemId": "190101", "ilevel": 707, "simcReady": True},
                    {"slot": "neck", "itemId": "190102", "ilevel": 707, "simcReady": True},
                ],
                "missingSlots": [],
                "readySlotCount": 2,
            },
        ]

        with patch.object(postgres_cache_sync, "load_community_talent_sources_postgres", return_value={}), patch.object(
            postgres_cache_sync,
            "expected_spec_pairs",
            return_value=["mage:frost", "deathknight:unholy"],
            create=True,
        ), patch.object(postgres_cache_sync, "CANONICAL_GEAR_SLOTS", ["head", "neck"], create=True):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(store=store, refresh_raiderio=False)

        preflight = payload["gear"]["preflight"]
        self.assertEqual(preflight["schemaRevision"], "community-gear-template-preflight-v1")
        self.assertEqual(preflight["status"], "partial")
        self.assertEqual(preflight["totalSpecCount"], 2)
        self.assertEqual(preflight["totalDisplaySlotCount"], 4)
        self.assertEqual(preflight["communityImport"]["status"], "partial")
        self.assertEqual(preflight["communityImport"]["totalTemplateSlotCount"], 4)
        self.assertEqual(preflight["communityImport"]["coveredTemplateSlotCount"], 1)
        self.assertEqual(preflight["communityImport"]["missingTemplateSlotCount"], 3)
        self.assertEqual(preflight["communityImport"]["realCommunityCompleteSpecCount"], 0)
        self.assertEqual(preflight["communityImport"]["baselineAvailableSpecCount"], 1)
        self.assertIn("80/80", preflight["communityImport"]["countingPolicy"])
        self.assertEqual(preflight["canonicalSlotMatrix"]["totalSlotCount"], 4)
        self.assertEqual(preflight["canonicalSlotMatrix"]["readySlotCount"], 1)
        self.assertEqual(preflight["canonicalSlotMatrix"]["missingSlotCount"], 3)
        self.assertEqual(preflight["communityBest"]["partialSpecCount"], 1)
        self.assertEqual(preflight["communityBest"]["pendingSpecCount"], 1)
        self.assertEqual(preflight["baseline"]["availableSpecCount"], 1)
        self.assertEqual(preflight["baseline"]["blockedSpecCount"], 1)
        mage_best = next(
            row
            for row in preflight["displaySlots"]
            if row["specId"] == "mage:frost" and row["templateSlot"] == "community_best"
        )
        self.assertEqual(mage_best["status"], "partial")
        self.assertEqual(mage_best["missingSlots"], ["neck"])
        mage_baseline = next(
            row
            for row in preflight["displaySlots"]
            if row["specId"] == "mage:frost" and row["templateSlot"] == "baseline"
        )
        self.assertEqual(mage_baseline["status"], "available")
        self.assertEqual(mage_baseline["sourceKey"], "default_template")
        self.assertFalse(
            any(row["templateSlot"] == "community_best" and row["sourceKey"] == "default_template" for row in preflight["displaySlots"])
        )
        target_keys = {row["targetKey"] for row in preflight["targetQueue"]}
        self.assertIn("gear-template:deathknight:unholy:community_best:mplus_mixed_route", target_keys)
        self.assertIn("gear-slot:mage:frost:neck", target_keys)
        self.assertEqual(payload["gear"]["realCommunityTemplates"]["coveredSpecCount"], 0)
        self.assertEqual(payload["gear"]["realCommunityTemplates"]["missingSpecCount"], 2)
        self.assertEqual(payload["gear"]["realCommunityTemplates"]["missingSpecs"], ["mage:frost", "deathknight:unholy"])
        self.assertEqual(payload["gear"]["baselineTemplates"]["availableSpecCount"], 1)

    def test_season_recommended_gear_sync_writes_templates_and_state(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.season_recommended_gear_templates = [
            {
                "id": "season-rec-mage-frost",
                "classKey": "mage",
                "specKey": "frost",
                "sourceKey": "season_recommendation",
                "sourceName": "当前赛季大秘境 AOE 推荐模板",
                "sourceStatus": "synced",
                "status": "complete",
                "readySlotCount": 16,
                "missingSlots": [],
                "gearItems": [],
                "rawString": "head=test,id=1",
                "payload": {
                    "templateSlot": "baseline",
                    "templateEvidence": {"recommendationConfidence": "provisional"},
                },
            }
        ]

        with patch.object(postgres_cache_sync, "utc_now", return_value="2026-07-06T09:44:36+00:00"):
            result = postgres_cache_sync.sync_season_recommended_gear_postgres(
                mode="manual",
                store=store,
            )

        self.assertEqual(result["runner"], "postgres")
        self.assertEqual(result["sourceKey"], "season_recommendation")
        self.assertEqual(result["scanRunId"], "season-recommended-gear-20260706T094436Z")
        self.assertEqual(result["completeSpecCount"], 1)
        self.assertEqual(result["provisionalSpecCount"], 1)
        self.assertEqual(store.community_gear_templates[0]["sourceKey"], "season_recommendation")
        self.assertEqual(store.real_player_residue_cleanups[0]["scanRunId"], "season-recommended-gear-20260706T094436Z")
        saved = {key: value for key, value, _updated_at in store.saved_states}
        self.assertIn("season_recommended_gear_sync", saved)
        self.assertEqual(saved["season_recommended_gear_sync"]["completeSpecCount"], 1)

    def test_recommended_bis_guard_sync_persists_optimizer_readiness_state(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.community_gear_template_live_health_summary = lambda: {
            "scanRunId": "pg-community-template-source-evidence-test",
            "templateChains": {
                "recommendedBis": {
                    "guardMode": "readiness_only",
                    "totalSpecCount": 1,
                    "expectedSpecCount": 2,
                    "missingSpecCount": 1,
                    "candidateSpecCount": 1,
                    "verifiedSpecCount": 0,
                    "blockedSpecCount": 1,
                    "optimizerRequiredSpecCount": 1,
                    "fullOptimizerRunRequiredSpecCount": 1,
                    "missingSpecs": ["shaman:elemental"],
                    "blockedExamples": [
                        {
                            "spec": "shaman:elemental",
                            "status": "optimizer_blocked",
                            "blockers": ["recommended_bis_v1 optimizer has not produced a candidate for this spec"],
                        }
                    ],
                }
            },
        }

        with patch.object(postgres_cache_sync, "utc_now", return_value="2026-07-07T13:00:00+00:00"):
            result = postgres_cache_sync.sync_recommended_bis_guard_postgres(mode="manual", store=store)

        self.assertEqual(result["runner"], "postgres")
        self.assertEqual(result["schemaRevision"], "recommended-bis-v1-guard-state-v1")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["sourceStatus"], "partial")
        self.assertEqual(result["guardMode"], "readiness_only")
        self.assertEqual(result["expectedSpecCount"], 2)
        self.assertEqual(result["totalSpecCount"], 1)
        self.assertEqual(result["optimizerRequiredSpecCount"], 1)
        self.assertEqual(result["missingSpecs"], ["shaman:elemental"])
        saved = {key: value for key, value, _updated_at in store.saved_states}
        self.assertIn("recommended_bis_v1_guard", saved)
        self.assertEqual(saved["recommended_bis_v1_guard"]["fullOptimizerRunRequiredSpecCount"], 1)
        self.assertEqual(saved["recommended_bis_v1_guard"]["lastGuardCheckAt"], "2026-07-07T13:00:00+00:00")

    def test_recommended_bis_prototype_sync_writes_projected_templates_and_state(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.recommended_bis_prototype_templates = [
            {
                "id": "recommended-bis-mage-frost",
                "classKey": "mage",
                "specKey": "frost",
                "sourceKey": "recommended_bis",
                "sourceName": "SimC optimizer 毕业模板",
                "sourceStatus": "synced",
                "status": "complete",
                "readySlotCount": 16,
                "missingSlots": [],
                "gearItems": [],
                "rawString": "head=test,id=1",
                "payload": {
                    "templateSlot": "recommended_bis",
                    "templateType": "recommended_bis",
                    "templateEvidence": {
                        "schemaRevision": "recommended-bis-v1",
                        "status": "projected_bis",
                        "optimizerVersion": "gear-bis-optimizer-v1",
                    },
                },
            }
        ]

        with patch.object(postgres_cache_sync, "utc_now", return_value="2026-07-07T14:00:00+00:00"):
            result = postgres_cache_sync.sync_recommended_bis_prototype_postgres(
                mode="manual",
                store=store,
            )

        self.assertEqual(result["runner"], "postgres")
        self.assertEqual(result["schemaRevision"], "recommended-bis-v1-prototype-sync-state-v1")
        self.assertEqual(result["sourceKey"], "recommended_bis")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["projectedSpecCount"], 1)
        self.assertEqual(result["verifiedSpecCount"], 0)
        self.assertEqual(result["fullOptimizerRunRequiredSpecCount"], result["dpsExpectedSpecCount"])
        self.assertIn("mage:frost", result["projectedSpecs"])
        self.assertEqual(store.community_gear_templates[0]["sourceKey"], "recommended_bis")
        saved = {key: value for key, value, _updated_at in store.saved_states}
        self.assertIn("recommended_bis_v1_prototype_sync", saved)
        self.assertEqual(saved["recommended_bis_v1_prototype_sync"]["checkedAt"], "2026-07-07T14:00:00+00:00")

    def test_community_best_guard_sync_persists_observed_readiness_state(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.community_gear_template_live_health_summary = lambda: {
            "scanRunId": "pg-community-template-source-evidence-test",
            "templateChains": {
                "communityObserved": {
                    "guardMode": "readiness_only",
                    "expectedSpecCount": 2,
                    "coveredSpecCount": 1,
                    "verifiedSpecCount": 1,
                    "provisionalSpecCount": 0,
                    "partialSpecCount": 0,
                    "blockedSpecCount": 1,
                    "missingSpecCount": 1,
                    "simcReplayRequiredSpecCount": 1,
                    "missingSpecs": ["mage:frost"],
                    "simcReplayRequiredSpecs": ["shaman:elemental"],
                    "blockedExamples": [
                        {
                            "spec": "mage:frost",
                            "status": "observed_blocked",
                            "blockers": ["community_best_v2 requires sourceUrl for the observed character"],
                        }
                    ],
                }
            },
        }

        with patch.object(postgres_cache_sync, "utc_now", return_value="2026-07-07T13:05:00+00:00"):
            result = postgres_cache_sync.sync_community_best_guard_postgres(mode="manual", store=store)

        self.assertEqual(result["runner"], "postgres")
        self.assertEqual(result["schemaRevision"], "community-best-v2-guard-state-v1")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["sourceStatus"], "partial")
        self.assertEqual(result["guardMode"], "readiness_only")
        self.assertEqual(result["expectedSpecCount"], 2)
        self.assertEqual(result["coveredSpecCount"], 1)
        self.assertEqual(result["missingSpecCount"], 1)
        self.assertEqual(result["simcReplayRequiredSpecCount"], 1)
        self.assertEqual(result["missingSpecs"], ["mage:frost"])
        self.assertEqual(result["simcReplayRequiredSpecs"], ["shaman:elemental"])
        saved = {key: value for key, value, _updated_at in store.saved_states}
        self.assertIn("community_best_v2_guard", saved)
        self.assertEqual(saved["community_best_v2_guard"]["lastGuardCheckAt"], "2026-07-07T13:05:00+00:00")

    def test_gear_preflight_refreshes_stale_complete_community_winner_without_breaking_coverage(self):
        from server import postgres_cache_sync

        template = {
            "id": "observed-mage-frost-complete",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "sourceName": "Raider.IO observed gear",
            "sourceUrl": "https://raider.io/characters/us/area-52/Magewinner",
            "sourceStatus": "verified",
            "status": "complete",
            "signature": "sig-observed-mage-frost-complete",
            "sampleCount": 1,
            "profileHash": "profile:mage:frost:magewinner",
            "gearHash": "gear:mage:frost:magewinner",
            "scanRunId": "scan-active-observed",
            "gearItems": [
                {"slot": "head", "itemId": "190001", "ilevel": 707, "simcReady": True},
                {"slot": "neck", "itemId": "190002", "ilevel": 707, "simcReady": True},
            ],
            "payload": {
                "sampleCount": 1,
                "profileHash": "profile:mage:frost:magewinner",
                "gearHash": "gear:mage:frost:magewinner",
                "character": {"name": "Magewinner", "region": "us", "realmSlug": "area-52"},
                "communityTemplateFreshness": {
                    "status": "fresh",
                    "checkedAt": "2026-07-04T00:00:00+00:00",
                    "freshUntil": "2026-07-05T00:00:00+00:00",
                }
            },
        }

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "CANONICAL_GEAR_SLOTS",
            ["head", "neck"],
            create=True,
        ):
            preflight = postgres_cache_sync.build_community_gear_template_preflight([template])

        self.assertEqual(preflight["communityBest"]["completeSpecCount"], 1)
        self.assertEqual(preflight["realCommunityTemplates"]["coveredSpecCount"], 1)
        mage_best = next(
            row
            for row in preflight["displaySlots"]
            if row["specId"] == "mage:frost" and row["templateSlot"] == "community_best"
        )
        self.assertEqual(mage_best["status"], "complete")
        self.assertEqual(mage_best["freshnessStatus"], "stale")
        self.assertEqual(mage_best["nextAction"], "refresh_stale_winner")
        stale_target = next(
            row
            for row in preflight["targetQueue"]
            if row["targetKey"] == "gear-template:mage:frost:community_best:mplus_mixed_route"
        )
        self.assertEqual(stale_target["status"], "stale")
        self.assertEqual(stale_target["nextAction"], "refresh_stale_winner")

    def test_gear_preflight_blocks_complete_observed_without_single_profile_evidence(self):
        from server import postgres_cache_sync

        template = {
            "id": "observed-mage-frost-aggregate",
            "classKey": "mage",
            "specKey": "frost",
            "sourceKey": "raiderio_observed_profile",
            "sourceName": "Raider.IO observed gear",
            "sourceUrl": "https://raider.io/characters/us/area-52/Magewinner",
            "sourceStatus": "verified",
            "status": "complete",
            "signature": "sig-observed-mage-frost-aggregate",
            "sampleCount": 12,
            "profileHash": "profile:mage:frost:aggregate",
            "gearHash": "gear:mage:frost:aggregate",
            "scanRunId": "scan-aggregate-observed",
            "gearItems": [
                {"slot": "head", "itemId": "190001", "ilevel": 707, "simcReady": True},
                {"slot": "neck", "itemId": "190002", "ilevel": 707, "simcReady": True},
            ],
            "payload": {
                "sampleCount": 12,
                "profileHash": "profile:mage:frost:aggregate",
                "gearHash": "gear:mage:frost:aggregate",
                "character": {"name": "Magewinner", "region": "us", "realmSlug": "area-52"},
            },
        }

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["mage:frost"]), patch.object(
            postgres_cache_sync,
            "CANONICAL_GEAR_SLOTS",
            ["head", "neck"],
            create=True,
        ):
            preflight = postgres_cache_sync.build_community_gear_template_preflight([template])

        self.assertEqual(preflight["communityBest"]["completeSpecCount"], 0)
        self.assertEqual(preflight["communityBest"]["blockedSpecCount"], 1)
        self.assertEqual(preflight["realCommunityTemplates"]["coveredSpecCount"], 0)
        self.assertEqual(preflight["realCommunityTemplates"]["blockedSpecCount"], 1)

    def test_gear_preflight_treats_mandatory_two_hand_offhand_as_covered(self):
        from server import postgres_cache_sync

        template = {
            "id": "observed-dk-blood",
            "classKey": "deathknight",
            "specKey": "blood",
            "sourceKey": "raiderio_observed_profile",
            "sourceName": "Raider.IO observed gear",
            "sourceUrl": "https://raider.io/characters/us/area-52/Dkwinner",
            "sourceStatus": "verified",
            "status": "complete",
            "signature": "sig-observed-dk-blood",
            "sampleCount": 1,
            "profileHash": "profile:deathknight:blood:dkwinner",
            "gearHash": "gear:deathknight:blood:dkwinner",
            "scanRunId": "scan-active-observed",
            "gearItems": [
                {
                    "slot": "main_hand",
                    "itemId": "190001",
                    "ilevel": 707,
                    "bonus_id": "12345",
                    "weaponType": "Two-Handed Axe",
                    "sourceType": "observed_profile",
                    "statDisplayStatus": "verified_variant",
                    "statSource": "simulationcraft",
                    "itemStats": [{"key": "strength", "label": "Strength", "value": 111}],
                    "simcReady": True,
                }
            ],
            "missingSlots": [],
            "readySlotCount": 2,
            "payload": {
                "sampleCount": 1,
                "profileHash": "profile:deathknight:blood:dkwinner",
                "gearHash": "gear:deathknight:blood:dkwinner",
                "character": {"name": "Dkwinner", "region": "us", "realmSlug": "area-52"},
            },
        }

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["deathknight:blood"]), patch.object(
            postgres_cache_sync,
            "CANONICAL_GEAR_SLOTS",
            ["main_hand", "off_hand"],
            create=True,
        ):
            preflight = postgres_cache_sync.build_community_gear_template_preflight([template])

        self.assertEqual(preflight["communityBest"]["completeSpecCount"], 1)
        self.assertEqual(preflight["communityBest"]["partialSpecCount"], 0)
        self.assertEqual(preflight["canonicalSlotMatrix"]["readySlotCount"], 2)
        self.assertEqual(preflight["canonicalSlotMatrix"]["missingSlotCount"], 0)
        community_targets = [
            row for row in preflight["targetQueue"]
            if row.get("templateSlot") == "community_best" or row.get("targetType") == "gear_slot"
        ]
        self.assertEqual(community_targets, [])

    def test_gear_preflight_treats_verified_two_hand_metadata_as_offhand_occupancy(self):
        from server import postgres_cache_sync

        template = {
            "id": "observed-monk-brewmaster",
            "classKey": "monk",
            "specKey": "brewmaster",
            "sourceKey": "raiderio_observed_profile",
            "sourceName": "Raider.IO observed gear",
            "sourceUrl": "https://raider.io/characters/eu/draenor/Monkwinner",
            "sourceStatus": "verified",
            "status": "complete",
            "signature": "sig-observed-monk-brewmaster",
            "sampleCount": 1,
            "profileHash": "profile:monk:brewmaster:monkwinner",
            "gearHash": "gear:monk:brewmaster:monkwinner",
            "scanRunId": "scan-active-observed",
            "gearItems": [
                {
                    "slot": "main_hand",
                    "itemId": "193723",
                    "ilevel": 707,
                    "bonus_id": "12345",
                    "sourceType": "observed_profile",
                    "metadataStatus": "verified",
                    "metadataSource": "Battle.net Game Data API",
                    "weaponType": "Staff",
                }
            ],
            "missingSlots": [],
            "readySlotCount": 2,
            "payload": {
                "sampleCount": 1,
                "profileHash": "profile:monk:brewmaster:monkwinner",
                "gearHash": "gear:monk:brewmaster:monkwinner",
                "character": {"name": "Monkwinner", "region": "eu", "realmSlug": "draenor"},
            },
        }

        with patch.object(postgres_cache_sync, "expected_spec_pairs", return_value=["monk:brewmaster"]), patch.object(
            postgres_cache_sync,
            "CANONICAL_GEAR_SLOTS",
            ["main_hand", "off_hand"],
            create=True,
        ):
            preflight = postgres_cache_sync.build_community_gear_template_preflight([template])

        self.assertEqual(preflight["communityBest"]["completeSpecCount"], 1)
        self.assertEqual(preflight["communityBest"]["partialSpecCount"], 0)
        self.assertEqual(preflight["canonicalSlotMatrix"]["readySlotCount"], 2)
        self.assertEqual(preflight["canonicalSlotMatrix"]["missingSlotCount"], 0)
        self.assertEqual(
            [
                row for row in preflight["targetQueue"]
                if row.get("templateSlot") == "community_best" or row.get("targetType") == "gear_slot"
            ],
            [],
        )

    def test_gear_template_first_sync_runs_backfill_without_replacing_talent_templates(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "verified",
            "profiles": [{"name": "Mage A", "gear": [{"itemId": "190001", "slot": "head", "ilevel": 707}]}],
        }

        with patch.object(
            postgres_cache_sync,
            "load_community_talent_sources_postgres",
            return_value={
                "raiderio": {
                    "status": "verified",
                    "sourceName": "Raider.IO",
                    "templates": [{"id": "talent-candidate-that-must-not-be-written"}],
                }
            },
        ), patch.object(
            postgres_cache_sync,
            "sync_raiderio_cache_postgres",
            side_effect=AssertionError("gear first sync should not refresh Raider.IO when refresh_raiderio=False"),
        ), patch.object(
            postgres_cache_sync,
            "expected_spec_pairs",
            return_value=["mage:frost"],
            create=True,
        ), patch.object(
            postgres_cache_sync,
            "CANONICAL_GEAR_SLOTS",
            ["head", "neck"],
            create=True,
        ), patch.dict(
            os.environ,
            {
                "WOW_COMMUNITY_GEAR_FIRST_SYNC_TARGET_LIMIT": "5",
                "WOW_COMMUNITY_GEAR_FIRST_SYNC_PROFILE_LIMIT": "2",
                "WOW_COMMUNITY_GEAR_FIRST_SYNC_TIMEOUT_SECONDS": "30",
                "WOW_COMMUNITY_GEAR_FIRST_SYNC_SIMC_STATS": "1",
                "WOW_COMMUNITY_GEAR_FIRST_SYNC_FULL_PROFILE_GEAR": "0",
                "WOW_COMMUNITY_GEAR_FIRST_SYNC_ITEM_PROBE_LIMIT": "4",
            },
        ):
            payload = postgres_cache_sync.sync_community_template_cache_postgres(
                mode="gear_template_first_sync",
                store=store,
                refresh_raiderio=False,
            )

        self.assertEqual(store.community_talent_templates, [])
        self.assertIsNone(store.talent_replace_target_slot_ids)
        self.assertEqual(len(store.observed_backfills), 1)
        backfill_call = store.observed_backfills[0]
        self.assertEqual(backfill_call["mode"], "gear_template_first_sync")
        self.assertEqual(backfill_call["targetLimit"], 5)
        self.assertEqual(backfill_call["profileLimit"], 2)
        self.assertEqual(backfill_call["timeoutSeconds"], 30)
        self.assertTrue(backfill_call["enableSimcStats"])
        self.assertFalse(backfill_call["fullProfileGear"])
        self.assertEqual(backfill_call["itemProbeLimit"], 4)
        self.assertEqual(payload["gear"]["observedBackfill"]["targetLimit"], 5)
        self.assertEqual(payload["gear"]["observedBackfill"]["itemProbeLimit"], 4)
        stages = payload["stageTimings"]["stages"]
        self.assertIn("gear_observed_backfill", {stage["stage"] for stage in stages})
        gear_stage = next(stage for stage in stages if stage["stage"] == "gear_observed_backfill")
        self.assertEqual(gear_stage["itemProbeLimit"], 4)
        self.assertEqual(gear_stage["simcItemProbeCount"], 4)
        self.assertEqual(gear_stage["simcItemProbeResolvedCount"], 1)
        source_stage = next(stage for stage in stages if stage["stage"] == "source_collection")
        self.assertEqual(source_stage["targetMode"], "gear_template_first_sync")

    def test_observed_backfill_postgres_calls_row_writer(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {
            "sourceStatus": "verified",
            "profiles": [{"name": "Mage A", "gear": [{"itemId": "190001", "slot": "head", "ilevel": 707}]}],
        }

        payload = postgres_cache_sync.run_gear_observed_backfill_postgres(mode="scheduled", store=store)

        self.assertEqual(len(store.observed_backfills), 1)
        self.assertEqual(store.observed_backfills[0]["payload"], store.raiderio_payload)
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["sourceStatus"], "verified")
        self.assertNotIn("not implemented", json.dumps(payload))
        self.assertEqual(store.saved_states[-1][0], postgres_cache_sync.GEAR_OBSERVED_BACKFILL_SYNC_KEY)

    def test_observed_backfill_postgres_forwards_budget_to_store(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        store.raiderio_payload = {"sourceStatus": "verified", "profiles": []}

        payload = postgres_cache_sync.run_gear_observed_backfill_postgres(
            mode="gear_template_first_sync",
            store=store,
            target_limit=7,
            profile_limit=3,
            timeout_seconds=22,
            enable_simc_stats=True,
            full_profile_gear=False,
            item_probe_limit=11,
        )

        self.assertEqual(len(store.observed_backfills), 1)
        call = store.observed_backfills[0]
        self.assertEqual(call["mode"], "gear_template_first_sync")
        self.assertEqual(call["targetLimit"], 7)
        self.assertEqual(call["profileLimit"], 3)
        self.assertEqual(call["timeoutSeconds"], 22)
        self.assertTrue(call["enableSimcStats"])
        self.assertFalse(call["fullProfileGear"])
        self.assertEqual(call["itemProbeLimit"], 11)
        self.assertEqual(payload["targetLimit"], 7)
        self.assertEqual(payload["profileLimit"], 3)
        self.assertEqual(payload["timeoutSeconds"], 22)
        self.assertEqual(payload["itemProbeLimit"], 11)

    def test_crafted_backfill_postgres_calls_seed_row_writer(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        seed_items = [{"itemId": "260100", "slot": "main_hand", "itemLevel": 285, "crafted_stats": "32/49"}]

        with patch.object(postgres_cache_sync, "load_crafted_gear_seed_postgres", return_value=seed_items, create=True):
            payload = postgres_cache_sync.run_crafted_gear_backfill_postgres(mode="scheduled", store=store)

        self.assertEqual(len(store.crafted_backfills), 1)
        self.assertEqual(store.crafted_backfills[0][0], seed_items)
        self.assertEqual(payload["runner"], "postgres")
        self.assertEqual(payload["sourceStatus"], "partial")
        self.assertNotIn("not implemented", json.dumps(payload))
        self.assertEqual(store.saved_states[-1][0], postgres_cache_sync.CRAFTED_GEAR_BACKFILL_SYNC_KEY)

    def test_stat_weight_postgres_sync_builds_and_writes_pg_payloads(self):
        from server import postgres_cache_sync

        store = FakePostgresSyncStore()
        previous_mixed = {
            "classKey": "mage",
            "specKey": "frost",
            "scenarioKey": "mplus_mixed_route",
            "summaryZh": "cached translation",
            "sourceStatus": "verified",
        }
        store.stat_previous[("mage", "frost", "mplus_mixed_route")] = previous_mixed
        spec_meta = {
            "classKey": "mage",
            "specKey": "frost",
            "className": "法师",
            "specName": "冰霜",
            "role": "dps",
            "primaryStat": "intellect",
        }
        raiderio_payload = {"sourceStatus": "verified", "checkedAt": "2026-07-03T00:00:00+00:00"}
        previous_seen = []

        def fake_builder(spec, scenario, raiderio, aggregate, ready_profiles, blocked_notes, previous=None):
            previous_seen.append((scenario["key"], previous))
            self.assertEqual(spec, spec_meta)
            self.assertEqual(raiderio, raiderio_payload)
            self.assertEqual(aggregate["sampleCount"], 5)
            self.assertEqual(len(ready_profiles), 1)
            self.assertEqual(blocked_notes, [])
            return {
                "classKey": spec["classKey"],
                "specKey": spec["specKey"],
                "scenarioKey": scenario["key"],
                "sourceStatus": "verified",
                "checkedAt": "2026-07-03T00:01:00+00:00",
                "weights": [{"key": "haste", "value": "1.00"}],
            }

        with patch.object(postgres_cache_sync, "specialization_registry", return_value=[spec_meta]), patch.object(
            postgres_cache_sync,
            "aggregate_by_spec",
            return_value={"mage:frost": {"sampleCount": 5}},
            create=True,
        ), patch.object(
            postgres_cache_sync,
            "representative_profile_candidates",
            return_value=[{"name": "Mage A"}],
            create=True,
        ), patch.object(
            postgres_cache_sync,
            "ready_profile_candidate",
            return_value={"ready": True, "name": "Mage A", "importCode": "CAE", "gearItems": []},
            create=True,
        ), patch.object(
            postgres_cache_sync,
            "build_scenario_payload_with_previous",
            side_effect=fake_builder,
            create=True,
        ):
            result = postgres_cache_sync.sync_stat_weight_cache_postgres(
                raiderio_payload=raiderio_payload,
                store=store,
            )

        self.assertEqual(len(store.stat_payloads), len(postgres_cache_sync.MPLUS_SCENARIOS))
        self.assertEqual({item["sourceStatus"] for item in store.stat_payloads}, {"verified"})
        self.assertFalse(
            any("PostgreSQL-native stat weight evidence has not been produced yet" in json.dumps(item) for item in store.stat_payloads)
        )
        self.assertEqual(result["acceptedCount"], len(postgres_cache_sync.MPLUS_SCENARIOS))
        self.assertEqual(result["blockedCount"], 0)
        self.assertEqual(result["sourceStatus"], "verified")
        self.assertIn(("mplus_mixed_route", previous_mixed), previous_seen)
        self.assertEqual(store.saved_states[-1][0], "stat_weights_sync")


if __name__ == "__main__":
    unittest.main()
