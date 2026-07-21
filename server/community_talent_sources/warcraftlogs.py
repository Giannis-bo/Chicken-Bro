import json
import hashlib
import os
import re

try:
    from ..simulator_payload import warcraftlogs_credentials_state, warcraftlogs_graphql
    from ..websim_payload import (
        SPEC_LABELS,
        WOW_CLASSES,
        expected_hero_tree_triplets,
        hero_tree_for,
        resolve_community_talent_structured_loadout,
        slugify,
    )
except ImportError:
    from simulator_payload import warcraftlogs_credentials_state, warcraftlogs_graphql
    from websim_payload import (
        SPEC_LABELS,
        WOW_CLASSES,
        expected_hero_tree_triplets,
        hero_tree_for,
        resolve_community_talent_structured_loadout,
        slugify,
    )


WCL_RANKINGS_QUERY = """
query WowMiniProgramWclRankings(
  $encounterId: Int!,
  $className: String!,
  $specName: String!,
  $metric: CharacterRankingMetricType!,
  $partition: Int,
  $page: Int!
) {
  worldData {
    encounter(id: $encounterId) {
      id
      name
      characterRankings(
        page: $page,
        partition: $partition,
        className: $className,
        specName: $specName,
        metric: $metric,
        includeCombatantInfo: true
      )
    }
  }
}
"""


WCL_ZONES_QUERY = """
query WowMiniProgramWclZones {
  worldData {
    zones {
      id
      name
      partitions { id }
      encounters { id name }
    }
  }
}
"""


def load_seed_templates():
    raw = os.environ.get("WOW_WARCRAFTLOGS_TEMPLATE_SEED_JSON", "").strip()
    if not raw:
        return []
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = parsed.get("templates") or []
    return parsed if isinstance(parsed, list) else []


def int_env(name, default):
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _positive_int(value, default=0):
    try:
        number = int(value or 0)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _float_value(value, default=0.0):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _parse_int_list(raw):
    values = []
    for part in re.split(r"[\s,;/]+", str(raw or "")):
        number = _positive_int(part)
        if number and number not in values:
            values.append(number)
    return values


def _normalize_slot(value):
    parts = [slugify(part, "") for part in str(value or "").split(":")]
    if len(parts) != 3 or not all(parts):
        return ""
    class_key, spec_key, hero_key = parts
    return f"{class_key}:{spec_key}:{hero_tree_for(class_key, spec_key, hero_key)}"


def target_slots_from_env():
    raw = os.environ.get("WOW_WARCRAFTLOGS_TEMPLATE_TARGET_SLOTS", "").strip()
    return [slot for slot in (_normalize_slot(item) for item in re.split(r"[\s,;]+", raw)) if slot]


def target_slots_from_store(store):
    if not store or not hasattr(store, "community_talent_template_coverage_rows"):
        return []
    try:
        rows = store.community_talent_template_coverage_rows()
    except Exception:
        return []
    verified_slots = {
        _normalize_slot(f"{row.get('classKey')}:{row.get('specKey')}:{row.get('heroKey')}")
        for row in rows or []
        if isinstance(row, dict) and row.get("status") == "verified"
    }
    return [
        slot
        for slot in expected_hero_tree_triplets()
        if slot and slot not in verified_slots
    ]


def target_slots_for_run(store=None):
    slots = target_slots_from_env() or target_slots_from_store(store)
    limit = int_env("WOW_WARCRAFTLOGS_TEMPLATE_TARGET_LIMIT", 12)
    if limit > 0:
        slots = slots[:limit]
    return slots


def class_name_for_wcl(class_key):
    label = next((item.get("label") for item in WOW_CLASSES if item.get("key") == class_key), class_key)
    if class_key in {"deathknight", "demonhunter"}:
        return str(label or class_key).replace(" ", "")
    return str(label or class_key)


def spec_name_for_wcl(spec_key):
    return SPEC_LABELS.get(spec_key, spec_key.replace("_", " ").title())


