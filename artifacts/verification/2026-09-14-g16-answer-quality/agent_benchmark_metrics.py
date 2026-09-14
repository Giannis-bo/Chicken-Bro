"""Stdlib-only, conservative statistics for paired agent benchmark evidence."""
from collections import Counter, defaultdict
import json
import math
from statistics import median


def _number(value, positive=False):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > 0 if positive else value >= 0))


def summarize_timing(events, total_ms):
    """Union completed intervals; unknown spans remain unknown, never imputed.

    nonToolMs is residual wall time, NOT model reasoning time. Repeated queries
    are observations, not proof of wasted work. Mark retries with retryOf or
    isRetry and polls with isPolling; get_simulation/get_simulation_result/get_simulation_job are
    known polling tools. Timestamps may arrive unordered, with a visible issue.
    """
    if not _number(total_ms):
        raise ValueError("total_ms must be finite and nonnegative")
    tools = {}
    calls = defaultdict(list)
    issues = []
    queries = Counter()
    query_args = {}
    previous = -1
    model_ids = set()
    for index, item in enumerate(events):
        if item.get("type") == "model" and item.get("event") == "start":
            if item.get("id") is not None:
                model_ids.add(item["id"])
        if item.get("type") not in {"tool", "mcpToolCall", "webSearch"}:
            continue
        name = item.get("name") or "unknown"
        call_id = item.get("id")
        stats = tools.setdefault(name, dict(count=0, completedCount=0, unknownCount=0, inclusiveMs=0))
        if item.get("event") == "start":
            stats["count"] += 1
            if not (item.get("retryOf") is not None or item.get("isRetry") or item.get("isPolling")
                    or name in {"get_simulation", "get_simulation_result", "get_simulation_job"}):
                args = item.get("args", {})
                try:
                    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), allow_nan=False)
                except (ValueError, TypeError):
                    issues.append(dict(code="invalid_args", index=index, id=call_id))
                else:
                    queries[(name, canonical)] += 1
                    query_args[(name, canonical)] = args
        at = item.get("atMs")
        if _number(at):
            if at < previous:
                issues.append(dict(code="out_of_order", index=index, id=call_id))
            previous = at
        if call_id is None:
            issues.append(dict(code="missing_id", index=index))
        # Missing IDs must never accidentally match one another.
        calls[("missing", index) if call_id is None else ("id", call_id)].append(item)

    intervals = []
    unknown = []
    for items in calls.values():
        starts = [item for item in items if item.get("event") == "start"]
        ends = [item for item in items if item.get("event") == "end"]
        first = starts[0] if starts else items[0]
        name = first.get("name") or "unknown"
        reason = None
        if first.get("id") is None:
            reason = "missing_id"
        elif len(starts) != 1 or len(ends) != 1 or len(items) != 2:
            reason = "unclosed" if len(starts) == 1 and not ends and len(items) == 1 else "ambiguous_events"
        elif any(item.get("name") != first.get("name") for item in items):
            reason = "name_mismatch"
        elif any(not _number(item.get("atMs")) or item["atMs"] > total_ms for item in items):
            reason = "invalid_timestamp"
        elif ends[0]["atMs"] < starts[0]["atMs"]:
            reason = "negative_interval"
        if reason:
            record = dict(id=first.get("id"), name=name, reason=reason)
            unknown.append(record)
            tools[name]["unknownCount"] += 1
            issues.append(dict(code=reason, id=first.get("id")))
            continue
        begin, end = starts[0]["atMs"], ends[0]["atMs"]
        intervals.append((begin, end))
        tools[name]["completedCount"] += 1
        tools[name]["inclusiveMs"] += end - begin

    tool_ms = 0
    right = 0
    for begin, end in sorted(intervals):
        tool_ms += max(0, end - max(begin, right))
        right = max(right, end)
    repeated = [dict(name=name, args=query_args[(name, args)], count=count, extraCount=count - 1)
                for (name, args), count in sorted(queries.items()) if count > 1]
    return dict(totalMs=total_ms, toolMs=tool_ms, nonToolMs=max(0, total_ms - tool_ms),
                tools=tools, toolCount=sum(item["count"] for item in tools.values()),
                unknownTools=unknown, repeatedQueries=repeated, issues=issues,
                modelRoundTrips=len(model_ids) if model_ids else None)


