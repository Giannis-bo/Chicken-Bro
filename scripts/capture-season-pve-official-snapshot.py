#!/usr/bin/env python3
"""Capture official Blizzard PVE discovery inputs without touching project data.

This command performs only HTTPS reads and writes immutable JSON responses under
the caller-provided output directory. It never opens PostgreSQL, runs a sync,
builds a Catalog, starts SimC, or changes an active pointer.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.season_pve_official_capture import (  # noqa: E402
    OfficialCaptureContractError,
    bounded_capture_result,
    canonical_official_name,
    equipment_recipe_refs,
    index_official_item_search,
    journal_loot_reference,
    recipe_candidates_from_complete_item_index,
    select_journal_targets,
)
from server.season_pve_event_schedule import (  # noqa: E402
    select_active_timewalking_rotation,
)


CAPTURE_SCHEMA_REVISION = "season-pve-official-capture-v1"
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MYTHIC_DUNGEON_IDS = ("558", "560", "559", "557", "402", "556", "239", "161")
PROFESSION_IDS = {
    "Blacksmithing": "164",
    "Leatherworking": "165",
    "Tailoring": "197",
    "Engineering": "202",
    "Enchanting": "333",
    "Jewelcrafting": "755",
    "Alchemy": "171",
    "Inscription": "773",
}
CLASS_SET_NAMES = (
    "Relentless Rider's Lament",
    "Devouring Reaver's Sheathe",
    "Sprouts of the Luminous Bloom",
    "Livery of the Black Talon",
    "Primal Sentry's Camouflage",
    "Voidbreaker's Accordance",
    "Way of Ra-den's Chosen",
    "Luminant Verdict's Vestments",
    "Blind Oath's Burden",
    "Motley of the Grim Jest",
    "Mantle of the Primal Core",
    "Reign of the Abyssal Immolator",
    "Rage of the Night Ender",
)
TIMEWALKING_ROTATIONS = (
    {
        "rotationKey": "dragonflight-opening",
        "expansionName": "Dragonflight",
        "startsAt": "2026-06-30T00:00:00Z",
        "endsAt": "2026-07-07T00:00:00Z",
        "dungeonNames": [
            "Algeth'ar Academy",
            "Halls of Infusion",
            "Neltharus",
            "Ruby Life Pools",
            "The Azure Vault",
            "Brackenhide Hollow",
        ],
    },
    {
        "rotationKey": "battle-for-azeroth",
        "expansionName": "Battle for Azeroth",
        "startsAt": "2026-07-07T00:00:00Z",
        "endsAt": "2026-07-14T00:00:00Z",
        "dungeonNames": [
            "Atal'Dazar",
            "Freehold",
            "King's Rest",
            "Shrine of the Storm",
            "Temple of Sethraliss",
            "Waycrest Manor",
        ],
    },
    {
        "rotationKey": "shadowlands",
        "expansionName": "Shadowlands",
        "startsAt": "2026-07-14T00:00:00Z",
        "endsAt": "2026-07-21T00:00:00Z",
        "dungeonNames": [
            "De Other Side",
            "Spires of Ascension",
            "Plaguefall",
            "The Necrotic Wake",
            "Sanguine Depths",
            "Halls of Atonement",
        ],
    },
    {
        "rotationKey": "classic",
        "expansionName": "Classic",
        "startsAt": "2026-07-21T00:00:00Z",
        "endsAt": "2026-07-28T00:00:00Z",
        "dungeonNames": [
            "The Deadmines",
            "Dire Maul - East",
            "Dire Maul - West",
            "Stratholme",
            "Zul'Farrak",
        ],
    },
    {
        "rotationKey": "the-burning-crusade",
        "expansionName": "Burning Crusade",
        "startsAt": "2026-07-28T00:00:00Z",
        "endsAt": "2026-08-04T00:00:00Z",
        "dungeonNames": [
            "Magisters' Terrace",
            "Mana-Tombs",
            "The Blood Furnace",
            "The Botanica",
            "The Shattered Halls",
            "The Underbog",
        ],
    },
    {
        "rotationKey": "dragonflight-closing",
        "expansionName": "Dragonflight",
        "startsAt": "2026-08-04T00:00:00Z",
        "endsAt": "2026-08-12T00:00:00Z",
        "dungeonNames": [
            "Algeth'ar Academy",
            "Halls of Infusion",
            "Neltharus",
            "Ruby Life Pools",
            "The Azure Vault",
            "Brackenhide Hollow",
        ],
    },
)


def _json_bytes(value):
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _sha256(value):
    return hashlib.sha256(value).hexdigest()


def _instant(value, label):
    raw = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise OfficialCaptureContractError(
            f"{label} requires an ISO-8601 instant"
        ) from error
    if parsed.tzinfo is None:
        raise OfficialCaptureContractError(f"{label} requires a timezone")
    return parsed.astimezone(timezone.utc)


def _load_environment_file(path):
    if not path:
        return
    source = Path(path).expanduser().resolve()
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]
        os.environ[key] = value


def _extract_ref_id(value):
    if not isinstance(value, dict):
        return ""
    direct = str(value.get("id") or "").strip()
    if direct:
        return direct
    href = str(((value.get("key") or {}).get("href")) or "").strip()
    tail = href.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return tail if tail.isdigit() else ""


def _list(payload, *keys):
    for key in keys:
        value = payload.get(key) if isinstance(payload, dict) else None
        if isinstance(value, list):
            return value
    return []


class CaptureWriter:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.requests = []

    def write_json(self, relative_path, payload, *, request=None):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        body = _json_bytes(payload)
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        temporary.write_bytes(body)
        os.replace(temporary, path)
        record = {
            "relativePath": path.relative_to(self.root).as_posix(),
            "sha256": _sha256(body),
            "bytes": len(body),
        }
        if request:
            record["request"] = request
            self.requests.append(record)
        return record


class BlizzardClient:
    def __init__(self, writer, *, region, locale, timeout_seconds, retries):
        self.writer = writer
        self.region = region
        self.locale = locale
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.token = self._oauth_token()

    def _oauth_token(self):
        client_id = (
            os.environ.get("WOW_BLIZZARD_CLIENT_ID")
            or os.environ.get("WOW_BNET_CLIENT_ID")
            or ""
        ).strip()
        client_secret = (
            os.environ.get("WOW_BLIZZARD_CLIENT_SECRET")
            or os.environ.get("WOW_BNET_CLIENT_SECRET")
            or ""
        ).strip()
        if not client_id or not client_secret:
            raise OfficialCaptureContractError(
                "Blizzard API credentials are not configured"
            )
        credentials = base64.b64encode(
            f"{client_id}:{client_secret}".encode("utf-8")
        ).decode("ascii")
        request = Request(
            "https://oauth.battle.net/token",
            data=urlencode({"grant_type": "client_credentials"}).encode("utf-8"),
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "wow-mini-program-season-pve-audit/1.0",
            },
            method="POST",
        )
        payload = self._read_json(request, "Blizzard OAuth")
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise OfficialCaptureContractError(
                "Blizzard OAuth response omitted access_token"
            )
        return token

    def _read_json(self, request, label):
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                with urlopen(
                    request,
                    timeout=self.timeout_seconds,
                ) as response:
                    body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise OfficialCaptureContractError(
                        f"{label} exceeds {MAX_RESPONSE_BYTES} bytes"
                    )
                payload = json.loads(body.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise OfficialCaptureContractError(
                        f"{label} response must be an object"
                    )
                return payload
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
                last_error = error
                if attempt < self.retries:
                    time.sleep(min(2 ** (attempt - 1), 4))
        raise OfficialCaptureContractError(
            f"{label} failed after {self.retries} attempts: "
            f"{type(last_error).__name__}"
        ) from last_error

    def get(
        self,
        path,
        relative_path,
        *,
        namespace="static",
        locale=None,
        params=None,
    ):
        resolved_namespace = (
            namespace
            if "-" in namespace
            else f"{namespace}-{self.region}"
        )
        query = {
            "namespace": resolved_namespace,
            "locale": locale or self.locale,
            **(params or {}),
        }
        url = (
            f"https://{self.region}.api.blizzard.com"
            f"{quote(path, safe='/%')}?{urlencode(query)}"
        )
        request = Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "User-Agent": "wow-mini-program-season-pve-audit/1.0",
            },
        )
        payload = self._read_json(request, path)
        self.writer.write_json(
            relative_path,
            payload,
            request={
                "method": "GET",
                "path": path,
                "namespace": resolved_namespace,
                "locale": locale or self.locale,
                "params": params or {},
            },
        )
        return payload


def _find_by_name(rows, names):
    expected = {
        canonical_official_name(name): name
        for name in names
    }
    found = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = canonical_official_name(row.get("name"))
        if key in expected:
            found[key] = row
    missing = [
        name
        for key, name in expected.items()
        if key not in found
    ]
    return found, sorted(missing)


def _capture_journal_tree(client, groups):
    captured_instances = {}
    captured_encounters = {}
    item_contexts = {}
    for source_group, targets in sorted(groups.items()):
        if source_group == "gaps":
            continue
        for target in targets:
            instance_id = target["instanceId"]
            if instance_id not in captured_instances:
                instance = client.get(
                    f"/data/wow/journal-instance/{instance_id}",
                    f"raw/game-data/journal/instances/{instance_id}.json",
                )
                captured_instances[instance_id] = instance
            instance = captured_instances[instance_id]
            encounter_refs = _list(instance, "encounters")
            if not encounter_refs:
                groups["gaps"].append(
                    {
                        "reasonCode": "OFFICIAL_JOURNAL_INSTANCE_EMPTY",
                        "sourceGroup": source_group,
                        "instanceId": instance_id,
                        "name": target["name"],
                    }
                )
            for encounter_ref in encounter_refs:
                encounter_id = _extract_ref_id(encounter_ref)
                if not encounter_id:
                    groups["gaps"].append(
                        {
                            "reasonCode": "OFFICIAL_JOURNAL_ENCOUNTER_ID_MISSING",
                            "sourceGroup": source_group,
                            "instanceId": instance_id,
                        }
                    )
                    continue
                if encounter_id not in captured_encounters:
                    encounter = client.get(
                        f"/data/wow/journal-encounter/{encounter_id}",
                        (
                            "raw/game-data/journal/encounters/"
                            f"{encounter_id}.json"
                        ),
                    )
                    captured_encounters[encounter_id] = encounter
                encounter = captured_encounters[encounter_id]
                for loot_ref in _list(encounter, "items", "loot"):
                    try:
                        loot = journal_loot_reference(loot_ref)
                    except OfficialCaptureContractError:
                        groups["gaps"].append(
                            {
                                "reasonCode": (
                                    "OFFICIAL_JOURNAL_LOOT_IDENTITY_MISSING"
                                ),
                                "sourceGroup": source_group,
                                "instanceId": instance_id,
                                "encounterId": encounter_id,
                            }
                        )
                        continue
                    item_id = loot["itemId"]
                    item_contexts.setdefault(item_id, []).append(
                        {
                            "sourceGroup": source_group,
                            "instanceId": instance_id,
                            "instanceName": target["name"],
                            "encounterId": encounter_id,
                            "encounterName": str(
                                encounter.get("name") or ""
                            ).strip(),
                            "lootRelationId": loot["lootRelationId"],
                        }
                    )
    return {
        "instanceCount": len(captured_instances),
        "encounterCount": len(captured_encounters),
        "itemCount": len(item_contexts),
        "itemContexts": dict(
            sorted(
                item_contexts.items(),
                key=lambda row: int(row[0]),
            )
        ),
    }


def capture(args):
    _load_environment_file(args.env_file)
    captured_at = _instant(args.captured_at, "captured-at")
    as_of = _instant(args.as_of, "as-of")
    if captured_at > as_of:
        raise OfficialCaptureContractError(
            "captured-at cannot be after as-of"
        )
    writer = CaptureWriter(args.output)
    client = BlizzardClient(
        writer,
        region=args.region,
        locale=args.locale,
        timeout_seconds=args.timeout_seconds,
        retries=args.retries,
    )

    item_search = client.get(
        "/data/wow/search/item",
        "raw/game-data/items/required-level-90-equippable.json",
        params={
            "required_level": 90,
            "is_equippable": "true",
            "_pageSize": 1000,
            "_page": 1,
            "orderby": "id",
        },
    )
    item_index = index_official_item_search(item_search)

    mythic_season_index = client.get(
        "/data/wow/mythic-keystone/season/index",
        "raw/game-data/mythic/season-index.json",
        namespace="dynamic",
    )
    current_season_id = _extract_ref_id(
        mythic_season_index.get("current_season") or {}
    )
    if not current_season_id:
        raise OfficialCaptureContractError(
            "Mythic Keystone season index omitted current_season"
        )
    mythic_season = client.get(
        f"/data/wow/mythic-keystone/season/{current_season_id}",
        (
            "raw/game-data/mythic/seasons/"
            f"{current_season_id}.json"
        ),
        namespace="dynamic",
    )
    mythic_dungeons = [
        client.get(
            f"/data/wow/mythic-keystone/dungeon/{dungeon_id}",
            (
                "raw/game-data/mythic/dungeons/"
                f"{dungeon_id}.json"
            ),
            namespace="dynamic",
        )
        for dungeon_id in MYTHIC_DUNGEON_IDS
    ]

    expansion_index = client.get(
        "/data/wow/journal-expansion/index",
        "raw/game-data/journal/expansion-index.json",
    )
    midnight_expansion = client.get(
        "/data/wow/journal-expansion/516",
        "raw/game-data/journal/expansions/516-midnight.json",
    )
    current_expansion = client.get(
        "/data/wow/journal-expansion/505",
        "raw/game-data/journal/expansions/505-current-season.json",
    )
    timewalking_rotation = select_active_timewalking_rotation(
        list(TIMEWALKING_ROTATIONS),
        as_of.isoformat(),
    )
    expansion_rows = _list(expansion_index, "tiers", "expansions")
    timewalking_expansion_matches, missing_timewalking_expansion = _find_by_name(
        expansion_rows,
        [timewalking_rotation["expansionName"]],
    )
    if missing_timewalking_expansion:
        raise OfficialCaptureContractError(
            "official Journal expansion index omitted active Timewalking "
            f"expansion {timewalking_rotation['expansionName']}"
        )
    timewalking_expansion_ref = next(
        iter(timewalking_expansion_matches.values())
    )
    timewalking_expansion_id = _extract_ref_id(
        timewalking_expansion_ref
    )
    timewalking_expansion = client.get(
        f"/data/wow/journal-expansion/{timewalking_expansion_id}",
        (
            "raw/game-data/journal/expansions/"
            f"{timewalking_expansion_id}-"
            f"{timewalking_rotation['rotationKey']}.json"
        ),
    )
    timewalking_index = {
        "instances": _list(
            timewalking_expansion,
            "dungeons",
            "instances",
        )
    }
    journal_targets = select_journal_targets(
        mythic_dungeons=mythic_dungeons,
        midnight_expansion=midnight_expansion,
        journal_instance_index=timewalking_index,
        timewalking_names=timewalking_rotation["dungeonNames"],
    )
    journal_capture = _capture_journal_tree(
        client,
        journal_targets,
    )

    profession_index = client.get(
        "/data/wow/profession/index",
        "raw/game-data/professions/index.json",
    )
    profession_recipe_rows = []
    recipe_resolution_gaps = []
    for profession_name, profession_id in PROFESSION_IDS.items():
        profession = client.get(
            f"/data/wow/profession/{profession_id}",
            (
                "raw/game-data/professions/"
                f"{profession_id}.json"
            ),
        )
        tier_refs = _list(profession, "skill_tiers")
        tier_matches, missing_tier = _find_by_name(
            tier_refs,
            [f"Midnight {profession_name}"],
        )
        if missing_tier:
            recipe_resolution_gaps.append(
                {
                    "reasonCode": "OFFICIAL_PROFESSION_TIER_MISSING",
                    "profession": profession_name,
                }
            )
            continue
        tier_ref = next(iter(tier_matches.values()))
        tier_id = _extract_ref_id(tier_ref)
        tier = client.get(
            (
                f"/data/wow/profession/{profession_id}"
                f"/skill-tier/{tier_id}"
            ),
            (
                "raw/game-data/professions/skill-tiers/"
                f"{profession_id}-{tier_id}.json"
            ),
        )
        for recipe in equipment_recipe_refs(
            profession_name,
            tier,
        ):
            recipe_id = recipe["recipeId"]
            client.get(
                f"/data/wow/recipe/{recipe_id}",
                (
                    "raw/game-data/professions/recipes/"
                    f"{recipe_id}.json"
                ),
            )
            candidate_projection = (
                recipe_candidates_from_complete_item_index(
                    item_index,
                    recipe["name"],
                )
            )
            matches = candidate_projection["matches"]
            candidate_join_method = candidate_projection[
                "candidateJoinMethod"
            ]
            profession_recipe_rows.append(
                {
                    **recipe,
                    "candidateItemIds": [
                        str(match["id"])
                        for match in matches
                    ],
                    "candidateJoinMethod": candidate_join_method,
                    "candidateSearchRefs": [],
                    "membershipStatus": "candidate_unproven",
                }
            )
            recipe_resolution_gaps.append(
                {
                    "reasonCode": (
                        "OFFICIAL_RECIPE_OUTPUT_ITEM_ID_UNAVAILABLE"
                    ),
                    **recipe,
                    "candidateMatchCount": len(matches),
                    "candidateItemIds": [
                        str(match["id"])
                        for match in matches
                    ],
                }
            )

    item_set_index = client.get(
        "/data/wow/item-set/index",
        "raw/game-data/item-sets/index.json",
    )
    set_matches, missing_sets = _find_by_name(
        _list(item_set_index, "item_sets"),
        CLASS_SET_NAMES,
    )
    captured_sets = []
    for set_name in CLASS_SET_NAMES:
        set_ref = set_matches.get(canonical_official_name(set_name))
        if not set_ref:
            continue
        set_id = _extract_ref_id(set_ref)
        item_set = client.get(
            f"/data/wow/item-set/{set_id}",
            f"raw/game-data/item-sets/{set_id}.json",
        )
        captured_sets.append(
            {
                "itemSetId": set_id,
                "name": set_name,
                "itemIds": sorted(
                    {
                        _extract_ref_id(item)
                        for item in _list(item_set, "items")
                        if _extract_ref_id(item)
                    },
                    key=int,
                ),
            }
        )

    gaps = [
        *journal_targets["gaps"],
        *recipe_resolution_gaps,
        *[
            {
                "reasonCode": "OFFICIAL_CLASS_SET_MISSING",
                "name": name,
            }
            for name in missing_sets
        ],
    ]
    summary = {
        "schemaVersion": 1,
        "schemaRevision": CAPTURE_SCHEMA_REVISION,
        "status": "blocked" if gaps else "captured",
        "capturedAt": captured_at.isoformat().replace("+00:00", "Z"),
        "asOf": as_of.isoformat().replace("+00:00", "Z"),
        "region": args.region,
        "locale": args.locale,
        "requestCount": len(writer.requests),
        "requestBytes": sum(row["bytes"] for row in writer.requests),
        "officialItemSearch": {
            "requiredLevel": 90,
            "equippable": True,
            "itemCount": sum(len(rows) for rows in item_index.values()),
            "distinctNameCount": len(item_index),
            "resultCountCapped": item_search.get("resultCountCapped") is True,
        },
        "mythicSeason": {
            "seasonId": current_season_id,
            "seasonName": mythic_season.get("season_name") or "",
            "dungeonCount": len(mythic_dungeons),
        },
        "journalTargets": {
            key: rows
            for key, rows in journal_targets.items()
            if key != "gaps"
        },
        "timewalkingRotation": timewalking_rotation,
        "journalCapture": journal_capture,
        "professionCapture": {
            "professionIndexCount": len(
                _list(profession_index, "professions")
            ),
            "recipeCount": len(profession_recipe_rows),
            "exactNameCandidateCount": sum(
                1
                for row in profession_recipe_rows
                if row["candidateJoinMethod"]
                == "level_90_equippable_name_unique"
            ),
            "level90NameCandidateCount": sum(
                1
                for row in profession_recipe_rows
                if row["candidateJoinMethod"]
                == "level_90_equippable_name_unique"
            ),
            "exactSearchCandidateCount": 0,
            "membershipComplete": False,
            "recipes": sorted(
                profession_recipe_rows,
                key=lambda row: (
                    row["profession"],
                    row["category"],
                    int(row["recipeId"]),
                ),
            ),
        },
        "classSetCapture": {
            "setCount": len(captured_sets),
            "sets": captured_sets,
        },
        "currentSeasonExpansion": {
            "id": str(current_expansion.get("id") or ""),
            "name": current_expansion.get("name") or "",
        },
        "gaps": sorted(
            gaps,
            key=lambda row: (
                row.get("reasonCode") or "",
                row.get("profession") or "",
                row.get("name") or "",
            ),
        ),
    }
    writer.write_json("official-game-data-capture.json", summary)
    manifest = {
        "schemaVersion": 1,
        "schemaRevision": CAPTURE_SCHEMA_REVISION,
        "status": summary["status"],
        "capturedAt": summary["capturedAt"],
        "asOf": summary["asOf"],
        "requestCount": len(writer.requests),
        "requestBytes": sum(row["bytes"] for row in writer.requests),
        "requests": writer.requests,
        "summary": {
            "officialItemCount": summary["officialItemSearch"]["itemCount"],
            "journalInstanceCount": journal_capture["instanceCount"],
            "journalEncounterCount": journal_capture["encounterCount"],
            "journalItemCount": journal_capture["itemCount"],
            "professionRecipeCount": len(profession_recipe_rows),
            "classSetCount": len(captured_sets),
            "gapCount": len(gaps),
        },
    }
    writer.write_json("capture-manifest.json", manifest)
    return summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Capture official Blizzard current-season PVE source data into an "
            "isolated directory without database or pointer writes."
        )
    )
    parser.add_argument("--output", required=True)
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--region", default="us")
    parser.add_argument("--locale", default="en_US")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    parser.add_argument("--retries", type=int, default=3)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    summary = capture(args)
    print(
        json.dumps(
            bounded_capture_result(summary),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0 if summary["status"] == "captured" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except OfficialCaptureContractError as error:
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "reasonCode": "OFFICIAL_CAPTURE_CONTRACT_INVALID",
                    "error": str(error)[:500],
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        raise SystemExit(2)
