"""Current-client Journal item/difficulty relation authority."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


SCHEMA_REVISION = "season-pve-current-client-journal-membership-v1"
SOURCE_GROUP_DEFAULT_DIFFICULTIES = {
    "midnight_dungeon": ("heroic", "mythic"),
    "mythic_plus": ("mythic_plus",),
    "midnight_raid": ("lfr", "normal", "heroic", "mythic"),
    "midnight_world_boss": ("world_boss",),
    "timewalking": ("timewalking",),
}
SOURCE_GROUP_DIFFICULTY_IDS = {
    "midnight_dungeon": {
        "2": "heroic",
        "23": "mythic",
        "8": "mythic",
    },
    "midnight_raid": {
        "17": "lfr",
        "14": "normal",
        "15": "heroic",
        "16": "mythic",
    },
}
DIFFICULTY_ORDER = {
    "lfr": 10,
    "normal": 20,
    "heroic": 30,
    "mythic": 40,
    "mythic_plus": 50,
    "world_boss": 60,
    "timewalking": 70,
}


class ClientJournalRelationError(ValueError):
    """Raised when official relations cannot join to the current client."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _source_key(source_group: str, instance_name: str) -> str:
    if source_group == "midnight_dungeon":
        return "dungeon:midnight-season-1-heroic-mythic0"
    if source_group == "mythic_plus":
        return "mythic_plus:midnight-season-1"
    if source_group == "midnight_raid":
        if instance_name.strip().lower() == "sporefall":
            return "raid:sporefall"
        return "raid:midnight-season-1-core"
    if source_group == "midnight_world_boss":
        return "world_boss:midnight-season-1-core"
    if source_group == "timewalking":
        return "timewalking_event:turbulent-timeways-revelations"
    raise ClientJournalRelationError(
        f"unsupported Journal source group {source_group or 'missing'}"
    )


def _relation_sort_key(row: dict[str, Any]):
    return (
        row["sourceKey"],
        int(row["instanceId"]),
        int(row["encounterId"]),
        int(row["itemId"]),
    )