def _median(values):
    return median(values) if values else None


def _group_summary(runs, pairs):
    variants = {}
    for variant in ("old", "new"):
        selected = [run for run in runs if run.get("variant") == variant]
        variants[variant] = dict(
            runCount=len(selected),
            statusCounts=dict(Counter(run.get("status", "unknown") for run in selected)),
            qualityCounts=dict(Counter(run.get("quality", "unreviewed") for run in selected)),
            qualityPassRate=sum(run.get("quality") == "pass" for run in selected) / len(selected) if selected else None,
        )
    return dict(runCount=len(runs), pairedCount=len(pairs), variants=variants,
                oldMedianMs=_median([pair["oldMs"] for pair in pairs]),
                newMedianMs=_median([pair["newMs"] for pair in pairs]),
                pairedMedianDeltaMs=_median([pair["deltaMs"] for pair in pairs]),
                pairedMedianPercent=_median([pair["percent"] for pair in pairs]))


def paired_summary(results):
    """Only unique quality-pass succeeded pairs contribute to speed estimates.

    Percent is (new-old)/old*100: negative means faster. Variant medians use
    the SAME paired sample, while status/quality counts retain every run.
    Exclusions retain original records so failures and missingness are visible.
    No tail percentile is estimated from these deliberately small samples.
    """
    results = list(results)
    grouped = defaultdict(list)
    exclusions = []
    pairs = []
    for index, run in enumerate(results):
        if (not isinstance(run.get("caseId"), str) or not run["caseId"]
                or not isinstance(run.get("trial"), int) or isinstance(run.get("trial"), bool)
                or run["trial"] < 0 or run.get("variant") not in {"old", "new"}):
            exclusions.append(dict(reason="invalid_identity", index=index, runs=[run]))
            continue
        grouped[(run["caseId"], run["trial"])].append(run)
    for (case_id, trial), runs in sorted(grouped.items()):
        by_variant = {variant: [run for run in runs if run["variant"] == variant] for variant in ("old", "new")}
        reason = None
        if any(len(items) > 1 for items in by_variant.values()):
            reason = "duplicate_variant"
        elif any(not items for items in by_variant.values()):
            reason = "missing_variant"
        elif any(run.get("status") != "succeeded" for run in runs):
            reason = "not_succeeded"
        elif any(run.get("quality") != "pass" for run in runs):
            reason = "quality_not_pass"
        elif any(not _number(run.get("totalMs"), positive=True) for run in runs):
            reason = "invalid_duration"
        elif len({run.get("category") for run in runs}) != 1:
            reason = "category_mismatch"
        if reason:
            exclusions.append(dict(caseId=case_id, trial=trial, reason=reason, runs=runs))
            continue
        old, new = by_variant["old"][0], by_variant["new"][0]
        delta = new["totalMs"] - old["totalMs"]
        pairs.append(dict(caseId=case_id, trial=trial, category=old.get("category"),
                          oldMs=old["totalMs"], newMs=new["totalMs"], deltaMs=delta,
                          percent=delta / old["totalMs"] * 100))
    categories = {category: _group_summary([run for run in results if run.get("category") == category],
                                           [pair for pair in pairs if pair["category"] == category])
                  for category in sorted({run["category"] for run in results if run.get("category") is not None})}
    return dict(overall=_group_summary(results, pairs), categories=categories, pairs=pairs,
                exclusions=exclusions, percentConvention="(new-old)/old*100; negative means faster")