def metric_for_spec(spec_key):
    if spec_key in {"restoration", "preservation", "mistweaver", "holy", "discipline"}:
        return "hps"
    if spec_key in {"blood", "vengeance", "guardian", "brewmaster", "protection"}:
        return "tankhps"
    return "dps"


def discover_default_ranking_targets():
    configured = _parse_int_list(os.environ.get("WOW_WARCRAFTLOGS_RANKING_ENCOUNTERS", ""))
    partition = _positive_int(os.environ.get("WOW_WARCRAFTLOGS_RANKING_PARTITION", ""), 0)
    if configured:
        return configured, partition or None, []
    data = warcraftlogs_graphql(WCL_ZONES_QUERY)
    zones = ((data.get("worldData") or {}).get("zones") or [])
    selected_zone = {}
    for zone in zones:
        name = str((zone or {}).get("name") or "")
        encounters = (zone or {}).get("encounters") or []
        if encounters and ("/" in name or "Mythic+" in name):
            selected_zone = zone
            break
    if not selected_zone:
        selected_zone = next((zone for zone in zones if (zone or {}).get("encounters")), {})
    encounters = [
        _positive_int(item.get("id"))
        for item in (selected_zone.get("encounters") or [])
        if isinstance(item, dict)
    ]
    partitions = [
        _positive_int(item.get("id"))
        for item in (selected_zone.get("partitions") or [])
        if isinstance(item, dict)
    ]
    warnings = []
    if selected_zone:
        warnings.append(f"WCL rankings target zone: {selected_zone.get('name')} ({selected_zone.get('id')})")
    return [item for item in encounters if item], partition or (max(partitions) if partitions else None), warnings


def _source_url(report):
    report = report if isinstance(report, dict) else {}
    code = str(report.get("code") or "").strip()
    fight_id = str(report.get("fightID") or report.get("fightId") or "").strip()
    if not code:
        return "https://www.warcraftlogs.com/"
    suffix = f"#fight={fight_id}" if fight_id else ""
    return f"https://www.warcraftlogs.com/reports/{code}{suffix}"


def _loadout_signature(loadout):
    return json.dumps(
        [
            {
                "talentID": _positive_int(item.get("talentID") or item.get("talent_id") or item.get("id")),
                "points": _positive_int(item.get("points"), 1),
            }
            for item in loadout or []
            if isinstance(item, dict)
        ],
        ensure_ascii=False,
        sort_keys=True,
    )


