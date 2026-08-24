import unittest
import copy

from server.s2_equipment_library_simc_matrix import (
    assemble_s2_equipment_library_simc_matrix_report,
    build_s2_equipment_library_simc_matrix_plan,
    parse_simc_runtime_identity,
    rebind_s2_equipment_library_simc_matrix_report,
    validate_s2_enhancement_probe_result,
    validate_s2_item_probe_result,
)


RUNTIME = (
    "simc:12.1.0.69299:"
    "f50a2121bf894570146507496f3e113bff68e445:"
    "69b3e5fb56f3b7149fa239059cb510f1924ef5cd6690db718812df4d938172da"
)


def _canonical(item_id, slot, bonus, level):
    return {
        "status": "verified",
        "itemId": item_id,
        "slot": slot,
        "bonusIds": [bonus],
        "itemLevel": level,
        "itemContextValues": [],
        "line": f"{slot}=s2_item,id={item_id},ilevel={level},bonus_id={bonus}",
    }


def _variant(item_id, slot, bonus, level, key):
    return {
        "itemId": item_id,
        "itemSlot": slot,
        "variantKey": key,
        "status": "verified",
        "canonicalSimcInput": _canonical(item_id, slot, bonus, level),
    }


def _candidate():
    slots = [
        ("1001", "head"),
        ("1002", "neck"),
        ("1003", "shoulder"),
        ("1004", "back"),
        ("1005", "chest"),
        ("1006", "wrist"),
        ("1007", "hands"),
        ("1008", "waist"),
        ("1009", "legs"),
        ("1010", "feet"),
        ("1011", "finger1"),
        ("1012", "trinket1"),
        ("1013", "main_hand"),
        ("1014", "off_hand"),
    ]
    variants = [
        _variant(item_id, slot, str(index + 1), 300, f"variant:{item_id}")
        for index, (item_id, slot) in enumerate(slots)
    ]
    variants.append(
        {
            **_variant("1099", "head", "99", 300, "blocked:variant"),
            "status": "UNVERIFIED",
        }
    )
    variants.append(
        {
            **_variant("1098", "head", "98", 300, "excluded:variant"),
            "status": "excluded",
        }
    )
    variants.append(
        {
            **_variant("1097", "head", "97", 300, "crafted-only:variant"),
            "logicalSources": ["crafted"],
        }
    )
    set_items = ["1001", "1003", "1005", "1007", "1009"]
    return {
        "reportId": "candidate:test",
        "variants": variants,
        "craftedVariantTemplates": [],
        "craftedRelationships": [],
        "setConversions": [
            {
                "itemId": "1001",
                "status": "verified",
                "preservation": {
                    "setMembershipFacts": [
                        {
                            "setId": "2067",
                            "setName": "Jade Warlord's Dominion",
                            "itemIds": set_items,
                            "effects": [
                                {"requiredCount": 2, "displayString": "2pc"},
                                {"requiredCount": 4, "displayString": "4pc"},
                            ],
                        }
                    ]
                },
            }
        ],
    }


