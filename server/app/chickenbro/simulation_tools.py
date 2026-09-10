"""Run-scoped, trusted bridge to the shared Simulation application.

Capabilities are issued only by the Chat host. Model arguments never select an
owner, conversation, run, transport, executable, or idempotency key.
"""

import hashlib
import math
import re
import secrets
import threading
import time
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from uuid import UUID

from server.app.identity.domain import Principal
from server.app.simulation.application import (
    SimulationApplication,
    SimulationApplicationError,
    SimulationJobView,
    validated_simulation_result_provenance,
)
from server.app.simulation.compiler import SimcCompileError, normalize_scenario, scenario_hash
from server.app.simulation.domain import SimulationJob, SourceReadiness, SourceSnapshot
from server.app.simulation.snapshots import REQUIRED_GEAR_SLOTS
from server.app.simulation.experiments import merge_scenario, compare_jobs
from server.app.simulation.talent_editor import TalentEditError, edit_talents, talent_options, talent_difference
from server.app.simulation.localization import catalog_for_build
from server.app.simulation.item_variants import same_upgrade_variants, variant_item_names


_SAFE_CODE = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")
_TERMINAL = {"succeeded", "failed", "cancelled"}
_TTL_SECONDS = 600


class SimulationToolUnauthorized(ValueError):
    """The supplied run capability is unknown, expired, or revoked."""


@dataclass(frozen=True)
class SimulationToolContext:
    principal: Principal
    conversation_id: UUID
    run_id: UUID


@dataclass
class _Run:
    context: SimulationToolContext
    expires_at: float
    lock: object = field(default_factory=threading.RLock)
    preparations: dict[str, dict] = field(default_factory=dict)
    submissions: dict[str, UUID | None] = field(default_factory=dict)


def _code(value: object, fallback: str = "SIMC_UNAVAILABLE") -> str:
    return value if isinstance(value, str) and _SAFE_CODE.fullmatch(value) else fallback


def _codes(value: object) -> list[str]:
    return [item for item in value[:64] if isinstance(item, str) and _SAFE_CODE.fullmatch(item)] if isinstance(value, (list, tuple)) else []


def _packet(status: str, **fields: object) -> dict:
    return {"sourceKey": "simc", "status": status, "facts": [], "evidenceRefs": [],
            "limitations": [], "nextActions": [], **fields}


def _blocked(code: str, blockers: object = ()) -> dict:
    safe_code = _code(code)
    return _packet("blocked", errorCode=safe_code, blockers=_codes(blockers) or [safe_code],
                   limitations=["No new verified simulation result is available from this operation."],
                   nextActions=["Resolve the reported blocker before retrying."])


def _uuid(value: object) -> UUID:
    if not isinstance(value, str):
        raise ValueError("UUID string required")
    parsed = UUID(value)
    if str(parsed) != value.lower():
        raise ValueError("canonical UUID required")
    return parsed


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise ValueError("integer outside operation bounds")
    return value


def _project(raw: object, keys: tuple[str, ...], *, maximum: int = 160) -> dict:
    if not isinstance(raw, Mapping):
        return {}
    output = {}
    for key in keys:
        value = raw.get(key)
        if isinstance(value, str) and len(value) <= maximum:
            output[key] = value
        elif isinstance(value, int) and not isinstance(value, bool):
            output[key] = value
    return output