def template_from_ranking(slot, encounter, ranking, metric):
    if not isinstance(ranking, dict):
        return None
    class_key, spec_key, hero_key = slot.split(":", 2)
    loadout = [item for item in (ranking.get("talents") or []) if isinstance(item, dict)]
    if not loadout:
        return None
    report = ranking.get("report") if isinstance(ranking.get("report"), dict) else {}
    server = ranking.get("server") if isinstance(ranking.get("server"), dict) else {}
    player_name = str(ranking.get("name") or "wcl-player").strip()
    source_url = _source_url(report)
    report_code = str(report.get("code") or "").strip()
    fight_id = report.get("fightID") or report.get("fightId") or ""
    encounter_id = _positive_int((encounter or {}).get("id"))
    encounter_name = str((encounter or {}).get("name") or "").strip()
    amount = _float_value(ranking.get("amount"), 0.0)
    signature = _loadout_signature(loadout)
    digest = hashlib.sha1(f"{slot}:{player_name}:{report_code}:{fight_id}:{signature}".encode("utf-8")).hexdigest()[:10]
    normalized_performance = {
        "metric": metric,
        "score": amount,
        "durationMs": _positive_int(ranking.get("duration")),
        "encounterId": encounter_id,
        "encounterName": encounter_name,
    }
    wcl_evidence = {
        "tier": "wcl_exact_template",
        "status": "verified",
        "sourceUrl": source_url,
        "reportCode": report_code,
        "fightId": fight_id,
        "templateSignature": signature,
        "normalizedPerformance": normalized_performance,
    }
    return {
        "id": f"wcl-{class_key}-{spec_key}-{hero_key}-{slugify(player_name, 'player')}-{digest}",
        "classKey": class_key,
        "specKey": spec_key,
        "heroKey": hero_key,
        "scenarioKey": "mythic_plus",
        "name": f"WCL {spec_name_for_wcl(spec_key)} {hero_key} {player_name}",
        "flowLabel": "WCL backed",
        "sourceKey": "warcraftlogs",
        "sourceName": "Warcraft Logs",
        "sourceUrl": source_url,
        "playerId": player_name,
        "sampleCount": 1,
        "maxKeyLevel": 0,
        "analysisWindow": f"WCL encounter {encounter_id} ranking page",
        "sourceStatus": "partial",
        "status": "verified",
        "payload": {
            "warcraftlogs": {
                "characterName": player_name,
                "className": ranking.get("class") or class_name_for_wcl(class_key),
                "specName": ranking.get("spec") or spec_name_for_wcl(spec_key),
                "serverName": server.get("name") or "",
                "serverRegion": server.get("region") or "",
                "reportCode": report_code,
                "fightId": fight_id,
                "encounterId": encounter_id,
                "encounterName": encounter_name,
                "metric": metric,
                "amount": amount,
                "loadout": loadout,
                "evidenceKind": "character_rankings_combatantinfo",
            },
            "wclEvidence": wcl_evidence,
            "evidenceTier": "wcl_exact_template",
            "qualityScore": amount,
            "normalizedPerformance": normalized_performance,
        },
    }


class CachedAuthorityStore:
    def __init__(self, store):
        self.store = store
        self.cache = {}

    def community_talent_authority_index(self, class_key, spec_key):
        key = (slugify(class_key, ""), slugify(spec_key, ""))
        if key not in self.cache:
            self.cache[key] = self.store.community_talent_authority_index(*key)
        return self.cache[key]


def ranking_template_target_filter(store, template):
    if not store or not hasattr(store, "community_talent_authority_index"):
        return True, {"reason": "authority_unavailable"}
    class_key = slugify(template.get("classKey"), "")
    spec_key = slugify(template.get("specKey"), "")
    target_hero = hero_tree_for(class_key, spec_key, slugify(template.get("heroKey"), ""))
    parsed = resolve_community_talent_structured_loadout(store, template)
    errors = parsed.get("errors") if isinstance(parsed.get("errors"), list) else []
    parsed_hero = hero_tree_for(class_key, spec_key, slugify(parsed.get("heroKey"), ""))
    if errors:
        return False, {
            "reason": "authority_parse",
            "heroKey": parsed_hero,
            "errors": errors,
        }
    if parsed_hero != target_hero:
        return False, {
            "reason": "hero_mismatch",
            "heroKey": parsed_hero,
            "targetHeroKey": target_hero,
        }
    return True, {
        "reason": "target_hero_matched",
        "heroKey": parsed_hero,
        "nodeCount": len(parsed.get("selectedNodes") or []),
    }