def _candidate_with_enhancement_selections():
    candidate = _candidate()
    candidate["enhancementCatalog"] = {
        "canonicalSelections": [
            {
                "optionKey": "enchant-8013",
                "optionType": "enchant",
                "status": "verified",
                "baseItemId": "1005",
                "baseVariantKey": "variant:1005",
                "slot": "chest",
                "canonicalSimcInput": {
                    "status": "verified",
                    "itemId": "1005",
                    "slot": "chest",
                    "simcOptions": {"enchant_id": "8013"},
                    "line": "chest=s2_item,id=1005,ilevel=300,bonus_id=5,enchant_id=8013",
                },
            },
            {
                "optionKey": "gem-240888",
                "optionType": "gem",
                "status": "verified",
                "baseItemId": "1001",
                "baseVariantKey": "variant:1001",
                "slot": "head",
                "canonicalSimcInput": {
                    "status": "verified",
                    "itemId": "1001",
                    "slot": "head",
                    "simcOptions": {"gem_id": "240888"},
                    "line": "head=s2_item,id=1001,ilevel=300,bonus_id=1,gem_id=240888",
                },
            },
            {
                "optionKey": "crafted-stats-32-40",
                "optionType": "crafted_stats",
                "status": "verified",
                "baseItemId": "1005",
                "baseVariantKey": "variant:1005",
                "slot": "chest",
                "canonicalSimcInput": {
                    "status": "verified",
                    "itemId": "1005",
                    "slot": "chest",
                    "simcOptions": {"crafted_stats": "32/40"},
                    "line": "chest=s2_item,id=1005,ilevel=300,bonus_id=5,crafted_stats=32/40",
                },
            },
            {
                "optionKey": "embellishment-adorned_fang",
                "optionType": "embellishment",
                "status": "verified",
                "baseItemId": "1005",
                "baseVariantKey": "variant:1005",
                "slot": "chest",
                "canonicalSimcInput": {
                    "status": "verified",
                    "itemId": "1005",
                    "slot": "chest",
                    "simcOptions": {"embellishment": "adorned_fang"},
                    "line": "chest=s2_item,id=1005,ilevel=300,bonus_id=5,embellishment=adorned_fang",
                },
            },
        ]
    }
    return candidate