def _snapshot_packet(snapshot: SourceSnapshot) -> dict:
    raw = snapshot.snapshot if isinstance(snapshot.snapshot, Mapping) else {}
    ready = snapshot.readiness is SourceReadiness.READY_FOR_SIMC
    gear = {}
    raw_gear = raw.get("gear")
    if isinstance(raw_gear, Mapping):
        for slot in REQUIRED_GEAR_SLOTS:
            item = raw_gear.get(slot)
            if not isinstance(item, Mapping):
                continue
            projected = _project(item, ("itemId", "itemLevel", "name", "enchant"))
            # Preserve explicit absence; an omitted key still means unknown.
            if "enchant" in item and item["enchant"] in (None, ""):
                projected["enchant"] = None
            elif isinstance(item.get("enchant"), str) and item["enchant"].isdigit():
                projected["enchant"] = int(item["enchant"])
            for key in ("bonusIds", "gems"):
                values = item.get(key)
                if isinstance(values, (list, tuple)):
                    projected[key] = [value for value in values[:32] if isinstance(value, int) and not isinstance(value, bool) and value > 0]
            gear[slot] = projected
    raw_talents = raw.get("talents")
    talents = _project(raw_talents, ("string",), maximum=512)
    if isinstance(raw_talents, Mapping) and isinstance(raw_talents.get("loadout"), list):
        talents["loadout"] = [_project(entry, ("id", "talentId", "rank", "points")) for entry in raw_talents["loadout"][:128]]
    return _packet(
        "ready" if ready else "blocked", snapshotId=str(snapshot.id), readiness=snapshot.readiness.value,
        blockers=_codes(raw.get("readinessBlockers")), missingFields=_codes(raw.get("missingFields")),
        source={"provider": snapshot.provider.value, "url": snapshot.source_url[:2048],
                "key": snapshot.source_key[:256], "revision": snapshot.revision,
                "fetchedAt": snapshot.fetched_at.isoformat()},
        provenance={**_project(snapshot.provenance, ("sourceRevision",)), "sourceRawSha256": snapshot.raw_sha256},
        character=_project(raw.get("character"), ("name", "level", "classKey", "specKey", "raceKey", "region", "realm")),
        gear=gear, talents=talents,
        facts=["Source snapshot prepared; no simulation was submitted."],
        evidenceRefs=[{"snapshotId": str(snapshot.id)}],
        limitations=[] if ready else ["The source snapshot is not executable with the current runtime."],
        nextActions=["Submit this snapshot with the requested scenario."] if ready else ["Resolve the snapshot readiness blockers."],
    )


def _job_packet(view: SimulationJobView) -> dict:
    provenance = validated_simulation_result_provenance(view)
    job = view.job
    result = None
    limitations = []
    if view.result is not None:
        result = {"metricName": view.result.primary_metric_name,
                  "metricValue": view.result.primary_metric_value, "provenance": provenance}
        proof = view.result.result.get("effectiveConfig", {})
        if isinstance(proof,dict) and proof.get("status") == "verified" and proof.get("profileSha256") == view.result.profile_sha256:
            result["effectiveConfig"] = {"status":"verified", "profileSha256":view.result.profile_sha256,
                                         "checked":["talents","equipmentItemIds","overriddenItemLevels"]}
            if 'overriddenEnchantIds' in proof.get('checked', []) and isinstance(proof.get('overriddenEnchants'), dict):
                result['effectiveConfig'].update(
                    checked=["talents", "equipmentItemIds", "overriddenItemLevels", "overriddenEnchantIds"],
                    overriddenEnchants=deepcopy(proof['overriddenEnchants']),
                    enchantEvidenceScope='engine_reported_input_identity')
        evidence = view.result.result.get("actionEvidence")
        if isinstance(evidence, dict) and evidence.get("profileSha256") == view.result.profile_sha256:
            result["actionEvidence"] = deepcopy(evidence)
        for key in ("metricError", "metricErrorPct"):
            value = view.result.result.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
                result[key] = value
        if "metricError" not in result:
            limitations.append("This result has no reported simulation error; small differences are not conclusive.")
    elif job.status.value not in _TERMINAL:
        limitations.append("The simulation is pending; no performance result is available yet.")
    if view.scenario is None:
        limitations.append("The original scenario is unavailable; do not infer targets, duration or gem replacements from this job.")
    source_packet = _snapshot_packet(view.snapshot) if view.snapshot else {}
    gear = source_packet.get("gear", {})
    talents = source_packet.get("talents", {})
    if view.scenario and "talentOverrides" in view.scenario and view.snapshot:
        try:
            edited = edit_talents(talents, source_packet["character"], job.runtime_revision, view.scenario["talentOverrides"])
            talents = {"string": edited["string"], "loadout": edited["loadout"]}
        except TalentEditError:
            talents = {}
            limitations.append("Effective talents cannot be reconstructed with the available versioned catalog.")
    if view.scenario:
        gear.update(deepcopy(view.scenario.get("equipmentOverrides", {})))
        for slot, gems in view.scenario.get("gemOverrides", {}).items():
            if slot in gear:
                gear[slot]["gems"] = list(gems)
    return _packet(
        job.status.value, jobId=str(job.id), snapshotId=str(job.snapshot_id),
        scenario=deepcopy(view.scenario),
        gear=gear, talents=talents, character=source_packet.get("character", {}), source=source_packet.get("source", {}),
        scenarioHash=job.scenario_hash, compilerRevision=job.compiler_revision,
        runtimeRevision=job.runtime_revision, errorCode=_code(job.public_error_code, "SIMC_FAILED") if job.public_error_code else None,
        createdAt=job.created_at.isoformat(), updatedAt=job.updated_at.isoformat(), result=result,
        facts=[f"Simulation job status: {job.status.value}."],
        evidenceRefs=[{"jobId": str(job.id), "snapshotId": str(job.snapshot_id)}],
        limitations=limitations,
        nextActions=["Read this job again to check progress."] if job.status.value not in _TERMINAL else [],
    )


