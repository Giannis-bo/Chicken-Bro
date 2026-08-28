import hashlib
import json
from pathlib import Path


ALLOWLIST_REVISION = "s2-limited-client-db2-field-allowlist-v1"
CLIENT_BUILD = "12.1.0.68914"
SIMC_COMMIT = "f50a2121bf894570146507496f3e113bff68e445"


def _write_json(path: Path, value) -> bytes:
    body = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return body


def write_crafted_capture(root: Path) -> Path:
    rows_by_table = {
        "SkillLineAbility": [{"ID": 52446, "Spell": 1229890}],
        "SpellEffect": [
            {"SpellID": 1229890, "Effect": 288, "EffectMiscValue_0": 2826}
        ],
        "CraftingData": [
            {"ID": 2826, "CraftedItemID": 244767, "CraftingDifficultyID": 900}
        ],
        "CraftingDifficultyQuality": [
            {
                "ID": quality_id,
                "CraftingDifficultyID": 900,
                "CraftingQualityID": quality_id,
                "QualityPercentage": percentage,
            }
            for quality_id, percentage in enumerate((0, 20, 50, 80, 100), 1)
        ],
        "CraftingQuality": [
            {"ID": quality_id, "QualityTier": quality_id}
            for quality_id in range(1, 6)
        ],
        "ModifiedCraftingSpellSlot": [
            {
                "ID": 1,
                "SpellID": 1229890,
                "Slot": 1,
                "ModifiedCraftingReagentSlotID": 459,
            },
            {
                "ID": 2,
                "SpellID": 1229890,
                "Slot": 2,
                "ModifiedCraftingReagentSlotID": 502,
            },
        ],
        "ModifiedCraftingReagentSlot": [
            {
                "ID": 459,
                "Name_lang": "Amplify Secondary Stat",
                "ReagentType": 1,
                "ReagentSource": 1,
            },
            {
                "ID": 502,
                "Name_lang": "Add Embellishment",
                "ReagentType": 1,
                "ReagentSource": 1,
            },
        ],
        "ModifiedCraftingReagentItem": [
            {
                "ID": 1001,
                "ModifiedCraftingCategoryID": 459,
                "ItemBonusTreeID": 7001,
                "Description_lang": "Secondary stat candidate without semantic authority",
            },
            {
                "ID": 1002,
                "ModifiedCraftingCategoryID": 502,
                "ItemBonusTreeID": 7002,
                "Description_lang": "Embellishment candidate without effect authority",
            },
        ],
        "ModifiedCraftingItem": [
            {"ModifiedCraftingReagentItemID": 1001, "ItemID": 3001},
            {"ModifiedCraftingReagentItemID": 1002, "ItemID": 3002},
        ],
        "CraftingReagentQuality": [
            {"ID": 1, "ModifiedCraftingCategoryID": 459, "ItemID": 4001},
            {"ID": 2, "ModifiedCraftingCategoryID": 502, "ItemID": 4002},
        ],
    }
    entries = []
    for table, rows in rows_by_table.items():
        fields = list(dict.fromkeys(key for row in rows for key in row))
        body = json.dumps(
            rows,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        body_sha256 = hashlib.sha256(body).hexdigest()
        relative = f"responses/{table}.json"
        record = {
            "table": table,
            "fields": fields,
            "rows": rows,
            "bodySha256": body_sha256,
            "bodyBytes": len(body),
        }
        _write_json(root / relative, record)
        entries.append(
            {
                "table": table,
                "responsePath": relative,
                "bodySha256": body_sha256,
                "bodyBytes": len(body),
            }
        )
    _write_json(
        root / "capture-manifest.json",
        {
            "status": "captured",
            "clientBuild": CLIENT_BUILD,
            "allowlistRevision": ALLOWLIST_REVISION,
            "rawDb2Persisted": False,
            "requestCount": len(entries),
            "entries": entries,
        },
    )
    return root


def write_simc_probe(path: Path) -> Path:
    _write_json(
        path,
        {
            "schemaRevision": "s2-crafted-simc-probe-v1",
            "runtimeIdentity": {
                "build": "12.1.0.69299",
                "commit": SIMC_COMMIT,
                "binarySha256": "a" * 64,
            },
            "sourceCompatibilityVerified": False,
            "probes": [
                {
                    "option": "32/36",
                    "returncode": 0,
                    "encodedItem": (
                        "quel_dorei_softsteppers,id=244767,"
                        "ilevel=285,crafted_stats=32/36"
                    ),
                    "itemLevel": 285,
                    "stats": {"intellect": 90, "stamina": 1664},
                    "stderr": "",
                }
            ],
        },
    )
    return path