class S2EquipmentLibrarySimcMatrixTest(unittest.TestCase):
    def test_runtime_identity_parser_is_strict(self):
        self.assertEqual(parse_simc_runtime_identity(RUNTIME)["build"], "12.1.0.69299")
        self.assertIsNone(parse_simc_runtime_identity("simc:bad"))

    def test_plan_keeps_only_public_variants_and_builds_complete_base_profile(self):
        plan = build_s2_equipment_library_simc_matrix_plan(
            _candidate(),
            runtime_identity=RUNTIME,
            include_set_probe_specs=[("warrior", "arms")],
        )
        self.assertEqual(plan["baseProfile"]["status"], "verified")
        self.assertEqual(plan["baseProfile"]["slotCount"], 16)
        self.assertEqual(plan["probeSpecSelection"]["selected"], ["warrior:arms"])
        public_jobs = [job for job in plan["jobs"] if job["kind"] == "public_variant"]
        self.assertEqual(len(public_jobs), 14)
        self.assertEqual(len(plan["publicVariantBlocked"]), 1)
        self.assertEqual(len(plan["publicVariantExcluded"]), 2)
        self.assertEqual(
            {row["code"] for row in plan["publicVariantExcluded"]},
            {
                "S2_PUBLIC_VARIANT_OUT_OF_SCOPE",
                "S2_CRAFTED_VARIANT_SEPARATE_MATRIX",
            },
        )
        self.assertIn("finger2", next(job for job in plan["jobs"] if job["kind"] == "representative_profile")["profile"])
        representative_job = next(
            job for job in plan["jobs"] if job["kind"] == "representative_profile"
        )
        self.assertIn("iterations=1", representative_job["profile"])
        self.assertIn("max_time=10", representative_job["profile"])
        set_job = next(job for job in plan["jobs"] if job["kind"] == "set_conversion_probe")
        self.assertIn("max_time=1", set_job["profile"])
        self.assertIn("debug=1", set_job["profile"])
        self.assertNotIn("neck=", set_job["profile"])

    def test_default_set_probe_selection_is_class_specific(self):
        plan = build_s2_equipment_library_simc_matrix_plan(
            _candidate(),
            runtime_identity=RUNTIME,
        )
        set_jobs = [
            job for job in plan["jobs"] if job["kind"] == "set_conversion_probe"
        ]
        self.assertTrue(set_jobs)
        self.assertEqual(
            sorted({(job["classKey"], job["specKey"]) for job in set_jobs}),
            [("warrior", "protection")],
        )
        self.assertEqual(
            plan["probeSpecSelection"]["setBySetId"]["2067"],
            ["warrior:protection"],
        )

    def test_item_probe_requires_exact_readback_beyond_returncode_zero(self):
        job = {
            "jobKey": "public:variant:1001",
            "expected": {
                "itemId": "1001",
                "slot": "head",
                "bonusIds": ["1"],
                "itemLevel": 300,
            },
        }
        result = validate_s2_item_probe_result(
            job,
            {
                "returncode": 0,
                "dps": 10,
                "gear": {
                    "head": {
                        "encoded_item": "s2_item,id=9999,bonus_id=1,ilevel=300",
                        "ilevel": 300,
                        "stamina": 1,
                    }
                },
            },
        )
        self.assertEqual(result["status"], "blocked")
        self.assertIn("SIMC_ITEM_PROBE_ITEM_ID_MISMATCH", result["failureCodes"])

    def test_public_variant_probe_is_readback_only_and_uses_short_combat_window(self):
        plan = build_s2_equipment_library_simc_matrix_plan(
            _candidate(),
            runtime_identity=RUNTIME,
            include_set_probe_specs=[("warrior", "arms")],
        )
        job = next(job for job in plan["jobs"] if job["kind"] == "public_variant")
        self.assertEqual(job["probeMode"], "readback")
        self.assertIn("head=", job["profile"])
        self.assertIn("main_hand=", job["profile"])
        self.assertNotIn("chest=", job["profile"])
        self.assertIn("iterations=1", job["profile"])
        self.assertIn("max_time=0.1", job["profile"])
        self.assertIn("default_actions=1", job["profile"])
        self.assertNotIn("s2_item,id=", job["profile"])
        expected = job["expected"]
        result = validate_s2_item_probe_result(
            job,
            {
                "returncode": 0,
                "dps": None,
                "gear": {
                    expected["slot"]: {
                        "encoded_item": (
                            f"s2_item,id={expected['itemId']},"
                            f"bonus_id={'/'.join(expected['bonusIds'])},"
                            f"ilevel={expected['itemLevel']}"
                        ),
                        "ilevel": expected["itemLevel"],
                        "stamina": 1,
                    }
                },
            },
        )
        self.assertEqual(result["status"], "verified")
        self.assertFalse(result["dpsRequired"])
        self.assertIsNone(result["dps"])

        wrist_job = next(
            job for job in plan["jobs"]
            if job["kind"] == "public_variant" and job["itemId"] == "1006"
        )
        self.assertIn("wrists=", wrist_job["profile"])
        self.assertNotIn("\nwrist=", wrist_job["profile"])

    def test_plan_gives_each_crafted_quality_template_its_own_readback_job(self):
        candidate = _candidate()
        candidate["craftedVariantTemplates"] = [
            {
                "variantKey": "s2-crafted:recipe:5001:item:2001:quality:1:track:hero",
                "variantKind": "crafted_quality_template",
                "recipeId": "5001",
                "itemId": "2001",
                "itemSlot": "feet",
                "craftedTrackKey": "hero",
                "craftedTrackCurrencyId": "3445",
                "quality": {"qualityId": "4", "qualityTier": 1},
                "status": "verified",
                "simcReadiness": "blocked",
                "canonicalSimcInput": {
                    "status": "verified",
                    "schemaRevision": "s2-canonical-simc-crafted-quality-input-v1",
                    "itemId": "2001",
                    "slot": "feet",
                    "itemLevel": 305,
                    "bonusIds": ["12214", "13667", "12493"],
                    "itemContextValues": [],
                    "line": "feet=s2_crafted,id=2001,ilevel=305,bonus_id=12214/13667/12493",
                    "simcOptions": {
                        "id": "2001",
                        "ilevel": "305",
                        "bonus_id": "12214/13667/12493",
                    },
                },
            }
        ]
        plan = build_s2_equipment_library_simc_matrix_plan(
            candidate,
            runtime_identity=RUNTIME,
            include_set_probe_specs=[("warrior", "arms")],
        )
        crafted_jobs = [
            job for job in plan["jobs"] if job["kind"] == "crafted_variant"
        ]
        self.assertEqual(len(crafted_jobs), 1)
        self.assertEqual(plan["counts"]["craftedVariantJobCount"], 1)
        self.assertEqual(crafted_jobs[0]["recipeId"], "5001")
        self.assertEqual(crafted_jobs[0]["craftedTrackKey"], "hero")
        self.assertIn("feet=item_2001,id=2001", crafted_jobs[0]["profile"])
        self.assertNotIn("s2_crafted,id=", crafted_jobs[0]["profile"])

        report = assemble_s2_equipment_library_simc_matrix_report(
            candidate,
            plan,
            batch_results=[],
            golden_prefix={"status": "verified", "runtimeIdentity": RUNTIME},
        )
        self.assertEqual(report["craftedVariantMatrix"]["status"], "blocked")
        self.assertIn(
            "SIMC_CRAFTED_VARIANT_MATRIX_UNVERIFIED",
            report["blockerCodes"],
        )

    def test_report_keeps_enhancement_blocker_and_closes_public_matrix_when_results_match(self):
        candidate = _candidate()
        plan = build_s2_equipment_library_simc_matrix_plan(
            candidate,
            runtime_identity=RUNTIME,
            include_set_probe_specs=[("warrior", "arms")],
        )
        batches = []
        results = []
        for job in plan["jobs"]:
            if job["kind"] == "public_variant":
                expected = job["expected"]
                slot = expected["slot"]
                simc_slot = {"shoulder": "shoulders", "wrist": "wrists"}.get(
                    slot, slot
                )
                results.append(
                    {
                        "jobKey": job["jobKey"],
                        "returncode": 0,
                        "dps": 10,
                        "gear": {
                            simc_slot: {
                                "encoded_item": (
                                    f"s2_item,id={expected['itemId']},"
                                    f"bonus_id={'/'.join(expected['bonusIds'])},"
                                    f"ilevel={expected['itemLevel']}"
                                ),
                                "ilevel": expected["itemLevel"],
                                "stamina": 1,
                            }
                        },
                    }
                )
            elif job["kind"] == "representative_profile":
                results.append(
                    {
                        "jobKey": job["jobKey"],
                        "returncode": 0,
                        "dps": 10,
                        "gear": {slot: {} for slot in plan["baseProfile"]["slots"]},
                    }
                )
            else:
                set_gear = {}
                for variant in candidate["variants"]:
                    if variant["itemId"] not in job["setItemIds"]:
                        continue
                    canonical = variant["canonicalSimcInput"]
                    slot = variant["itemSlot"]
                    set_gear[slot] = {
                        "encoded_item": (
                            f"s2_item,id={variant['itemId']},"
                            f"bonus_id={'/'.join(canonical['bonusIds'])},"
                            f"ilevel={canonical['itemLevel']}"
                        ),
                        "ilevel": canonical["itemLevel"],
                        "stamina": 1,
                    }
                results.append(
                    {
                        "jobKey": job["jobKey"],
                        "returncode": 0,
                        "dps": 10 if job["enabled"] else 5,
                        "gear": set_gear,
                        "setBonusInitializationLines": (
                            [
                                "0.000 Initialized set bonus: { Jade Warlord's Dominion, "
                                f"test_set, Test Spec, {job['requiredCount']} piece bonus  }}"
                            ]
                            if job["enabled"]
                            else []
                        ),
                    }
                )
        batches.append(
            {
                "runtimeIdentityStatus": "verified",
                "runtimeIdentity": RUNTIME,
                "results": results,
            }
        )
        report = assemble_s2_equipment_library_simc_matrix_report(
            candidate,
            plan,
            batch_results=batches,
            golden_prefix={"status": "verified", "runtimeIdentity": RUNTIME, "reportId": "golden"},
        )
        self.assertEqual(report["publicVariantMatrix"]["status"], "verified")
        self.assertEqual(report["representativeProfileMatrix"]["status"], "verified")
        self.assertEqual(report["setConversionMatrix"]["status"], "verified")
        self.assertEqual(report["enhancementMatrix"]["status"], "UNVERIFIED")
        self.assertIn("SIMC_ENHANCEMENT_MATRIX_UNVERIFIED", report["blockerCodes"])

        missing_set_readback = copy.deepcopy(batches)
        missing_set_readback[0]["results"][
            next(
                index
                for index, row in enumerate(missing_set_readback[0]["results"])
                if ":enabled" in row["jobKey"]
            )
        ]["gear"] = {}
        blocked_report = assemble_s2_equipment_library_simc_matrix_report(
            candidate,
            plan,
            batch_results=missing_set_readback,
            golden_prefix={
                "status": "verified",
                "runtimeIdentity": RUNTIME,
                "reportId": "golden",
            },
        )
        self.assertEqual(blocked_report["setConversionMatrix"]["status"], "blocked")
        self.assertIn(
            "SIMC_SET_CONVERSION_SET_ITEM_READBACK_UNVERIFIED",
            blocked_report["setConversionMatrix"]["results"][0]["failureCodes"],
        )

        missing_initialization = copy.deepcopy(batches)
        missing_initialization[0]["results"][
            next(
                index
                for index, row in enumerate(missing_initialization[0]["results"])
                if ":enabled" in row["jobKey"]
            )
        ]["setBonusInitializationLines"] = []
        blocked_initialization = assemble_s2_equipment_library_simc_matrix_report(
            candidate,
            plan,
            batch_results=missing_initialization,
            golden_prefix={
                "status": "verified",
                "runtimeIdentity": RUNTIME,
                "reportId": "golden",
            },
        )
        self.assertEqual(blocked_initialization["setConversionMatrix"]["status"], "blocked")
        self.assertIn(
            "SIMC_SET_EFFECT_INITIALIZATION_NOT_OBSERVED",
            blocked_initialization["setConversionMatrix"]["results"][0]["failureCodes"],
        )

    def test_plan_builds_exact_enhancement_readback_jobs(self):
        plan = build_s2_equipment_library_simc_matrix_plan(
            _candidate_with_enhancement_selections(),
            runtime_identity=RUNTIME,
            include_set_probe_specs=[("warrior", "arms")],
        )
        jobs = [job for job in plan["jobs"] if job["kind"] == "enhancement_probe"]
        self.assertEqual(len(jobs), 4)
        by_key = {job["optionKey"]: job for job in jobs}
        self.assertEqual(by_key["enchant-8013"]["probeMode"], "enhancement_readback")
        self.assertEqual(by_key["enchant-8013"]["expected"]["simcOptions"], {"enchant_id": "8013"})
        self.assertIn("enchant_id=8013", by_key["enchant-8013"]["profile"])
        self.assertIn("gem_id=240888", by_key["gem-240888"]["profile"])
        self.assertIn("crafted_stats=32/40", by_key["crafted-stats-32-40"]["profile"])
        self.assertIn("embellishment=adorned_fang", by_key["embellishment-adorned_fang"]["profile"])

    def test_enhancement_probe_requires_exact_option_readback(self):
        plan = build_s2_equipment_library_simc_matrix_plan(
            _candidate_with_enhancement_selections(),
            runtime_identity=RUNTIME,
            include_set_probe_specs=[("warrior", "arms")],
        )
        job = next(
            job for job in plan["jobs"] if job["kind"] == "enhancement_probe" and job["optionKey"] == "enchant-8013"
        )
        expected = job["expected"]
        result = validate_s2_enhancement_probe_result(
            job,
            {
                "returncode": 0,
                "gear": {
                    "chest": {
                        "encoded_item": "s2_item,id=1005,bonus_id=5,ilevel=300,enchant_id=8013",
                        "ilevel": 300,
                        "stamina": 1,
                    }
                },
            },
        )
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["observedSimcOptions"], expected["simcOptions"])

        missing_option = validate_s2_enhancement_probe_result(
            job,
            {
                "returncode": 0,
                "gear": {
                    "chest": {
                        "encoded_item": "s2_item,id=1005,bonus_id=5,ilevel=300",
                        "ilevel": 300,
                        "stamina": 1,
                    }
                },
            },
        )
        self.assertEqual(missing_option["status"], "blocked")
        self.assertIn("SIMC_ENHANCEMENT_OPTION_READBACK_MISSING", missing_option["failureCodes"])

    def test_report_closes_enhancement_matrix_only_after_all_option_readbacks(self):
        candidate = _candidate_with_enhancement_selections()
        plan = build_s2_equipment_library_simc_matrix_plan(
            candidate,
            runtime_identity=RUNTIME,
            include_set_probe_specs=[("warrior", "arms")],
        )
        results = []
        for job in plan["jobs"]:
            if job["kind"] != "enhancement_probe":
                continue
            expected = job["expected"]
            options = ",".join(
                f"{key}={value}" for key, value in expected["simcOptions"].items()
            )
            results.append(
                {
                    "jobKey": job["jobKey"],
                    "returncode": 0,
                    "gear": {
                        {"shoulder": "shoulders", "wrist": "wrists"}.get(expected["slot"], expected["slot"]): {
                            "encoded_item": (
                                f"s2_item,id={expected['itemId']},"
                                f"bonus_id={'/'.join(expected['bonusIds'])},"
                                f"ilevel={expected['itemLevel']},{options}"
                            ),
                            "ilevel": expected["itemLevel"],
                            "stamina": 1,
                        }
                    },
                }
            )
        report = assemble_s2_equipment_library_simc_matrix_report(
            candidate,
            plan,
            batch_results=[
                {
                    "runtimeIdentityStatus": "verified",
                    "runtimeIdentity": RUNTIME,
                    "results": results,
                }
            ],
            golden_prefix={"status": "verified", "runtimeIdentity": RUNTIME, "reportId": "golden"},
        )
        self.assertEqual(report["enhancementMatrix"]["status"], "verified")
        self.assertEqual(report["enhancementMatrix"]["canonicalSelectionCount"], 4)
        self.assertEqual(report["enhancementMatrix"]["verifiedProbeCount"], 4)
        self.assertNotIn("SIMC_ENHANCEMENT_MATRIX_UNVERIFIED", report["blockerCodes"])

    def test_matrix_rebind_requires_exact_plan_equivalence_and_records_provenance(self):
        candidate = _candidate()
        candidate["reportId"] = "candidate:new"
        source_candidate = {**candidate, "reportId": "candidate:old"}
        source_plan = build_s2_equipment_library_simc_matrix_plan(
            source_candidate,
            runtime_identity=RUNTIME,
            include_set_probe_specs=[("warrior", "arms")],
        )
        target_plan = build_s2_equipment_library_simc_matrix_plan(
            candidate,
            runtime_identity=RUNTIME,
            include_set_probe_specs=[("warrior", "arms")],
        )
        source_report = assemble_s2_equipment_library_simc_matrix_report(
            source_candidate,
            source_plan,
            batch_results=[],
            golden_prefix={"status": "verified", "runtimeIdentity": RUNTIME},
        )
        source_report["runtimeIdentityStatus"] = "verified"

        rebound = rebind_s2_equipment_library_simc_matrix_report(
            candidate,
            source_report,
            source_plan,
            target_plan,
            golden_prefix={"status": "verified", "runtimeIdentity": RUNTIME},
        )

        self.assertEqual(rebound["candidateReportId"], "candidate:new")
        self.assertEqual(rebound["candidateIdentity"], "candidate:new")
        self.assertEqual(rebound["matrixReuse"]["mode"], "strict_plan_equivalent_reuse")
        self.assertEqual(rebound["matrixReuse"]["jobCount"], len(source_plan["jobs"]))
        self.assertEqual(rebound["matrixReuse"]["sourceReportId"], source_report["reportId"])
        self.assertEqual(rebound["reportId"], rebound["matrixReuse"]["reportId"])

        changed_plan = copy.deepcopy(target_plan)
        changed_plan["jobs"][0]["profile"] += "\n# changed\n"
        with self.assertRaises(ValueError):
            rebind_s2_equipment_library_simc_matrix_report(
                candidate,
                source_report,
                source_plan,
                changed_plan,
                golden_prefix={"status": "verified", "runtimeIdentity": RUNTIME},
            )


if __name__ == "__main__":
    unittest.main()