class SimulationToolGateway:
    def __init__(self, application: SimulationApplication, *, clock: Callable[[], float] | None = None,
                 sleep: Callable[[float], None] | None = None):
        self._application = application
        self._clock = clock or time.monotonic
        self._sleep = sleep or time.sleep
        self._lock = threading.RLock()
        self._capabilities: dict[str, _Run] = {}
        self._runs: dict[tuple[UUID, UUID, UUID], _Run] = {}

    def issue_capability(self, context: SimulationToolContext) -> str:
        if (not isinstance(context, SimulationToolContext) or not isinstance(context.principal, Principal)
                or not all(isinstance(value, UUID) for value in (context.principal.user_id, context.conversation_id, context.run_id))):
            raise ValueError("trusted simulation context required")
        with self._lock:
            now = self._clock()
            self._capabilities = {key: run for key, run in self._capabilities.items() if now < run.expires_at}
            self._runs = {key: run for key, run in self._runs.items() if now < run.expires_at}
            key = (context.principal.user_id, context.conversation_id, context.run_id)
            run = self._runs.setdefault(key, _Run(context, now + _TTL_SECONDS))
            token = secrets.token_urlsafe(32)
            self._capabilities[hashlib.sha256(token.encode()).hexdigest()] = run
            return token

    def revoke(self, token: str) -> None:
        if isinstance(token, str):
            with self._lock:
                self._capabilities.pop(hashlib.sha256(token.encode()).hexdigest(), None)

    def _authorized(self, token: str) -> _Run:
        with self._lock:
            run = self._capabilities.get(hashlib.sha256(token.encode()).hexdigest()) if isinstance(token, str) and len(token) <= 256 else None
            if run is None or self._clock() >= run.expires_at:
                raise SimulationToolUnauthorized("Simulation capability is invalid or expired")
            return run

    def _options(self, run, arguments):
        principal = run.context.principal
        if ("snapshotId" in arguments) == ("baseJobId" in arguments):
            raise ValueError("exactly one source required")
        if "baseJobId" in arguments:
            source = _job_packet(self._application.read_job(principal, _uuid(arguments["baseJobId"])))
        else:
            source = _snapshot_packet(self._application.read_snapshot(principal, _uuid(arguments["snapshotId"])))
        query = arguments.get("query", "")
        if not isinstance(query,str) or len(query)>120: raise ValueError("bounded query required")
        caps = self._application.capabilities()
        if arguments.get("kind") == "talents":
            options = talent_options(source["character"], source["talents"], caps.runtime_revision, query)
        elif arguments.get("kind") == "items":
            from server.app.simulation.wcl_talents import _catalog
            catalog = _catalog()[0]
            if not caps.runtime_revision.startswith("simc:managed:"+catalog["revision"]+":"):
                return _blocked("TALENT_CATALOG_RUNTIME_MISMATCH")
            names = catalog_for_build(catalog["build"])
            engine_names = variant_item_names(caps.runtime_revision)
            localized = names.data['items'] if names else {}
            if not localized and not engine_names: return _blocked("SIMC_CATALOG_UNAVAILABLE")
            if not query: raise ValueError("item name or ID required")
            all_names = {**engine_names, **localized}
            rows = [{"itemId":int(k),"name":v,"nameEn":engine_names.get(k)} for k,v in all_names.items()
                    if k.isdigit() and v and (query.casefold() in v.casefold() or query==k
                        or query.casefold() in engine_names.get(k,'').casefold())]
            for row in rows[:30]:
                row["sameUpgradeVariants"] = same_upgrade_variants(row["itemId"], source.get("gear", {}), caps.runtime_revision)
            options = {"items":rows[:30],"hasMore":len(rows)>30,"gameBuild":catalog['build'],
                       "catalogRevision":catalog["revision"],
                       "supportedVariantItems":([{ "itemId":int(k), "nameEn":v} for k,v in engine_names.items()] if not rows else []),
                       "limitations":["If a localized name has no match, inspect supportedVariantItems and retry its exact English name or ID. Use sameUpgradeVariants only when the user intends the same upgrade progress; disclose its assumption. Otherwise research an exact item variant. Name matches alone do not establish track, rank or availability."]}
        else: raise ValueError("unknown option kind")
        return _packet("ready", options=options, runtimeRevision=caps.runtime_revision,
                       compilerRevision=caps.compiler_revision)

    def execute(self, token: str, operation: str, arguments: dict) -> dict:
        run = self._authorized(token)
        try:
            if not isinstance(arguments, dict) or not isinstance(operation, str):
                raise ValueError("invalid operation arguments")
            allowed = {"prepare": {"sourceUrl"}, "submit": {"snapshotId", "baseJobId", "scenario"},
                       "get": {"jobId", "waitSeconds"}, "list": {"limit", "cursor"},
                       "preview": {"snapshotId", "baseJobId", "scenario"},
                       "options": {"snapshotId", "baseJobId", "kind", "query"},
                       "compare": {"baselineJobId", "variantJobId"}}
            if operation not in allowed or set(arguments) - allowed[operation]:
                raise ValueError("unknown operation or extra arguments")
            if operation == "compare":
                principal = run.context.principal
                comparison = compare_jobs(
                    self._application.read_job(principal, _uuid(arguments.get("baselineJobId"))),
                    self._application.read_job(principal, _uuid(arguments.get("variantJobId"))))
                return _packet("ready", comparison=comparison, evidenceRefs=[
                    {"jobId":comparison["baselineJobId"]}, {"jobId":comparison["variantJobId"]}])
            if operation == "options":
                return self._options(run, arguments)
            if operation == "get":
                job_id = _uuid(arguments.get("jobId"))
                wait = _bounded_int(arguments.get("waitSeconds", 0), 0, 20)
                for attempt in range(wait + 1):
                    self._authorized(token)
                    packet = _job_packet(self._application.read_job(run.context.principal, job_id))
                    if packet["status"] in _TERMINAL or attempt == wait:
                        return packet
                    self._sleep(1)
            with run.lock:
                self._authorized(token)
                principal = run.context.principal
                if operation == "prepare":
                    url = arguments.get("sourceUrl")
                    if not isinstance(url, str) or not 1 <= len(url) <= 2048:
                        raise ValueError("bounded source URL required")
                    url = url.strip()
                    if url in run.preparations:
                        return deepcopy(run.preparations[url])
                    if len(run.preparations) >= 3:
                        return _blocked("SIMC_PREPARE_BUDGET_EXCEEDED")
                    # Reserve before network/DB work so failures cannot bypass the budget.
                    run.preparations[url] = _blocked("SIMC_UNAVAILABLE")
                    try:
                        packet = _snapshot_packet(self._application.resolve_source(principal, url))
                    except SimulationApplicationError as error:
                        run.preparations[url] = _blocked(error.code, error.blockers)
                        raise
                    run.preparations[url] = packet
                    return deepcopy(packet)
                if operation in {"submit", "preview"}:
                    if ("snapshotId" in arguments) == ("baseJobId" in arguments):
                        raise ValueError("exactly one simulation source required")
                    if "baseJobId" in arguments:
                        base = self._application.read_job(principal, _uuid(arguments["baseJobId"]))
                        if base.scenario is None:
                            return _blocked("SIMC_BASE_SCENARIO_UNAVAILABLE")
                        snapshot_id = base.job.snapshot_id
                        patch = arguments.get("scenario", {})
                        if not isinstance(patch, dict):
                            raise ValueError("scenario patch required")
                        if "string" in base.scenario.get("talentOverrides", {}) and "nodes" in patch.get("talentOverrides", {}):
                            packet = _job_packet(base)
                            edited = edit_talents(packet["talents"], packet["character"],
                                                  self._application.capabilities().runtime_revision, patch["talentOverrides"])
                            patch = {**patch, "talentOverrides": {"string":edited["string"]}}
                        scenario = merge_scenario(base.scenario, patch)
                    else:
                        snapshot_id = _uuid(arguments["snapshotId"])
                        scenario = normalize_scenario(arguments.get("scenario"))
                    if operation == "preview":
                        compiled = self._application.preview(principal, snapshot_id, scenario)
                        source = _snapshot_packet(self._application.read_snapshot(principal, snapshot_id))
                        prior = _job_packet(base) if "baseJobId" in arguments else source
                        gear = deepcopy(source["gear"])
                        gear.update(deepcopy(scenario.get("equipmentOverrides", {})))
                        for slot,gems in scenario.get("gemOverrides", {}).items():
                            gear[slot]["gems"] = list(gems)
                        talents = compiled.provenance.get("talentOverrides", source["talents"])
                        changes = {"equipment":{slot:{"before":prior["gear"].get(slot), "after":item}
                                   for slot,item in gear.items() if item!=prior["gear"].get(slot)},
                                   "talents":(talent_difference(prior["talents"], talents, source["character"], compiled.runtime_revision)
                                              if "talentOverrides" in scenario else []),
                                   "parameters":{key:{"before":prior.get("scenario", {}).get(key),"after":value}
                                                 for key,value in scenario.items() if key not in {"equipmentOverrides","gemOverrides","talentOverrides"}
                                                 and value!=prior.get("scenario", {}).get(key)}}
                        return _packet("ready", snapshotId=str(snapshot_id), scenario=dict(compiled.scenario),
                                       source=source["source"], character=source["character"], gear=gear, talents=talents,
                                       changes=changes, profileSha256=compiled.profile_sha256, scenarioHash=compiled.scenario_hash,
                                       compilerRevision=compiled.compiler_revision, runtimeRevision=compiled.runtime_revision,
                                       facts=["Configuration compiled without enqueueing a simulation."],
                                       limitations=["Custom APL syntax checks are not engine execution or proof of the intended order. Inspect result actionEvidence.sample after running.", "Equipment identifiers and syntax are checked; verify game slot, upgrade track and unique-equipped rules from item sources before submission."])
                    digest = scenario_hash(scenario)
                    key = hashlib.sha256(f"{run.context.run_id}:{snapshot_id}:{digest}".encode()).hexdigest()
                    if run.submissions.get(key) is not None:
                        return _job_packet(self._application.read_job(principal, run.submissions[key]))
                    if key not in run.submissions and len(run.submissions) >= 4:
                        return _blocked("SIMC_JOB_BUDGET_EXCEEDED")
                    # A lost response may already have committed and enqueued the job.
                    # Retain its slot and retry with the same application idempotency key.
                    run.submissions[key] = None
                    job: SimulationJob = self._application.submit(principal, snapshot_id, scenario, key)
                    run.submissions[key] = job.id
                    return _job_packet(self._application.read_job(principal, job.id))
                limit = _bounded_int(arguments.get("limit", 5), 1, 10)
                cursor = arguments.get("cursor")
                if cursor is not None and (not isinstance(cursor, str) or not 1 <= len(cursor) <= 1024):
                    raise ValueError("invalid cursor")
                page = self._application.list_jobs(principal, cursor=cursor, limit=limit)
                jobs = [_job_packet(view) for view in page.items]
                return _packet("ready", jobs=jobs, nextCursor=page.next_cursor,
                               facts=[f"Returned {len(jobs)} owner-scoped simulation jobs."],
                               evidenceRefs=[{"jobId": job["jobId"]} for job in jobs])
        except SimulationToolUnauthorized:
            raise
        except SimulationApplicationError as error:
            return _blocked(error.code, error.blockers)
        except (SimcCompileError, TalentEditError) as error:
            return _blocked(error.code)
        except (ValueError, TypeError, KeyError):
            return _blocked("SIMC_ARGUMENTS_INVALID")
        except Exception:
            # Database/network failures must not expose raw exceptions or credentials.
            return _blocked("SIMC_UNAVAILABLE")


__all__ = ("SimulationToolContext", "SimulationToolGateway", "SimulationToolUnauthorized")