def load_ranking_templates(store=None):
    slots = target_slots_for_run(store)
    if not slots:
        return [], ["Warcraft Logs ranking extraction skipped: no target slots for this sync run."], []
    encounters, partition, warnings = discover_default_ranking_targets()
    if not encounters:
        return [], warnings, ["Warcraft Logs ranking extraction has no encounter targets for this sync run."]
    start_page = max(1, int_env("WOW_WARCRAFTLOGS_RANKING_START_PAGE", 1))
    end_page = max(
        start_page,
        int_env("WOW_WARCRAFTLOGS_RANKING_END_PAGE", int_env("WOW_WARCRAFTLOGS_RANKING_PAGES", 1)),
    )
    per_slot_limit = max(1, int_env("WOW_WARCRAFTLOGS_RANKING_TEMPLATE_LIMIT_PER_SLOT", 4))
    templates = []
    errors = []
    skip_counts = {}
    seen = set()
    authority_store = CachedAuthorityStore(store) if store and hasattr(store, "community_talent_authority_index") else store
    for slot in slots:
        class_key, spec_key, _hero_key = slot.split(":", 2)
        metric = metric_for_spec(spec_key)
        slot_count = 0
        for encounter_id in encounters:
            if slot_count >= per_slot_limit:
                break
            for page in range(start_page, end_page + 1):
                if slot_count >= per_slot_limit:
                    break
                variables = {
                    "encounterId": encounter_id,
                    "className": class_name_for_wcl(class_key),
                    "specName": spec_name_for_wcl(spec_key),
                    "metric": metric,
                    "partition": partition,
                    "page": page,
                }
                try:
                    data = warcraftlogs_graphql(WCL_RANKINGS_QUERY, variables)
                except Exception as error:
                    errors.append(f"{slot}/encounter-{encounter_id}/page-{page}: {error}")
                    continue
                encounter = ((data.get("worldData") or {}).get("encounter") or {})
                rankings = ((encounter.get("characterRankings") or {}).get("rankings") or [])
                for ranking in rankings:
                    template = template_from_ranking(slot, encounter, ranking, metric)
                    if not template:
                        continue
                    accepted, filter_detail = ranking_template_target_filter(authority_store, template)
                    if not accepted:
                        reason = filter_detail.get("reason") or "skipped"
                        skip_counts[reason] = skip_counts.get(reason, 0) + 1
                        continue
                    key = template["payload"]["wclEvidence"]["templateSignature"]
                    dedupe_key = f"{slot}:{key}"
                    if dedupe_key in seen:
                        continue
                    seen.add(dedupe_key)
                    templates.append(template)
                    slot_count += 1
                    if slot_count >= per_slot_limit:
                        break
    if skip_counts:
        warnings.append(
            "WCL ranking candidates skipped before promotion: "
            + ", ".join(f"{key}={value}" for key, value in sorted(skip_counts.items()))
        )
    return templates, warnings, errors


def _quality_score(payload):
    performance = payload.get("normalizedPerformance") if isinstance(payload.get("normalizedPerformance"), dict) else {}
    try:
        return float(performance.get("score") or 0)
    except (TypeError, ValueError):
        return 0


def _wcl_evidence_for_seed(payload, source_url):
    warcraftlogs = payload.get("warcraftlogs") if isinstance(payload.get("warcraftlogs"), dict) else {}
    conflict_reason = str(warcraftlogs.get("conflictReason") or payload.get("conflictReason") or "").strip()
    report_code = str(warcraftlogs.get("reportCode") or payload.get("reportCode") or "").strip()
    combatant_info = warcraftlogs.get("combatantInfo") or payload.get("combatantInfo")
    template_signature = str(warcraftlogs.get("templateSignature") or payload.get("templateSignature") or "").strip()
    character_matched = bool(warcraftlogs.get("characterMatched") or payload.get("characterMatched"))
    if conflict_reason:
        tier = "wcl_conflict"
        status = "blocked"
    elif combatant_info and template_signature:
        tier = "wcl_exact_template"
        status = "verified"
    elif report_code or character_matched:
        tier = "wcl_character_supported"
        status = "verified"
    else:
        tier = "wcl_missing"
        status = "missing"
    return {
        "tier": tier,
        "status": status,
        "sourceUrl": source_url,
        "reportCode": report_code,
        "templateSignature": template_signature,
        "conflictReason": conflict_reason,
        "normalizedPerformance": payload.get("normalizedPerformance") if isinstance(payload.get("normalizedPerformance"), dict) else {},
    }