def build_current_client_journal_membership(
    journal_capture: Any,
    encounter_items: Any,
    item_difficulties: Any,
    difficulties: Any,
    *,
    client_build: str,
) -> dict[str, Any]:
    """Join Game Data Journal contexts to current-client DB2 relations."""

    if not isinstance(journal_capture, dict) or not isinstance(
        journal_capture.get("itemContexts"),
        dict,
    ):
        raise ClientJournalRelationError(
            "journal capture requires itemContexts"
        )
    difficulty_names = {
        _text(row.get("id")): _text(row.get("name"))
        for row in (difficulties or [])
        if isinstance(row, dict) and _text(row.get("id"))
    }
    current_by_item_encounter: dict[
        tuple[str, str], list[dict[str, Any]]
    ] = defaultdict(list)
    current_by_id = {}
    for raw_row in encounter_items or []:
        row = raw_row if isinstance(raw_row, dict) else {}
        relation_id = _text(row.get("id"))
        encounter_id = _text(row.get("id_encounter"))
        item_id = _text(row.get("id_item"))
        if not relation_id or not encounter_id or not item_id:
            continue
        current_by_item_encounter[(item_id, encounter_id)].append(row)
        current_by_id[relation_id] = row
    difficulty_ids_by_relation: dict[str, set[str]] = defaultdict(set)
    for raw_row in item_difficulties or []:
        row = raw_row if isinstance(raw_row, dict) else {}
        relation_id = _text(row.get("id_parent"))
        difficulty_id = _text(row.get("id_difficulty"))
        if relation_id and difficulty_id:
            difficulty_ids_by_relation[relation_id].add(difficulty_id)
    projected = {}
    for raw_item_id, raw_contexts in journal_capture[
        "itemContexts"
    ].items():
        item_id = _text(raw_item_id)
        if not isinstance(raw_contexts, list):
            raise ClientJournalRelationError(
                f"journal item {item_id} contexts must be an array"
            )
        for raw_context in raw_contexts:
            context = (
                raw_context if isinstance(raw_context, dict) else {}
            )
            encounter_id = _text(context.get("encounterId"))
            instance_id = _text(context.get("instanceId"))
            source_group = _text(context.get("sourceGroup"))
            instance_name = _text(context.get("instanceName"))
            if not item_id or not encounter_id or not instance_id:
                raise ClientJournalRelationError(
                    "Journal context is missing item/encounter/instance identity"
                )
            current_rows = current_by_item_encounter.get(
                (item_id, encounter_id),
                [],
            )
            if not current_rows:
                raise ClientJournalRelationError(
                    "missing current client JournalEncounterItem relation "
                    f"for item {item_id}, encounter {encounter_id}"
                )
            source_key = _source_key(source_group, instance_name)
            identity = (
                source_key,
                instance_id,
                encounter_id,
                item_id,
            )
            row = projected.setdefault(
                identity,
                {
                    "sourceKey": source_key,
                    "sourceGroup": source_group,
                    "instanceId": instance_id,
                    "instanceName": instance_name,
                    "encounterId": encounter_id,
                    "encounterName": _text(
                        context.get("encounterName")
                    ),
                    "itemId": item_id,
                    "officialLootRelationIds": set(),
                    "currentClientRelationIds": {
                        _text(current.get("id"))
                        for current in current_rows
                    },
                },
            )
            official_relation_id = _text(
                context.get("lootRelationId")
            )
            if official_relation_id:
                row["officialLootRelationIds"].add(
                    official_relation_id
                )
    relations = []
    source_counts = Counter()
    difficulty_counts = Counter()
    for row in projected.values():
        source_group = row["sourceGroup"]
        defaults = SOURCE_GROUP_DEFAULT_DIFFICULTIES.get(source_group)
        if not defaults:
            raise ClientJournalRelationError(
                f"missing difficulty policy for source group {source_group}"
            )
        explicit_ids = {
            difficulty_id
            for relation_id in row["currentClientRelationIds"]
            for difficulty_id in difficulty_ids_by_relation.get(
                relation_id,
                set(),
            )
        }
        allowed_explicit = SOURCE_GROUP_DIFFICULTY_IDS.get(
            source_group,
            {},
        )
        explicit_keys = {
            allowed_explicit[difficulty_id]
            for difficulty_id in explicit_ids
            if difficulty_id in allowed_explicit
        }
        difficulty_keys = (
            sorted(
                explicit_keys,
                key=lambda key: DIFFICULTY_ORDER[key],
            )
            if explicit_keys
            else list(defaults)
        )
        public_row = {
            **row,
            "officialLootRelationIds": sorted(
                row["officialLootRelationIds"],
                key=int,
            ),
            "currentClientRelationIds": sorted(
                row["currentClientRelationIds"],
                key=int,
            ),
            "explicitClientDifficultyIds": sorted(
                explicit_ids,
                key=int,
            ),
            "explicitClientDifficultyNames": [
                difficulty_names.get(difficulty_id, "")
                for difficulty_id in sorted(explicit_ids, key=int)
            ],
            "difficultyKeys": difficulty_keys,
            "clientBuild": _text(client_build),
            "membershipStatus": "verified_current_client_relation",
        }
        relations.append(public_row)
        source_counts[public_row["sourceKey"]] += 1
        for difficulty_key in difficulty_keys:
            difficulty_counts[difficulty_key] += 1
    relations.sort(key=_relation_sort_key)
    return {
        "schemaVersion": 1,
        "schemaRevision": SCHEMA_REVISION,
        "scope": "current_client_journal_item_difficulty_relations",
        "status": "complete",
        "clientBuild": _text(client_build),
        "summary": {
            "relationCount": len(relations),
            "sourceCount": len(source_counts),
            "bySource": dict(sorted(source_counts.items())),
            "byDifficulty": dict(sorted(difficulty_counts.items())),
        },
        "relations": relations,
    }