def normalize_wcl_seed_template(template):
    if not isinstance(template, dict):
        return None
    payload = template.get("payload") if isinstance(template.get("payload"), dict) else {}
    source_url = str(template.get("sourceUrl") or payload.get("sourceUrl") or "").strip()
    wcl_evidence = _wcl_evidence_for_seed(payload, source_url)
    quality_score = _quality_score(payload)
    normalized = {
        **template,
        "sourceName": "Warcraft Logs",
        "sourceUrl": source_url,
        "sourceStatus": template.get("sourceStatus") or "partial",
        "status": template.get("status") or "blocked",
        "payload": {
            **payload,
            "warcraftlogs": {
                **(payload.get("warcraftlogs") if isinstance(payload.get("warcraftlogs"), dict) else {}),
                "sourceUrl": source_url,
                "evidenceKind": payload.get("evidenceKind") or "combatantinfo_seed",
            },
            "wclEvidence": wcl_evidence,
            "evidenceTier": wcl_evidence["tier"],
            "qualityScore": quality_score,
        },
    }
    blocked_by_evidence = wcl_evidence["tier"] in {"wcl_conflict", "wcl_blocked"}
    if blocked_by_evidence:
        normalized["status"] = "blocked"
    if normalized.get("talentState") or normalized.get("loadout") or normalized.get("rawImportCode"):
        normalized["status"] = "blocked" if blocked_by_evidence else template.get("status") or "verified"
    return normalized


def load_templates(conn=None):
    credentials = warcraftlogs_credentials_state()
    if not credentials["configured"]:
        return {
            "status": "missing_credentials",
            "sourceName": "Warcraft Logs",
            "templates": [],
            "errors": [
                "WOW_WARCRAFTLOGS_CLIENT_ID/WOW_WARCRAFTLOGS_CLIENT_SECRET or WOW_WARCRAFTLOGS_API_KEY are not configured"
            ],
        }
    if credentials.get("api") != "warcraftlogs-v2-graphql":
        return {
            "status": "blocked",
            "sourceName": "Warcraft Logs",
            "credentialMode": credentials["mode"],
            "api": credentials["api"],
            "templates": [],
            "errors": ["Warcraft Logs v1 is deprecated; community template extraction requires v2 OAuth/GraphQL."],
        }
    try:
        seed_templates = [
            item
            for item in (normalize_wcl_seed_template(raw) for raw in load_seed_templates())
            if item
        ]
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        return {
            "status": "blocked",
            "sourceName": "Warcraft Logs",
            "credentialMode": credentials["mode"],
            "api": credentials["api"],
            "templates": [],
            "errors": [f"Warcraft Logs template seed could not be parsed: {error}"],
        }
    ranking_templates = []
    warnings = []
    ranking_errors = []
    if os.environ.get("WOW_WARCRAFTLOGS_RANKINGS_DISABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        try:
            ranking_templates, warnings, ranking_errors = load_ranking_templates(conn)
        except Exception as error:
            ranking_errors = [f"Warcraft Logs ranking extraction failed: {error}"]
    templates = [*seed_templates, *ranking_templates]
    if templates:
        return {
            "status": "partial",
            "sourceName": "Warcraft Logs",
            "credentialMode": credentials["mode"],
            "api": credentials["api"],
            "templates": templates,
            "warnings": warnings,
            "errors": ranking_errors,
        }
    if not ranking_errors and any("no target slots" in str(warning).lower() for warning in warnings):
        return {
            "status": "synced",
            "sourceName": "Warcraft Logs",
            "credentialMode": credentials["mode"],
            "api": credentials["api"],
            "templates": [],
            "warnings": warnings,
            "errors": [],
        }
    errors = ranking_errors or ["Warcraft Logs v2 credentials are configured, but no combatantinfo template seed/report extraction is available for this sync run."]
    return {
        "status": "partial",
        "sourceName": "Warcraft Logs",
        "credentialMode": credentials["mode"],
        "api": credentials["api"],
        "templates": [],
        "warnings": warnings,
        "errors": errors,
    }
