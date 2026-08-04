import ast
from collections import Counter
import copy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import unittest

from server.gear_contracts import CANONICAL_GEAR_SLOTS


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "tests/fixtures/gear_canonical_owner_registry.json"
TARGETS = frozenset({
    "server/gear_exact_item_instance.py",
    "server/gear_exact_authority.py",
    "server/simc_item_effect_support.py",
    "server/simc_item_effect_probe.py",
    "scripts/simc-item-effect-probe.py",
})
PROFILE_BY_PATH = {
    path: (
        "simc_probe_cli_bootstrap_v1"
        if path.startswith("scripts/")
        else "server_owner_declaration_v1"
    )
    for path in TARGETS
}
EXEMPTION_UNIVERSE = frozenset({
    (
        "server/gear_exact_item_instance.py",
        "EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER_ASSIGN",
        "module_assignment",
        "EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER",
        "Assign",
    ),
    (
        "server/gear_exact_item_instance.py",
        "EXACT_STATIC_FACTS_MAX_CANONICAL_BYTES_ASSIGN",
        "module_assignment",
        "EXACT_STATIC_FACTS_MAX_CANONICAL_BYTES",
        "Assign",
    ),
    (
        "server/simc_item_effect_support.py",
        "EFFECT_DYNAMIC_RECORD_KEYS_ASSIGN",
        "module_assignment",
        "_DYNAMIC_RECORD_KEYS",
        "Assign",
    ),
    (
        "server/simc_item_effect_support.py",
        "EFFECT_UNSUPPORTED_RECORD_KEYS_ASSIGN",
        "module_assignment",
        "_UNSUPPORTED_RECORD_KEYS",
        "Assign",
    ),
    (
        "scripts/simc-item-effect-probe.py",
        "CLI_ROOT_ASSIGNMENT",
        "cli_bootstrap",
        "ROOT",
        "Assign",
    ),
    (
        "scripts/simc-item-effect-probe.py",
        "CLI_PATH_GUARD",
        "cli_bootstrap",
        None,
        "If",
    ),
    (
        "scripts/simc-item-effect-probe.py",
        "CLI_VALUE_ERROR_BASE",
        "cli_class",
        "_StrictJsonError",
        "ClassDef",
    ),
    (
        "scripts/simc-item-effect-probe.py",
        "CLI_ARGUMENT_PARSER_BASE",
        "cli_class",
        "_ReasonCodeArgumentParser",
        "ClassDef",
    ),
    (
        "scripts/simc-item-effect-probe.py",
        "CLI_MAIN_GUARD",
        "cli_main_guard",
        None,
        "If",
    ),
})
DELETED_PUBLIC_NAMES = frozenset({
    "build_exact_item_identity",
    "build_exact_progression_binding",
    "build_exact_authority_envelope",
    "resolve_exact_item_effect_support",
    "validate_effect_record",
    "seal_legacy_effect_record",
    "effect_record_key",
    "effect_support_key",
    "valid_runtime_revision",
    "valid_effect_tokens",
})
FORBIDDEN_OLD_ENGINE_SYMBOLS = frozenset({
    "_ResolvedSymbol",
    "_UnknownBinding",
    "_CallableTarget",
    "_ClassTarget",
    "_ScopeBindingCollector",
    "_resolve_expression",
    "_called_targets",
    "_bind_callable_target",
    "_sealed_call_graph",
    "IMPORTED_CALLABLE_ALLOWLIST",
    "LOCAL_CALLABLE_ALLOWLIST",
    "PUBLIC_FUNCTION_ALLOWLIST",
})
SEALED_SIGNATURES = {
    (
        "server/gear_exact_item_instance.py",
        "seal_exact_item",
    ): "exact_slot_payload: object -> CanonicalResult",
    (
        "server/gear_exact_item_instance.py",
        "seal_exact_static_facts",
    ): "exact: SealedCanonicalDocument, facts: object -> CanonicalResult",
    (
        "server/gear_exact_item_instance.py",
        "derive_simc_serializer_input",
    ): "exact: SealedCanonicalDocument -> dict[str, str]",
    (
        "server/gear_exact_authority.py",
        "seal_exact_progression",
    ): (
        "exact: SealedCanonicalDocument, *, season_revision: str, "
        "gear_rule_revision: str, slot: str, has_crafted_source: bool "
        "-> CanonicalResult"
    ),
    (
        "server/gear_exact_authority.py",
        "seal_exact_authority_envelope",
    ): (
        "*, exact: SealedCanonicalDocument, "
        "static_facts: SealedCanonicalDocument, "
        "progression: SealedCanonicalDocument, "
        "effect_support: SealedCanonicalDocument, "
        "resolver_revision: str -> CanonicalResult"
    ),
    (
        "server/simc_item_effect_support.py",
        "derive_exact_effect_subjects",
    ): "exact: SealedCanonicalDocument -> tuple[EffectSubject, ...]",
    (
        "server/simc_item_effect_support.py",
        "seal_effect_record",
    ): "record_payload: object, *, runtime_revision: str -> CanonicalResult",
    (
        "server/simc_item_effect_support.py",
        "verify_effect_record",
    ): "document: object, *, runtime_revision: object -> bool",
    (
        "server/simc_item_effect_support.py",
        "resolve_exact_effect_support",
    ): (
        "exact: SealedCanonicalDocument, *, runtime_revision: object, "
        "records: Sequence[SealedCanonicalDocument] -> EffectSupportOutcome"
    ),
    (
        "server/simc_item_effect_probe.py",
        "evaluate_effect_probe",
    ): (
        "manifest: object, experiment: object, control: object, *, "
        "runtime_revision: object -> CanonicalResult"
    ),
    (
        "scripts/simc-item-effect-probe.py",
        "main",
    ): "argv: list[str] | None=None -> int",
}
TRACK_AUTHORITY_RELATIVE_IMPORT = (
    ".gear_track_authority",
    "resolve_exact_instance_progression",
    "resolve_exact_instance_progression",
)
TRACK_AUTHORITY_ABSOLUTE_IMPORT = (
    "gear_track_authority",
    "resolve_exact_instance_progression",
    "resolve_exact_instance_progression",
)
TRACK_AUTHORITY_OWNER_NAME = "resolve_exact_instance_progression"
TRACK_AUTHORITY_PRODUCTION_ASSIGNMENT_SHA256 = (
    "0c5d9ae84b8b0c5754f46be974e462a7c2235d89593c3fa6a5197b8b74ebc75d"
)
FROZEN_V1_DIRECT_PRIMITIVE_EXCEPTIONS = Counter((
    ("server/gear_exact_item_instance.py", "_canonical", "DUPLICATE_JSON_OWNER", "7231941be36f1e81041b1597a91a543b42f48c410be92ac9238de06fd4dc1058"),
    ("server/gear_exact_item_instance.py", "_canonical_bytes", "DUPLICATE_JSON_OWNER", "7231941be36f1e81041b1597a91a543b42f48c410be92ac9238de06fd4dc1058"),
    ("server/gear_exact_item_instance.py", "_hash", "DUPLICATE_HASH_OWNER", "72e0ca3c56475eb0e591218d85a12e77c8eec5e237feaf9a46148188e9ed1f38"),
    ("server/gear_exact_item_instance.py", "_text", "IDENTITY_TRIM", "76193f035544dbf4410d97b6bb66e790ce9a81005ca9626c99a8067972771351"),
    ("server/gear_exact_item_instance.py", "_text", "IDENTITY_COERCION", "88d3520b955995521e902e02cd7ed820574701d159c015fc2852eeaab3bd2e61"),
    ("server/gear_exact_item_instance.py", "_canonical_context", "IDENTITY_COERCION", "9fa2a35533437c0274affe76a7b1619b3e9ef75a1bdae6f73cc29c25b992a17c"),
    ("server/gear_exact_item_instance.py", "_canonical_context", "IDENTITY_COERCION", "9fa2a35533437c0274affe76a7b1619b3e9ef75a1bdae6f73cc29c25b992a17c"),
    ("server/gear_exact_item_instance.py", "_canonical_context", "IDENTITY_TRIM", "84cb1f8f503d698f97ff7b08f108f3bbc0760985a10dd861301b3548c7d38e9e"),
    ("server/gear_exact_item_instance.py", "_canonical_context", "IDENTITY_COERCION", "9172f9f6deaae82373906c7fd148ee65d7cea4f91a3f2d93745737c5673aaaed"),
    ("server/gear_exact_item_instance.py", "_canonical_context", "IDENTITY_COERCION", "019dfe6b75fcef641ee0b24e169a3576836536a91415032aeca085d2812d923a"),
    ("server/gear_exact_item_instance.py", "_raw_tokens", "IDENTITY_TRIM", "2cc3d1350f1c21f2b556937457fa70ea7ab6efb453e76e13bc5687165351d97d"),
    ("server/gear_exact_item_instance.py", "_raw_tokens", "IDENTITY_COERCION", "6c6a4d567443d96ee7f9d07bbb204dd9e92a330c87aabae410295bfb276a63c1"),
    ("server/gear_exact_item_instance.py", "_set_tokens", "IDENTITY_SORT_DEDUPE", "a3ffee7061e217bb8f6a455a863d1bfbcacb62ef202faf7e47c28e137ec8e6ea"),
    ("server/gear_exact_item_instance.py", "canonical_enhancement_selection", "DUPLICATE_HASH_OWNER", "0a5cf397fdb7508337974e0ba7a404fc4e025b3fe91f8b63dfa3822c3121be1f"),
    ("server/gear_exact_item_instance.py", "_serializer_input", "IDENTITY_COERCION", "ce20643b915809b71d818a374d24e5b0b825817d651aafb58bda8936dd40d5cf"),
    ("server/gear_exact_item_instance.py", "_serializer_input", "IDENTITY_COERCION", "d9a9216a4d47b9504ea1fdb080ff5e01215827e00abc1f8dc1ab3ced09f58d04"),
    ("server/gear_exact_item_instance.py", "build_exact_item_instance", "CATALOG_DEPENDENCY", "091ab6d2bd135623aa02be6aa7328aa38f67315172d64733e6afc61be42b2af2"),
    ("server/gear_exact_item_instance.py", "build_exact_item_instance", "DUPLICATE_HASH_OWNER", "0c5a7104a2a9d846495c91bb1c36135dbfc4b1767f6bfeba6d7430a5bd7af03b"),
    ("server/gear_exact_item_instance.py", "build_exact_item_instance", "DUPLICATE_HASH_OWNER", "ea208855052b7c112adf648f7cce112720920ee9d51738f863f9978fbbda230e"),
))


@dataclass(frozen=True, order=True)
class Violation:
    path: str
    function: str
    code: str
    detail: str


def _formatted(violations: list[Violation]) -> str:
    return "\n".join(
        f"{item.path}:{item.function}:{item.code}:{item.detail}"
        for item in violations
    )


def _load_registry() -> dict[str, object]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _target_trees() -> dict[str, ast.Module]:
    return {
        path: ast.parse(
            (ROOT / path).read_text(encoding="utf-8"),
            filename=path,
        )
        for path in TARGETS
    }


def _repository_python_trees() -> dict[str, ast.Module]:
    trees: dict[str, ast.Module] = {}
    for directory in ("server", "scripts", "tests"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            relative = path.relative_to(ROOT).as_posix()
            trees[relative] = ast.parse(
                path.read_text(encoding="utf-8"),
                filename=relative,
            )
    return trees


REGISTRY = _load_registry()
TREES = _target_trees()


def _registry_finding(code: str, detail: str) -> Violation:
    return Violation(
        "tests/fixtures/gear_canonical_owner_registry.json",
        "<registry>",
        code,
        detail,
    )


def _schema_finding(code: str, detail: str) -> Violation:
    return _registry_finding(f"REGISTRY_SCHEMA_{code}", detail)


def _registry_schema_violations(registry: object) -> list[Violation]:
    violations: list[Violation] = []
    root_keys = {
        "schemaVersion",
        "proofClaim",
        "digestSerialization",
        "targets",
    }
    if type(registry) is not dict:
        return [_schema_finding("ROOT_INVALID", type(registry).__name__)]
    if set(registry) != root_keys:
        violations.append(_schema_finding("ROOT_KEYS_INVALID", ",".join(sorted(str(key) for key in set(registry).symmetric_difference(root_keys)))))
    if type(registry.get("schemaVersion")) is not int:
        violations.append(_schema_finding("VERSION_INVALID", type(registry.get("schemaVersion")).__name__))
    if type(registry.get("proofClaim")) is not str:
        violations.append(_schema_finding("PROOF_CLAIM_INVALID", type(registry.get("proofClaim")).__name__))
    if type(registry.get("digestSerialization")) is not str:
        violations.append(_schema_finding("DIGEST_SERIALIZATION_INVALID", type(registry.get("digestSerialization")).__name__))

    targets = registry.get("targets")
    if type(targets) is not list:
        violations.append(_schema_finding("TARGETS_INVALID", type(targets).__name__))
        return sorted(set(violations))
    target_keys = {
        "path",
        "profile",
        "sealedEntrypoints",
        "publicCallables",
        "exports",
        "reexports",
        "imports",
        "importFallbackPairs",
        "exemptions",
    }
    exemption_keys = {
        "id",
        "role",
        "binding",
        "nodeKind",
        "astSha256",
        "reason",
        "owner",
    }
    for index, target in enumerate(targets):
        location = f"targets[{index}]"
        if type(target) is not dict:
            violations.append(_schema_finding("TARGET_INVALID", f"{location}:{type(target).__name__}"))
            continue
        if set(target) != target_keys:
            violations.append(_schema_finding("TARGET_KEYS_INVALID", f"{location}:{','.join(sorted(str(key) for key in set(target).symmetric_difference(target_keys)))}"))
        for field in ("path", "profile"):
            if type(target.get(field)) is not str:
                violations.append(_schema_finding("TARGET_SCALAR_INVALID", f"{location}.{field}:{type(target.get(field)).__name__}"))
        for field in (
            "sealedEntrypoints",
            "publicCallables",
            "exports",
            "reexports",
            "imports",
            "importFallbackPairs",
            "exemptions",
        ):
            if type(target.get(field)) is not list:
                violations.append(_schema_finding("TARGET_LIST_INVALID", f"{location}.{field}:{type(target.get(field)).__name__}"))

        for field in ("sealedEntrypoints", "publicCallables", "exports"):
            values = target.get(field)
            if type(values) is list:
                for item_index, value in enumerate(values):
                    if type(value) is not str:
                        violations.append(_schema_finding("NAME_INVALID", f"{location}.{field}[{item_index}]:{type(value).__name__}"))

        imports = target.get("imports")
        if type(imports) is list:
            for item_index, record in enumerate(imports):
                if not _valid_import_record(record):
                    violations.append(_schema_finding("IMPORT_INVALID", f"{location}.imports[{item_index}]"))

        fallbacks = target.get("importFallbackPairs")
        if type(fallbacks) is list:
            for item_index, pair in enumerate(fallbacks):
                pair_location = f"{location}.importFallbackPairs[{item_index}]"
                if type(pair) is not dict or set(pair) != {"relative", "absolute"}:
                    violations.append(_schema_finding("FALLBACK_INVALID", pair_location))
                    continue
                if not _valid_import_record(pair.get("relative")) or not _valid_import_record(pair.get("absolute")):
                    violations.append(_schema_finding("FALLBACK_IMPORT_INVALID", pair_location))

        reexports = target.get("reexports")
        if type(reexports) is list:
            for item_index, record in enumerate(reexports):
                item_location = f"{location}.reexports[{item_index}]"
                if (
                    type(record) is not dict
                    or set(record) != {"export", "module", "symbol", "alias"}
                    or any(type(record.get(field)) is not str for field in ("export", "module", "symbol", "alias"))
                ):
                    violations.append(_schema_finding("REEXPORT_INVALID", item_location))

        exemptions = target.get("exemptions")
        if type(exemptions) is list:
            for item_index, exemption in enumerate(exemptions):
                item_location = f"{location}.exemptions[{item_index}]"
                if type(exemption) is not dict or set(exemption) != exemption_keys:
                    violations.append(_schema_finding("EXEMPTION_INVALID", item_location))
                    continue
                if (
                    any(type(exemption.get(field)) is not str for field in ("id", "role", "nodeKind", "astSha256", "reason", "owner"))
                    or exemption.get("binding") is not None
                    and type(exemption.get("binding")) is not str
                    or len(exemption.get("astSha256", "")) != 64
                    or any(character not in "0123456789abcdef" for character in exemption.get("astSha256", ""))
                ):
                    violations.append(_schema_finding("EXEMPTION_FIELD_INVALID", item_location))
    return sorted(set(violations))


def _ast_digest(node: ast.AST) -> str:
    serialized = ast.dump(
        node,
        annotate_fields=True,
        include_attributes=False,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _import_tuple(record: dict[str, object]) -> tuple[object, object, object]:
    return (record.get("module"), record.get("symbol"), record.get("alias"))


def _valid_import_record(record: object) -> bool:
    return (
        type(record) is dict
        and set(record) == {"module", "symbol", "alias"}
        and type(record.get("module")) is str
        and (
            record.get("symbol") is None
            or type(record.get("symbol")) is str
        )
        and type(record.get("alias")) is str
    )


def _unique_string_list(value: object) -> bool:
    return (
        type(value) is list
        and all(type(item) is str for item in value)
        and len(value) == len(set(value))
    )


def _import_detail(record: tuple[object, object, object]) -> str:
    module, symbol, alias = record
    return f"{module}:{symbol if symbol is not None else '<module>'} as {alias}"


def _physical_imports(tree: ast.Module) -> list[tuple[object, object, object]]:
    imports: list[tuple[object, object, object]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((
                    alias.name,
                    None,
                    alias.asname or alias.name.split(".")[0],
                ))
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            for alias in node.names:
                imports.append((module, alias.name, alias.asname or alias.name))
    return imports


def _imports_from_statement(
    node: ast.Import | ast.ImportFrom,
) -> list[tuple[object, object, object]]:
    if isinstance(node, ast.Import):
        return [
            (alias.name, None, alias.asname or alias.name.split(".")[0])
            for alias in node.names
        ]
    module = "." * node.level + (node.module or "")
    return [
        (module, alias.name, alias.asname or alias.name)
        for alias in node.names
    ]


def _fallback_pairs_and_violations(
    path: str,
    tree: ast.Module,
) -> tuple[
    list[tuple[tuple[object, object, object], tuple[object, object, object]]],
    list[Violation],
]:
    pairs: list[
        tuple[tuple[object, object, object], tuple[object, object, object]]
    ] = []
    violations: list[Violation] = []
    for node in tree.body:
        if not isinstance(node, ast.Try):
            continue
        valid_structure = (
            len(node.handlers) == 1
            and isinstance(node.handlers[0].type, ast.Name)
            and node.handlers[0].type.id == "ImportError"
            and node.handlers[0].name is None
            and not node.orelse
            and not node.finalbody
            and node.body
            and node.handlers[0].body
            and all(
                isinstance(statement, (ast.Import, ast.ImportFrom))
                for statement in [*node.body, *node.handlers[0].body]
            )
        )
        if not valid_structure:
            violations.append(Violation(
                path,
                "<module>",
                "FALLBACK_STRUCTURE_INVALID",
                "Try must contain only mirrored imports and one ImportError handler",
            ))
            continue
        relative = [
            item
            for statement in node.body
            for item in _imports_from_statement(statement)
        ]
        absolute = [
            item
            for statement in node.handlers[0].body
            for item in _imports_from_statement(statement)
        ]
        relative_counts = Counter(relative)
        absolute_counts = Counter(absolute)
        if any(count != 1 for count in relative_counts.values()) or any(
            count != 1 for count in absolute_counts.values()
        ):
            violations.append(Violation(
                path,
                "<module>",
                "FALLBACK_MIRROR_INVALID",
                "duplicate import binding",
            ))
        expected_absolute = Counter()
        valid_relative = True
        for item, count in relative_counts.items():
            if not str(item[0]).startswith("."):
                valid_relative = False
                continue
            mirror = (str(item[0]).lstrip("."), item[1], item[2])
            expected_absolute[mirror] += count
            if count == 1 and absolute_counts[mirror] == 1:
                pairs.append((item, mirror))
        if not valid_relative or expected_absolute != absolute_counts:
            missing = expected_absolute - absolute_counts
            extra = absolute_counts - expected_absolute
            violations.append(Violation(
                path,
                "<module>",
                "FALLBACK_MIRROR_INVALID",
                f"missing={sorted(map(str, missing.elements()))};extra={sorted(map(str, extra.elements()))}",
            ))
    return pairs, sorted(set(violations))


def _local_public_callables(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    }


def _local_definitions(tree: ast.Module) -> set[str]:
    definitions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            definitions.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            definitions.add(node.target.id)
    return definitions


def _module_import_bindings(
    path: str,
    tree: ast.Module,
) -> set[tuple[object, object, object]]:
    bindings = {
        item
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for item in _imports_from_statement(node)
    }
    fallback_pairs, fallback_violations = _fallback_pairs_and_violations(path, tree)
    if not fallback_violations:
        for relative, absolute in fallback_pairs:
            bindings.add(relative)
            bindings.add(absolute)
    return bindings


def _exports(tree: ast.Module) -> list[str] | None:
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        )
    ]
    if not assignments:
        return []
    if len(assignments) != 1:
        return None
    try:
        value = ast.literal_eval(assignments[0].value)
    except (ValueError, TypeError):
        return None
    if (
        type(value) not in {tuple, list}
        or any(type(item) is not str for item in value)
    ):
        return None
    return list(value)


def _actual_reexports(path: str, tree: ast.Module) -> set[tuple[object, ...]]:
    exports = _exports(tree) or []
    local = _local_definitions(tree)
    by_alias: dict[str, list[tuple[object, object, object]]] = {}
    for item in _module_import_bindings(path, tree):
        by_alias.setdefault(str(item[2]), []).append(item)
    result: set[tuple[object, ...]] = set()
    for exported in exports:
        if exported in local:
            continue
        candidates = by_alias.get(exported, [])
        if not candidates:
            continue
        chosen = next(
            (item for item in candidates if str(item[0]).startswith(".")),
            candidates[0],
        )
        result.add((exported, *chosen))
    return result


def _assignment_has_binding(node: ast.AST, binding: object) -> bool:
    return (
        isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == binding
            for target in node.targets
        )
    )


def _exemption_candidates(
    tree: ast.Module,
    exemption: dict[str, object],
) -> list[ast.AST]:
    role = exemption.get("role")
    binding = exemption.get("binding")
    node_kind = exemption.get("nodeKind")
    candidates = [
        node for node in tree.body if type(node).__name__ == node_kind
    ]
    if role in {"module_assignment", "cli_bootstrap"} and binding is not None:
        return [node for node in candidates if _assignment_has_binding(node, binding)]
    if role == "cli_class":
        return [
            node
            for node in candidates
            if isinstance(node, ast.ClassDef) and node.name == binding
        ]
    if role in {"cli_bootstrap", "cli_main_guard"} and binding is None:
        return candidates
    return []


def _registry_violations(
    registry: dict[str, object],
    trees: dict[str, ast.Module],
) -> list[Violation]:
    schema_violations = _registry_schema_violations(registry)
    if schema_violations:
        return schema_violations
    violations: list[Violation] = []
    if registry.get("schemaVersion") != 1:
        violations.append(_registry_finding("SCHEMA_VERSION_INVALID", "schemaVersion"))
    if registry.get("proofClaim") != "source_change_control_only":
        violations.append(_registry_finding("PROOF_CLAIM_INVALID", str(registry.get("proofClaim"))))
    if registry.get("digestSerialization") != "python_ast_dump_v1":
        violations.append(_registry_finding("DIGEST_SERIALIZATION_INVALID", str(registry.get("digestSerialization"))))

    raw_targets = registry.get("targets")
    if type(raw_targets) is not list:
        return [*violations, _registry_finding("TARGETS_INVALID", type(raw_targets).__name__)]
    expected_target_keys = {
        "path",
        "profile",
        "sealedEntrypoints",
        "publicCallables",
        "exports",
        "reexports",
        "imports",
        "importFallbackPairs",
        "exemptions",
    }
    targets = []
    for target in raw_targets:
        if (
            type(target) is not dict
            or set(target) != expected_target_keys
            or type(target.get("path")) is not str
        ):
            violations.append(_registry_finding(
                "TARGET_RECORD_INVALID",
                type(target).__name__,
            ))
            continue
        targets.append(target)
    paths = [target.get("path") for target in targets]
    duplicate_paths = [
        str(path) for path, count in Counter(paths).items() if count != 1
    ]
    for path in duplicate_paths:
        violations.append(_registry_finding("DUPLICATE_TARGET", path))
    if set(paths) != TARGETS:
        violations.append(_registry_finding(
            "TARGET_UNIVERSE_MISMATCH",
            ",".join(sorted(str(path) for path in set(paths).symmetric_difference(TARGETS))),
        ))

    observed_exemptions: list[tuple[object, ...]] = []
    for target in targets:
        path = target.get("path")
        if path not in TARGETS:
            continue
        tree = trees.get(path)
        if tree is None:
            violations.append(_registry_finding("TARGET_TREE_MISSING", str(path)))
            continue
        if target.get("profile") != PROFILE_BY_PATH[path]:
            violations.append(_registry_finding("PROFILE_MISMATCH", str(path)))

        raw_imports = target.get("imports")
        imports = raw_imports if type(raw_imports) is list else []
        import_tuples: list[tuple[object, object, object]] = []
        for record in imports:
            if not _valid_import_record(record):
                violations.append(_registry_finding("IMPORT_RECORD_INVALID", str(path)))
                continue
            item = _import_tuple(record)
            import_tuples.append(item)
            if "*" in {item[0], item[1], item[2]}:
                violations.append(_registry_finding("IMPORT_WILDCARD_FORBIDDEN", _import_detail(item)))
        for item, count in Counter(import_tuples).items():
            if count != 1:
                violations.append(_registry_finding("DUPLICATE_IMPORT_RECORD", f"{path}:{_import_detail(item)}"))

        declared_pairs = []
        raw_pairs = target.get("importFallbackPairs")
        for pair in raw_pairs if type(raw_pairs) is list else []:
            if type(pair) is not dict or set(pair) != {"relative", "absolute"}:
                violations.append(_registry_finding("FALLBACK_PAIR_INVALID", str(path)))
                continue
            relative = pair.get("relative")
            absolute = pair.get("absolute")
            if not _valid_import_record(relative) or not _valid_import_record(absolute):
                violations.append(_registry_finding("FALLBACK_PAIR_INVALID", str(path)))
                continue
            rel = _import_tuple(relative)
            abs_ = _import_tuple(absolute)
            declared_pairs.append((rel, abs_))
            if (
                not str(rel[0]).startswith(".")
                or str(abs_[0]) != str(rel[0]).lstrip(".")
                or rel[1:] != abs_[1:]
                or rel not in import_tuples
                or abs_ not in import_tuples
            ):
                violations.append(_registry_finding("FALLBACK_PAIR_INVALID", f"{path}:{rel}:{abs_}"))
        actual_pairs, fallback_violations = _fallback_pairs_and_violations(path, tree)
        violations.extend(fallback_violations)
        if Counter(declared_pairs) != Counter(actual_pairs):
            violations.append(_registry_finding("FALLBACK_PAIR_INVALID", f"{path}:coverage"))

        public = target.get("publicCallables")
        definition_counts = Counter(
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        )
        if (
            not _unique_string_list(public)
            or set(public) != _local_public_callables(tree)
            or any(definition_counts[name] != 1 for name in public)
        ):
            violations.append(_registry_finding("PUBLIC_CALLABLE_MISMATCH", str(path)))
        exports = target.get("exports")
        actual_exports = _exports(tree)
        if not _unique_string_list(exports) or exports != actual_exports:
            violations.append(_registry_finding("EXPORT_MISMATCH", str(path)))
        sealed = target.get("sealedEntrypoints")
        expected_sealed = {
            function
            for sealed_path, function in SEALED_SIGNATURES
            if sealed_path == path
        }
        if (
            not _unique_string_list(sealed)
            or set(sealed) != expected_sealed
            or not set(sealed).issubset(_local_public_callables(tree))
            or any(definition_counts[name] != 1 for name in sealed)
        ):
            violations.append(_registry_finding("SEALED_ENTRYPOINT_MISMATCH", str(path)))

        raw_reexports = target.get("reexports")
        declared_reexports = set()
        module_bindings = _module_import_bindings(path, tree)
        for record in raw_reexports if type(raw_reexports) is list else []:
            if type(record) is not dict or set(record) != {"export", "module", "symbol", "alias"}:
                violations.append(_registry_finding("REEXPORT_RECORD_INVALID", str(path)))
                continue
            declared_reexports.add((
                record.get("export"),
                record.get("module"),
                record.get("symbol"),
                record.get("alias"),
            ))
            binding = (
                record.get("module"),
                record.get("symbol"),
                record.get("alias"),
            )
            if (
                binding not in module_bindings
                or record.get("export") != record.get("alias")
            ):
                violations.append(_registry_finding(
                    "REEXPORT_MODULE_BINDING_REQUIRED",
                    f"{path}:{record.get('export')}",
                ))
        if type(raw_reexports) is list and len(raw_reexports) != len(declared_reexports):
            violations.append(_registry_finding("DUPLICATE_REEXPORT", str(path)))
        actual_reexports = _actual_reexports(path, tree)
        if declared_reexports != actual_reexports:
            violations.append(_registry_finding("REEXPORT_MISMATCH", str(path)))
        valid_exports = _local_definitions(tree) | {
            str(item[2]) for item in module_bindings
        }
        for exported in actual_exports or []:
            if exported not in valid_exports:
                violations.append(_registry_finding(
                    "UNDEFINED_EXPORT",
                    f"{path}:{exported}",
                ))

        raw_exemptions = target.get("exemptions")
        exemptions = raw_exemptions if type(raw_exemptions) is list else []
        ids = [
            item.get("id")
            for item in exemptions
            if type(item) is dict and type(item.get("id")) is str
        ]
        for exemption_id, count in Counter(ids).items():
            if count != 1:
                violations.append(_registry_finding("DUPLICATE_EXEMPTION", f"{path}:{exemption_id}"))
        for exemption in exemptions:
            if type(exemption) is not dict:
                violations.append(_registry_finding("EXEMPTION_RECORD_INVALID", str(path)))
                continue
            valid_shape = (
                type(exemption.get("id")) is str
                and type(exemption.get("role")) is str
                and (
                    exemption.get("binding") is None
                    or type(exemption.get("binding")) is str
                )
                and type(exemption.get("nodeKind")) is str
                and type(exemption.get("astSha256")) is str
                and len(exemption.get("astSha256")) == 64
            )
            if not valid_shape:
                violations.append(_registry_finding("EXEMPTION_RECORD_INVALID", f"{path}:shape"))
                continue
            observed_exemptions.append((
                path,
                exemption.get("id"),
                exemption.get("role"),
                exemption.get("binding"),
                exemption.get("nodeKind"),
            ))
            if (
                type(exemption.get("reason")) is not str
                or not exemption.get("reason")
                or exemption.get("owner") != "canonical_source_change_control"
            ):
                violations.append(_registry_finding("EXEMPTION_RECORD_INVALID", f"{path}:{exemption.get('id')}"))
            candidates = _exemption_candidates(tree, exemption)
            matching = [
                node
                for node in candidates
                if _ast_digest(node) == exemption.get("astSha256")
            ]
            if not candidates:
                violations.append(_registry_finding("EXEMPTION_ORPHAN", f"{path}:{exemption.get('id')}"))
            elif len(matching) > 1:
                violations.append(_registry_finding("EXEMPTION_MULTIMATCH", f"{path}:{exemption.get('id')}"))
            elif not matching:
                violations.append(_registry_finding("EXEMPTION_DIGEST_MISMATCH", f"{path}:{exemption.get('id')}"))

    if Counter(observed_exemptions) != Counter(EXEMPTION_UNIVERSE):
        violations.append(_registry_finding("EXEMPTION_UNIVERSE_MISMATCH", "fixed-nine"))
    return sorted(set(violations))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, (ast.Name, ast.Attribute)):
            return f"{_call_name(node.value)}.{node.attr}"
        return f"{ast.unparse(node.value)}.{node.attr}"
    if isinstance(node, ast.Lambda):
        return "<lambda>"
    return ast.unparse(node)


def _bound_target_names(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Starred):
        return _bound_target_names(node.value)
    if isinstance(node, (ast.Tuple, ast.List)):
        return set().union(*(_bound_target_names(item) for item in node.elts))
    return set()


class _TrackOwnerLexicalBindings(ast.NodeVisitor):
    """Collect one outer lexical binding while skipping nested code bodies."""

    def __init__(
        self,
        binding_name: str,
        *,
        approved_assignment: ast.Assign | None = None,
    ) -> None:
        self.binding_name = binding_name
        self.approved_assignment = approved_assignment
        self.reasons: set[str] = set()

    def _record_target(self, node: ast.AST, reason: str) -> None:
        if self.binding_name in _bound_target_names(node):
            self.reasons.add(reason)

    def visit_Assign(self, node: ast.Assign) -> None:
        if node is not self.approved_assignment:
            for target in node.targets:
                self._record_target(target, "assign")
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._record_target(node.target, "annassign")
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._record_target(node.target, "augassign")
        self.visit(node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._record_target(node.target, "namedexpr")
        self.visit(node.value)

    def visit_For(self, node: ast.For) -> None:
        self._record_target(node.target, "for")
        self.visit(node.iter)
        for item in (*node.body, *node.orelse):
            self.visit(item)

    visit_AsyncFor = visit_For

    def visit_With(self, node: ast.With) -> None:
        for item in node.items:
            self.visit(item.context_expr)
            if item.optional_vars is not None:
                self._record_target(item.optional_vars, "with")
        for statement in node.body:
            self.visit(statement)

    visit_AsyncWith = visit_With

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name == self.binding_name:
            self.reasons.add("except")
        if node.type is not None:
            self.visit(node.type)
        for statement in node.body:
            self.visit(statement)

    def visit_Delete(self, node: ast.Delete) -> None:
        for target in node.targets:
            self._record_target(target, "delete")

    def visit_Import(self, node: ast.Import) -> None:
        for item in node.names:
            bound_name = item.asname or item.name.split(".", 1)[0]
            if bound_name == self.binding_name:
                self.reasons.add("import")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for item in node.names:
            if (item.asname or item.name) == self.binding_name:
                self.reasons.add("import")

    def visit_Global(self, node: ast.Global) -> None:
        if self.binding_name in node.names:
            self.reasons.add("global")

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        if self.binding_name in node.names:
            self.reasons.add("nonlocal")

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name == self.binding_name:
            self.reasons.add("match")
        if node.pattern is not None:
            self.visit(node.pattern)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name == self.binding_name:
            self.reasons.add("match")

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest == self.binding_name:
            self.reasons.add("match")
        self.generic_visit(node)

    def _visit_definition_header(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> None:
        if node.name == self.binding_name:
            self.reasons.add("function")
        for item in (*node.decorator_list, *node.args.defaults):
            self.visit(item)
        for item in node.args.kw_defaults:
            if item is not None:
                self.visit(item)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_definition_header(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_definition_header(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name == self.binding_name:
            self.reasons.add("class")
        for item in (*node.decorator_list, *node.bases):
            self.visit(item)
        for item in node.keywords:
            self.visit(item.value)

    def visit_TypeAlias(self, node: ast.AST) -> None:
        name = getattr(node, "name", None)
        if isinstance(name, ast.AST):
            self._record_target(name, "type-alias")

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for item in node.args.defaults:
            self.visit(item)
        for item in node.args.kw_defaults:
            if item is not None:
                self.visit(item)


class _TrackOwnerCallCounter(ast.NodeVisitor):
    """Count only extra Track-owner invocations in the outer definition."""

    def __init__(self, approved_call: ast.Call | None) -> None:
        self.count = 0
        self.approved_call = approved_call

    def visit_Call(self, node: ast.Call) -> None:
        if (
            node is not self.approved_call
            and isinstance(node.func, ast.Name)
            and node.func.id == TRACK_AUTHORITY_OWNER_NAME
        ):
            self.count += 1
        self.generic_visit(node)

    def _visit_defaults(self, arguments: ast.arguments) -> None:
        for item in arguments.defaults:
            self.visit(item)
        for item in arguments.kw_defaults:
            if item is not None:
                self.visit(item)

    def _visit_decorators(self, decorators: list[ast.expr]) -> None:
        for item in decorators:
            if (
                isinstance(item, ast.Name)
                and item.id == TRACK_AUTHORITY_OWNER_NAME
            ):
                self.count += 1
            self.visit(item)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_decorators(node.decorator_list)
        self._visit_defaults(node.args)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._visit_defaults(node.args)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._visit_decorators(node.decorator_list)
        for item in node.bases:
            self.visit(item)
        for item in node.keywords:
            if (
                item.arg == "metaclass"
                and isinstance(item.value, ast.Name)
                and item.value.id == TRACK_AUTHORITY_OWNER_NAME
            ):
                self.count += 1
            self.visit(item.value)
        for statement in node.body:
            self.visit(statement)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self.visit(node.value)

    def visit_TypeAlias(self, node: ast.AST) -> None:
        return

    def _visit_outer_comprehension_iterable(
        self,
        node: ast.ListComp | ast.SetComp | ast.DictComp | ast.GeneratorExp,
    ) -> None:
        if node.generators:
            self.visit(node.generators[0].iter)

    visit_ListComp = _visit_outer_comprehension_iterable
    visit_SetComp = _visit_outer_comprehension_iterable
    visit_DictComp = _visit_outer_comprehension_iterable
    visit_GeneratorExp = _visit_outer_comprehension_iterable


def _track_production_assignments(
    progression: ast.FunctionDef | None,
) -> list[ast.Assign]:
    if progression is None:
        return []
    first_try = next(
        (node for node in progression.body if isinstance(node, ast.Try)),
        None,
    )
    if first_try is None:
        return []
    return [
        statement
        for statement in first_try.body
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and statement.targets[0].id == "resolved"
            and isinstance(statement.value, ast.Call)
            and isinstance(statement.value.func, ast.Name)
            and statement.value.func.id == TRACK_AUTHORITY_OWNER_NAME
            and _ast_digest(statement)
            == TRACK_AUTHORITY_PRODUCTION_ASSIGNMENT_SHA256
        )
    ]


def _track_owner_scope_state(
    progression: ast.FunctionDef | None,
) -> tuple[int, int, set[str], set[str]]:
    if progression is None:
        return 0, 0, set(), set()

    bindings = _TrackOwnerLexicalBindings(TRACK_AUTHORITY_OWNER_NAME)
    parameters = (
        *progression.args.posonlyargs,
        *progression.args.args,
        *progression.args.kwonlyargs,
    )
    if any(item.arg == TRACK_AUTHORITY_OWNER_NAME for item in parameters):
        bindings.reasons.add("parameter")
    if any(
        getattr(item, "name", None) == TRACK_AUTHORITY_OWNER_NAME
        for item in getattr(progression, "type_params", ())
    ):
        bindings.reasons.add("type-parameter")
    if (
        progression.args.vararg is not None
        and progression.args.vararg.arg == TRACK_AUTHORITY_OWNER_NAME
    ):
        bindings.reasons.add("parameter")
    if (
        progression.args.kwarg is not None
        and progression.args.kwarg.arg == TRACK_AUTHORITY_OWNER_NAME
    ):
        bindings.reasons.add("parameter")

    production_assignments = _track_production_assignments(progression)
    approved_assignment = (
        production_assignments[0]
        if len(production_assignments) == 1
        else None
    )
    approved_call = (
        approved_assignment.value
        if approved_assignment is not None
        and isinstance(approved_assignment.value, ast.Call)
        else None
    )
    calls = _TrackOwnerCallCounter(approved_call)
    result_bindings = _TrackOwnerLexicalBindings(
        "resolved",
        approved_assignment=approved_assignment,
    )
    result_parameters = (
        *progression.args.posonlyargs,
        *progression.args.args,
        *progression.args.kwonlyargs,
    )
    if any(item.arg == "resolved" for item in result_parameters):
        result_bindings.reasons.add("parameter")
    if any(
        getattr(item, "name", None) == "resolved"
        for item in getattr(progression, "type_params", ())
    ):
        result_bindings.reasons.add("type-parameter")
    if (
        progression.args.vararg is not None
        and progression.args.vararg.arg == "resolved"
    ):
        result_bindings.reasons.add("parameter")
    if (
        progression.args.kwarg is not None
        and progression.args.kwarg.arg == "resolved"
    ):
        result_bindings.reasons.add("parameter")
    for statement in progression.body:
        bindings.visit(statement)
        calls.visit(statement)
        result_bindings.visit(statement)
    return (
        len(production_assignments),
        calls.count,
        bindings.reasons,
        result_bindings.reasons,
    )


def _dynamic_annotation(node: ast.AST) -> bool:
    forbidden = (
        ast.Call,
        ast.Lambda,
        ast.ListComp,
        ast.SetComp,
        ast.DictComp,
        ast.GeneratorExp,
        ast.NamedExpr,
    )
    return any(isinstance(child, forbidden) for child in ast.walk(node))


def _header_violations(
    path: str,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[Violation]:
    violations = []
    if node.name in {"__getattr__", "__getattribute__", "__dir__"}:
        violations.append(Violation(path, node.name, "MODULE_HOOK_FORBIDDEN", node.name))
    if node.decorator_list:
        violations.append(Violation(path, node.name, "FUNCTION_DECORATOR_FORBIDDEN", ast.unparse(node.decorator_list[0])))
    defaults = [*node.args.defaults, *(item for item in node.args.kw_defaults if item is not None)]
    for default in defaults:
        if not _immutable_literal(default):
            violations.append(Violation(path, node.name, "CALL_DEFAULT_FORBIDDEN", ast.unparse(default)))
    annotations = [
        argument.annotation
        for argument in [
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
            node.args.vararg,
            node.args.kwarg,
        ]
        if argument is not None and argument.annotation is not None
    ]
    if node.returns is not None:
        annotations.append(node.returns)
    for annotation in annotations:
        if _dynamic_annotation(annotation):
            violations.append(Violation(path, node.name, "DYNAMIC_ANNOTATION_FORBIDDEN", ast.unparse(annotation)))
    return violations


def _immutable_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return type(node.value) in {str, bytes, int, float, bool, type(None)}
    if isinstance(node, ast.Tuple):
        return all(_immutable_literal(item) for item in node.elts)
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.UAdd, ast.USub))
        and isinstance(node.operand, ast.Constant)
        and type(node.operand.value) in {int, float}
    ):
        return True
    return False


def _intrinsic_assignment(node: ast.AST, binding: str) -> bool:
    if _immutable_literal(node):
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "frozenset"
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], (ast.Set, ast.Tuple))
        and all(_immutable_literal(item) for item in node.args[0].elts)
    ):
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "re"
        and node.func.attr == "compile"
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], ast.Constant)
        and type(node.args[0].value) is str
    ):
        return True
    if binding == "__all__" and isinstance(node, ast.Tuple):
        return all(isinstance(item, ast.Constant) and type(item.value) is str for item in node.elts)
    return False


def _accepted_exemption_nodes(
    path: str,
    tree: ast.Module,
    registry: dict[str, object],
) -> set[int]:
    try:
        target = _target_record(registry, path)
    except StopIteration:
        return set()
    accepted = set()
    for exemption in target.get("exemptions", []):
        candidates = _exemption_candidates(tree, exemption)
        matches = [node for node in candidates if _ast_digest(node) == exemption.get("astSha256")]
        if len(matches) == 1:
            accepted.add(id(matches[0]))
    return accepted


def _fallback_syntax_violations(path: str, node: ast.Try) -> list[Violation]:
    _, violations = _fallback_pairs_and_violations(
        path,
        ast.Module(body=[node], type_ignores=[]),
    )
    return violations


def _module_load_violations(
    path: str,
    tree: ast.Module,
    profile: str,
    registry: dict[str, object],
) -> list[Violation]:
    schema_violations = _registry_schema_violations(registry)
    if schema_violations:
        return schema_violations
    violations: list[Violation] = []
    if profile != PROFILE_BY_PATH.get(path):
        violations.append(Violation(path, "<module>", "PROFILE_MISMATCH", profile))
    try:
        target = _target_record(registry, path)
    except StopIteration:
        return [*violations, Violation(path, "<module>", "REGISTRY_TARGET_MISSING", path)]

    declared_imports = Counter(
        _import_tuple(record)
        for record in target.get("imports", [])
        if type(record) is dict
    )
    actual_imports = Counter(_physical_imports(tree))
    for item, count in actual_imports.items():
        if item[1] == "*":
            violations.append(Violation(path, "<module>", "STAR_IMPORT_FORBIDDEN", _import_detail(item)))
        if count > declared_imports[item]:
            violations.append(Violation(path, "<module>", "UNREGISTERED_PHYSICAL_IMPORT", _import_detail(item)))
    for item, count in declared_imports.items():
        if count > actual_imports[item]:
            violations.append(Violation(path, "<module>", "REGISTERED_IMPORT_MISSING", _import_detail(item)))

    future_annotations = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "__future__"
        and node.level == 0
        and any(alias.name == "annotations" for alias in node.names)
    ]
    if len(future_annotations) != 1:
        violations.append(Violation(path, "<module>", "FUTURE_ANNOTATIONS_REQUIRED", str(len(future_annotations))))

    exempt = _accepted_exemption_nodes(path, tree, registry)
    declared_names: set[str] = set()

    def claim(binding: str) -> None:
        if binding in declared_names:
            violations.append(Violation(
                path,
                "<module>",
                "MODULE_REBINDING_FORBIDDEN",
                binding,
            ))
        declared_names.add(binding)

    for index, node in enumerate(tree.body):
        if id(node) in exempt:
            if isinstance(node, ast.Assign):
                for target_node in node.targets:
                    if isinstance(target_node, ast.Name):
                        claim(target_node.id)
            elif isinstance(node, ast.ClassDef):
                claim(node.name)
            continue
        if (
            index == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and type(node.value.value) is str
        ):
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for binding in {str(item[2]) for item in _imports_from_statement(node)}:
                claim(binding)
            continue
        if isinstance(node, ast.Try):
            violations.extend(_fallback_syntax_violations(path, node))
            fallback_bindings = {
                str(item[2])
                for statement in [
                    *node.body,
                    *(node.handlers[0].body if node.handlers else []),
                ]
                if isinstance(statement, (ast.Import, ast.ImportFrom))
                for item in _imports_from_statement(statement)
            }
            for binding in fallback_bindings:
                claim(binding)
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            claim(node.name)
            violations.extend(_header_violations(path, node))
            continue
        if isinstance(node, ast.ClassDef):
            claim(node.name)
            violations.extend(_class_violations(path, node))
            continue
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                violations.append(Violation(path, "<module>", "MODULE_ASSIGNMENT_TARGET_FORBIDDEN", ast.unparse(node)))
                continue
            binding = node.targets[0].id
            claim(binding)
            if isinstance(node.value, (ast.List, ast.Dict, ast.Set)):
                violations.append(Violation(path, "<module>", "MUTABLE_MODULE_STATE", binding))
            elif binding in {"frozenset", "re", "dataclass", "builtins"}:
                violations.append(Violation(path, "<module>", "MODULE_ASSIGNMENT_FORBIDDEN", f"{binding}:intrinsic-shadow"))
            elif not _intrinsic_assignment(node.value, binding):
                violations.append(Violation(path, "<module>", "MODULE_ASSIGNMENT_FORBIDDEN", f"{binding}:{type(node.value).__name__}"))
            continue
        if isinstance(node, ast.AnnAssign):
            if not isinstance(node.target, ast.Name):
                violations.append(Violation(path, "<module>", "MODULE_ASSIGNMENT_TARGET_FORBIDDEN", ast.unparse(node.target)))
            else:
                claim(node.target.id)
                if _dynamic_annotation(node.annotation):
                    violations.append(Violation(
                        path,
                        "<module>",
                        "DYNAMIC_ANNOTATION_FORBIDDEN",
                        ast.unparse(node.annotation),
                    ))
                if node.value is not None and not _intrinsic_assignment(node.value, node.target.id):
                    violations.append(Violation(path, "<module>", "MODULE_ASSIGNMENT_FORBIDDEN", node.target.id))
            continue
        if isinstance(node, (ast.AugAssign, ast.Delete, ast.Global, ast.Nonlocal)):
            violations.append(Violation(path, "<module>", "MODULE_NAMESPACE_MUTATION", type(node).__name__))
            continue
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            name = _call_name(node.value.func)
            code = "DYNAMIC_IMPORT_FORBIDDEN" if name in {"__import__", "importlib.import_module"} else "MODULE_LOAD_CALL"
            violations.append(Violation(path, "<module>", code, name))
            continue
        violations.append(Violation(path, "<module>", "MODULE_LOAD_NODE_FORBIDDEN", type(node).__name__))
    return sorted(set(violations))


def _class_violations(path: str, node: ast.ClassDef) -> list[Violation]:
    violations: list[Violation] = []
    dataclass_decorator = (
        len(node.decorator_list) == 1
        and isinstance(node.decorator_list[0], ast.Call)
        and isinstance(node.decorator_list[0].func, ast.Name)
        and node.decorator_list[0].func.id == "dataclass"
        and not node.decorator_list[0].args
        and len(node.decorator_list[0].keywords) == 1
        and node.decorator_list[0].keywords[0].arg == "frozen"
        and isinstance(node.decorator_list[0].keywords[0].value, ast.Constant)
        and node.decorator_list[0].keywords[0].value.value is True
    )
    if node.decorator_list and not dataclass_decorator:
        violations.append(Violation(path, node.name, "CLASS_DECORATOR_FORBIDDEN", ast.unparse(node.decorator_list[0])))
    if node.bases or node.keywords:
        violations.append(Violation(path, node.name, "CLASS_BASE_FORBIDDEN", ast.unparse(node)))
    for index, statement in enumerate(node.body):
        if (
            index == 0
            and isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Constant)
            and type(statement.value.value) is str
        ):
            continue
        if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.value is None:
            if _dynamic_annotation(statement.annotation):
                violations.append(Violation(
                    path,
                    node.name,
                    "DYNAMIC_ANNOTATION_FORBIDDEN",
                    ast.unparse(statement.annotation),
                ))
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            violations.extend(_header_violations(path, statement))
            continue
        violations.append(Violation(path, node.name, "CLASS_BODY_NODE_FORBIDDEN", type(statement).__name__))
    return violations


def _direct_primitive_violations(
    path: str,
    tree: ast.Module,
) -> list[Violation]:
    violations = []
    observed: Counter[tuple[str, str, str, str]] = Counter()
    for function in [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]:
        for call in [node for node in ast.walk(function) if isinstance(node, ast.Call)]:
            name = _call_name(call.func)
            code = None
            if name.rsplit(".", 1)[-1] == "strip":
                code = "IDENTITY_TRIM"
            elif name.rsplit(".", 1)[-1] == "str":
                code = "IDENTITY_COERCION"
            elif name == "json.dumps":
                code = "DUPLICATE_JSON_OWNER"
            elif name.endswith(".sha256") and "hashlib" in name.lower().split("."):
                code = "DUPLICATE_HASH_OWNER"
            elif "catalog" in name.lower():
                code = "CATALOG_DEPENDENCY"
            elif (
                name == "sorted"
                and call.args
                and isinstance(call.args[0], ast.Call)
                and _call_name(call.args[0].func) == "set"
            ):
                code = "IDENTITY_SORT_DEDUPE"
            if code is None:
                continue
            digest = _ast_digest(call)
            identity = (path, function.name, code, digest)
            observed[identity] += 1
            if identity not in FROZEN_V1_DIRECT_PRIMITIVE_EXCEPTIONS:
                violations.append(Violation(path, function.name, code, name))
    for identity, expected_count in FROZEN_V1_DIRECT_PRIMITIVE_EXCEPTIONS.items():
        expected_path, function, code, digest = identity
        if expected_path != path:
            continue
        actual_count = observed[identity]
        if actual_count < expected_count:
            violations.append(Violation(
                path,
                function,
                "FROZEN_V1_EXCEPTION_MISSING",
                f"{code}:{digest}:expected={expected_count}:actual={actual_count}",
            ))
        elif actual_count > expected_count:
            violations.append(Violation(
                path,
                function,
                "FROZEN_V1_EXCEPTION_MULTIMATCH",
                f"{code}:{digest}:expected={expected_count}:actual={actual_count}",
            ))
    return sorted(set(violations))


class _DeletedNameScanner(ast.NodeVisitor):
    def __init__(self, path: str) -> None:
        self.path = path
        self.function = "<module>"
        self.violations: list[Violation] = []

    def _record(self, name: str, code: str) -> None:
        if name in DELETED_PUBLIC_NAMES:
            self.violations.append(Violation(self.path, self.function, code, name))

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record(node.name, "DELETED_DEFINITION")
        previous = self.function
        self.function = node.name
        self.generic_visit(node)
        self.function = previous

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Name(self, node: ast.Name) -> None:
        self._record(node.id, "DELETED_REFERENCE")

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._record(node.attr, "DELETED_REFERENCE")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            self._record(alias.name, "DELETED_IMPORT")
            self._record(alias.asname or "", "DELETED_IMPORT")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.name, "DELETED_IMPORT")
            self._record(alias.asname or "", "DELETED_IMPORT")

    def visit_Assign(self, node: ast.Assign) -> None:
        if any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets):
            try:
                values = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                values = ()
            for value in values if type(values) in {tuple, list, set} else ():
                if type(value) is str:
                    self._record(value, "DELETED_EXPORT")
        self.generic_visit(node)


def _deleted_name_violations(
    trees: dict[str, ast.Module],
) -> list[Violation]:
    violations = []
    for path, tree in trees.items():
        scanner = _DeletedNameScanner(path)
        scanner.visit(tree)
        violations.extend(scanner.violations)
    return sorted(set(violations))


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    result = ast.unparse(node.args)
    if node.returns is not None:
        result += f" -> {ast.unparse(node.returns)}"
    return result


def _string_collection(node: ast.AST) -> set[str] | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "frozenset"
        and len(node.args) == 1
        and not node.keywords
    ):
        return _string_collection(node.args[0])
    if not isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return None
    values = set()
    for item in node.elts:
        if not isinstance(item, ast.Constant) or type(item.value) is not str:
            return None
        values.add(item.value)
    return values


def _ownership_violations(
    trees: dict[str, ast.Module],
    registry: dict[str, object],
) -> list[Violation]:
    violations = []
    for (path, function), expected in SEALED_SIGNATURES.items():
        tree = trees.get(path)
        definitions = {
            node.name: node
            for node in (tree.body if tree is not None else [])
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        node = definitions.get(function)
        if node is None or _signature(node) != expected:
            violations.append(Violation(path, function, "SEALED_SIGNATURE_MISMATCH", _signature(node) if node is not None else "<missing>"))

    for path, tree in trees.items():
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            values = _string_collection(node.value)
            if values is not None and len(values.intersection(CANONICAL_GEAR_SLOTS)) >= 3:
                violations.append(Violation(path, "<module>", "DUPLICATE_SLOT_MEMBERSHIP", ",".join(sorted(values.intersection(CANONICAL_GEAR_SLOTS)))))

    authority = trees.get("server/gear_exact_authority.py")
    if authority is not None:
        progression = next(
            (
                node for node in authority.body
                if isinstance(node, ast.FunctionDef)
                and node.name == "seal_exact_progression"
            ),
            None,
        )
        calls = {
            _call_name(node.func)
            for node in ast.walk(progression) if isinstance(node, ast.Call)
        } if progression is not None else set()
        if "canonical_slot" not in calls:
            violations.append(Violation("server/gear_exact_authority.py", "seal_exact_progression", "MISSING_PRODUCTION_OWNER_CALL", "canonical_slot"))
        (
            production_call_count,
            extra_call_count,
            track_scope_bindings,
            result_scope_bindings,
        ) = _track_owner_scope_state(progression)
        if production_call_count != 1 or extra_call_count != 0:
            violations.append(Violation(
                "server/gear_exact_authority.py",
                "seal_exact_progression",
                "TRACK_AUTHORITY_CALL_INVALID",
                (
                    f"expected_production=1,actual={production_call_count};"
                    f"expected_extra=0,actual={extra_call_count}"
                ),
            ))
            if production_call_count == 0:
                violations.append(Violation(
                    "server/gear_exact_authority.py",
                    "seal_exact_progression",
                    "MISSING_PRODUCTION_OWNER_CALL",
                    TRACK_AUTHORITY_OWNER_NAME,
                ))
        if extra_call_count:
            violations.append(Violation(
                "server/gear_exact_authority.py",
                "seal_exact_progression",
                "TRACK_AUTHORITY_EXTRA_CALL_INVALID",
                f"expected=0,actual={extra_call_count}",
            ))
        if track_scope_bindings:
            violations.append(Violation(
                "server/gear_exact_authority.py",
                "seal_exact_progression",
                "TRACK_AUTHORITY_SCOPE_SHADOWED",
                ",".join(sorted(track_scope_bindings)),
            ))
        if result_scope_bindings:
            violations.append(Violation(
                "server/gear_exact_authority.py",
                "seal_exact_progression",
                "TRACK_AUTHORITY_RESULT_BINDING_INVALID",
                ",".join(sorted(result_scope_bindings)),
            ))
        physical = Counter(_physical_imports(authority))
        module_bindings = _module_import_bindings(
            "server/gear_exact_authority.py",
            authority,
        )
        target = _target_record(registry, "server/gear_exact_authority.py")
        registered_imports = Counter(
            _import_tuple(record) for record in target["imports"]
        )
        registered_pairs = Counter(
            (
                _import_tuple(pair["relative"]),
                _import_tuple(pair["absolute"]),
            )
            for pair in target["importFallbackPairs"]
        )
        expected_pair = (
            TRACK_AUTHORITY_RELATIVE_IMPORT,
            TRACK_AUTHORITY_ABSOLUTE_IMPORT,
        )
        provenance_valid = (
            physical[TRACK_AUTHORITY_RELATIVE_IMPORT] == 1
            and physical[TRACK_AUTHORITY_ABSOLUTE_IMPORT] == 1
            and TRACK_AUTHORITY_RELATIVE_IMPORT in module_bindings
            and TRACK_AUTHORITY_ABSOLUTE_IMPORT in module_bindings
            and registered_imports[TRACK_AUTHORITY_RELATIVE_IMPORT] == 1
            and registered_imports[TRACK_AUTHORITY_ABSOLUTE_IMPORT] == 1
            and registered_pairs[expected_pair] == 1
            and production_call_count == 1
            and extra_call_count == 0
            and not track_scope_bindings
            and not result_scope_bindings
        )
        if not provenance_valid:
            violations.append(Violation(
                "server/gear_exact_authority.py",
                "seal_exact_progression",
                "TRACK_AUTHORITY_PROVENANCE_INVALID",
                "gear_track_authority.resolve_exact_instance_progression",
            ))
    return sorted(set(violations))


def _source_change_control_violations(
    target_trees: dict[str, ast.Module],
    repository_trees: dict[str, ast.Module],
    registry: dict[str, object],
) -> list[Violation]:
    violations = _registry_violations(registry, target_trees)
    if any(item.code.startswith("REGISTRY_SCHEMA_") for item in violations):
        return sorted(set(violations))
    for path in TARGETS:
        violations.extend(_module_load_violations(
            path,
            target_trees[path],
            PROFILE_BY_PATH[path],
            registry,
        ))
        violations.extend(_direct_primitive_violations(path, target_trees[path]))
    violations.extend(_ownership_violations(target_trees, registry))
    violations.extend(_deleted_name_violations(repository_trees))
    return sorted(set(violations))


def _codes(violations: list[Violation]) -> set[str]:
    return {item.code for item in violations}


def _tree_with(path: str, source: str) -> ast.Module:
    current = (ROOT / path).read_text(encoding="utf-8")
    return ast.parse(current + "\n" + source + "\n", filename=path)


def _target_record(
    registry: dict[str, object],
    path: str,
) -> dict[str, object]:
    return next(
        target
        for target in registry["targets"]
        if target["path"] == path
    )


class GearCanonicalOwnerGateTest(unittest.TestCase):
    def assertModuleCode(
        self,
        path: str,
        source: str,
        code: str,
    ) -> list[Violation]:
        violations = _module_load_violations(
            path,
            _tree_with(path, source),
            PROFILE_BY_PATH[path],
            REGISTRY,
        )
        self.assertIn(code, _codes(violations), _formatted(violations))
        return violations

    def test_real_registry_and_five_profiles_are_clean(self):
        repository_trees = _repository_python_trees()
        violations = _source_change_control_violations(
            TREES,
            repository_trees,
            REGISTRY,
        )
        self.assertEqual([], violations, _formatted(violations))

    def test_module_load_helper_is_rejected_for_every_target_with_exact_finding(self):
        for path in sorted(TARGETS):
            with self.subTest(path=path):
                violations = _module_load_violations(
                    path,
                    _tree_with(
                        path,
                        "from server.hidden_owner import mutate\nmutate()",
                    ),
                    PROFILE_BY_PATH[path],
                    REGISTRY,
                )
                observed = {
                    (item.path, item.code, item.detail)
                    for item in violations
                }
                self.assertIn(
                    (
                        path,
                        "UNREGISTERED_PHYSICAL_IMPORT",
                        "server.hidden_owner:mutate as mutate",
                    ),
                    observed,
                    _formatted(violations),
                )
                self.assertIn(
                    (path, "MODULE_LOAD_CALL", "mutate"),
                    observed,
                    _formatted(violations),
                )

    def test_registry_contract_and_positive_controls_are_explicit(self):
        self.assertEqual(1, REGISTRY["schemaVersion"])
        self.assertEqual("source_change_control_only", REGISTRY["proofClaim"])
        self.assertEqual(
            "python_ast_dump_v1",
            REGISTRY["digestSerialization"],
        )
        self.assertEqual(
            TARGETS,
            {target["path"] for target in REGISTRY["targets"]},
        )
        observed_exemptions = {
            (
                target["path"],
                exemption["id"],
                exemption["role"],
                exemption["binding"],
                exemption["nodeKind"],
            )
            for target in REGISTRY["targets"]
            for exemption in target["exemptions"]
        }
        self.assertEqual(EXEMPTION_UNIVERSE, observed_exemptions)
        accepted_count = sum(
            len(_accepted_exemption_nodes(
                target["path"],
                TREES[target["path"]],
                REGISTRY,
            ))
            for target in REGISTRY["targets"]
        )
        self.assertEqual(9, accepted_count)
        support_tree = TREES["server/simc_item_effect_support.py"]
        frozen_dataclasses = [
            node.name
            for node in support_tree.body
            if isinstance(node, ast.ClassDef)
            and not _class_violations(
                "server/simc_item_effect_support.py",
                node,
            )
        ]
        self.assertEqual(
            ["EffectSubject", "EffectSupportOutcome"],
            frozen_dataclasses,
        )
        authority = _target_record(
            REGISTRY,
            "server/gear_exact_authority.py",
        )
        self.assertEqual(
            [{
                "export": "seal_exact_static_facts",
                "module": ".gear_exact_item_instance",
                "symbol": "seal_exact_static_facts",
                "alias": "seal_exact_static_facts",
            }],
            authority["reexports"],
        )
        self.assertEqual([], _registry_violations(REGISTRY, TREES))

    def test_registry_hygiene_fails_closed(self):
        cases: list[tuple[str, dict[str, object], dict[str, ast.Module], str]] = []

        changed = copy.deepcopy(REGISTRY)
        changed["proofClaim"] = "python_semantics_proof"
        cases.append(("proof claim", changed, TREES, "PROOF_CLAIM_INVALID"))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"].append(copy.deepcopy(changed["targets"][0]))
        cases.append(("duplicate target", changed, TREES, "DUPLICATE_TARGET"))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"].pop()
        cases.append(("target omission", changed, TREES, "TARGET_UNIVERSE_MISMATCH"))

        changed = copy.deepcopy(REGISTRY)
        target = changed["targets"][0]
        target["imports"].append(copy.deepcopy(target["imports"][0]))
        cases.append(("duplicate import", changed, TREES, "DUPLICATE_IMPORT_RECORD"))

        changed = copy.deepcopy(REGISTRY)
        target = next(item for item in changed["targets"] if item["exemptions"])
        target["exemptions"].append(copy.deepcopy(target["exemptions"][0]))
        cases.append(("duplicate exemption", changed, TREES, "DUPLICATE_EXEMPTION"))

        changed = copy.deepcopy(REGISTRY)
        target = next(item for item in changed["targets"] if item["exemptions"])
        target["exemptions"].pop()
        cases.append(("omitted exemption", changed, TREES, "EXEMPTION_UNIVERSE_MISMATCH"))

        changed = copy.deepcopy(REGISTRY)
        target = next(item for item in changed["targets"] if item["exemptions"])
        target["exemptions"][0]["id"] = "*"
        cases.append(("wildcard exemption", changed, TREES, "EXEMPTION_UNIVERSE_MISMATCH"))

        changed = copy.deepcopy(REGISTRY)
        target = next(item for item in changed["targets"] if item["exemptions"])
        target["exemptions"][0]["astSha256"] = "0" * 64
        cases.append(("digest mismatch", changed, TREES, "EXEMPTION_DIGEST_MISMATCH"))

        changed = copy.deepcopy(REGISTRY)
        target = next(item for item in changed["targets"] if item["exemptions"])
        target["exemptions"][0]["nodeKind"] = "Expr"
        cases.append(("kind changed", changed, TREES, "EXEMPTION_UNIVERSE_MISMATCH"))

        changed = copy.deepcopy(REGISTRY)
        item = _target_record(changed, "server/gear_exact_item_instance.py")
        item["publicCallables"].pop()
        cases.append(("public callable omitted", changed, TREES, "PUBLIC_CALLABLE_MISMATCH"))

        changed = copy.deepcopy(REGISTRY)
        authority = _target_record(changed, "server/gear_exact_authority.py")
        authority["exports"].pop()
        cases.append(("export omitted", changed, TREES, "EXPORT_MISMATCH"))

        changed = copy.deepcopy(REGISTRY)
        authority = _target_record(changed, "server/gear_exact_authority.py")
        authority["reexports"] = []
        cases.append(("reexport omitted", changed, TREES, "REEXPORT_MISMATCH"))

        changed = copy.deepcopy(REGISTRY)
        target = next(
            item for item in changed["targets"] if item["sealedEntrypoints"]
        )
        target["sealedEntrypoints"].pop()
        cases.append((
            "sealed entrypoint omitted",
            changed,
            TREES,
            "SEALED_ENTRYPOINT_MISMATCH",
        ))

        changed = copy.deepcopy(REGISTRY)
        target = next(
            item
            for item in changed["targets"]
            if item["importFallbackPairs"]
        )
        target["importFallbackPairs"][0]["absolute"]["alias"] = "changed"
        cases.append(("fallback mismatch", changed, TREES, "FALLBACK_PAIR_INVALID"))

        for label, registry, trees, expected in cases:
            with self.subTest(label=label):
                self.assertIn(
                    expected,
                    _codes(_registry_violations(registry, trees)),
                    _formatted(_registry_violations(registry, trees)),
                )

    def test_malformed_registry_values_fail_closed_without_exceptions(self):
        cases: list[tuple[str, dict[str, object], str]] = []

        changed = copy.deepcopy(REGISTRY)
        changed["targets"].append("not-a-target-record")
        cases.append(("target record", changed, "REGISTRY_SCHEMA_TARGET_INVALID"))

        for field, expected in (
            ("publicCallables", "REGISTRY_SCHEMA_NAME_INVALID"),
            ("exports", "REGISTRY_SCHEMA_NAME_INVALID"),
            ("sealedEntrypoints", "REGISTRY_SCHEMA_NAME_INVALID"),
        ):
            changed = copy.deepcopy(REGISTRY)
            changed["targets"][0][field].append([])
            cases.append((field, changed, expected))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["imports"][0]["symbol"] = []
        cases.append(("import symbol", changed, "REGISTRY_SCHEMA_IMPORT_INVALID"))

        for label, registry, expected in cases:
            with self.subTest(label=label):
                violations = _registry_violations(registry, TREES)
                self.assertIn(expected, _codes(violations), _formatted(violations))

    def test_aggregate_malformed_registry_schema_is_controlled_and_stops(self):
        cases: list[tuple[str, dict[str, object]]] = []

        changed = copy.deepcopy(REGISTRY)
        changed.pop("schemaVersion")
        cases.append(("root missing", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["extra"] = True
        cases.append(("root extra", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0].pop("profile")
        cases.append(("target missing", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["extra"] = True
        cases.append(("target extra", changed))

        for field in (
            "imports",
            "importFallbackPairs",
            "publicCallables",
            "exports",
            "reexports",
            "sealedEntrypoints",
            "exemptions",
        ):
            changed = copy.deepcopy(REGISTRY)
            changed["targets"][0][field] = None
            cases.append((f"{field}=None", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["imports"][0].pop("alias")
        cases.append(("nested import missing", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["imports"].append(None)
        cases.append(("nested import None", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["imports"][0]["extra"] = True
        cases.append(("nested import extra", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["importFallbackPairs"].append(None)
        cases.append(("nested fallback None", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["importFallbackPairs"][0].pop("absolute")
        cases.append(("nested fallback missing", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["importFallbackPairs"][0]["extra"] = True
        cases.append(("nested fallback extra", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["importFallbackPairs"][0]["relative"] = None
        cases.append(("nested fallback import None", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["reexports"].append({
            "export": "Ghost",
            "module": "server.ghost",
            "symbol": "Ghost",
            "alias": "Ghost",
            "extra": True,
        })
        cases.append(("nested reexport extra", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["reexports"].append(None)
        cases.append(("nested reexport None", changed))

        changed = copy.deepcopy(REGISTRY)
        exemption_target = next(
            target for target in changed["targets"] if target["exemptions"]
        )
        exemption_target["exemptions"].append(None)
        cases.append(("nested exemption None", changed))

        changed = copy.deepcopy(REGISTRY)
        exemption_target = next(
            target for target in changed["targets"] if target["exemptions"]
        )
        exemption_target["exemptions"][0].pop("owner")
        cases.append(("nested exemption missing", changed))

        changed = copy.deepcopy(REGISTRY)
        exemption_target = next(
            target for target in changed["targets"] if target["exemptions"]
        )
        exemption_target["exemptions"][0]["extra"] = True
        cases.append(("nested exemption extra", changed))

        changed = copy.deepcopy(REGISTRY)
        exemption_target = next(
            target for target in changed["targets"] if target["exemptions"]
        )
        exemption_target["exemptions"][0]["binding"] = []
        cases.append(("nested exemption field type", changed))

        changed = copy.deepcopy(REGISTRY)
        changed["digestSerialization"] = None
        cases.append(("digest serialization type", changed))

        repository_trees = _repository_python_trees()
        for label, registry in cases:
            with self.subTest(label=label):
                try:
                    violations = _source_change_control_violations(
                        TREES,
                        repository_trees,
                        registry,
                    )
                except Exception as error:  # controlled failure is the contract
                    self.fail(f"registry schema raised {type(error).__name__}: {error}")
                schema = [
                    item for item in violations
                    if item.code.startswith("REGISTRY_SCHEMA_")
                ]
                self.assertTrue(schema, _formatted(violations))
                self.assertFalse(any(
                    item.code in {
                        "REGISTERED_IMPORT_MISSING",
                        "REGISTRY_TARGET_MISSING",
                    }
                    for item in violations
                ), _formatted(violations))

    def test_fallback_requires_a_bidirectional_exact_mirror(self):
        path = "server/gear_exact_item_instance.py"

        trees = copy.deepcopy(TREES)
        registry = copy.deepcopy(REGISTRY)
        fallback = next(node for node in trees[path].body if isinstance(node, ast.Try))
        fallback.body.append(ast.ImportFrom(
            module="extra_owner",
            names=[ast.alias(name="Extra", asname=None)],
            level=1,
        ))
        _target_record(registry, path)["imports"].append({
            "module": ".extra_owner",
            "symbol": "Extra",
            "alias": "Extra",
        })
        violations = _registry_violations(registry, trees)
        self.assertIn(
            "FALLBACK_MIRROR_INVALID",
            _codes(violations),
            _formatted(violations),
        )

        structural_cases = []
        trees = copy.deepcopy(TREES)
        fallback = next(node for node in trees[path].body if isinstance(node, ast.Try))
        fallback.body.append(copy.deepcopy(fallback.body[0]))
        structural_cases.append(("duplicate", trees, "FALLBACK_MIRROR_INVALID"))

        trees = copy.deepcopy(TREES)
        fallback = next(node for node in trees[path].body if isinstance(node, ast.Try))
        fallback.body.append(ast.Expr(value=ast.Constant(value="not an import")))
        structural_cases.append(("non-import", trees, "FALLBACK_STRUCTURE_INVALID"))

        trees = copy.deepcopy(TREES)
        fallback = next(node for node in trees[path].body if isinstance(node, ast.Try))
        fallback.orelse = [ast.Pass()]
        structural_cases.append(("else", trees, "FALLBACK_STRUCTURE_INVALID"))

        trees = copy.deepcopy(TREES)
        fallback = next(node for node in trees[path].body if isinstance(node, ast.Try))
        fallback.finalbody = [ast.Pass()]
        structural_cases.append(("finally", trees, "FALLBACK_STRUCTURE_INVALID"))

        for label, trees, expected in structural_cases:
            with self.subTest(label=label):
                violations = _registry_violations(REGISTRY, trees)
                self.assertIn(expected, _codes(violations), _formatted(violations))

        trees = copy.deepcopy(TREES)
        registry = copy.deepcopy(REGISTRY)
        fallback = next(node for node in trees[path].body if isinstance(node, ast.Try))
        removed = fallback.handlers[0].body[0].names.pop()
        target = _target_record(registry, path)
        target["imports"] = [
            item for item in target["imports"]
            if not (
                item["module"] == "gear_canonical_kernel"
                and item["symbol"] == removed.name
                and item["alias"] == (removed.asname or removed.name)
            )
        ]
        target["importFallbackPairs"] = [
            pair for pair in target["importFallbackPairs"]
            if pair["absolute"]["symbol"] != removed.name
        ]
        violations = _registry_violations(registry, trees)
        self.assertIn(
            "FALLBACK_MIRROR_INVALID",
            _codes(violations),
            _formatted(violations),
        )

    def test_reexports_require_a_real_module_binding_and_defined_exports(self):
        path = "server/gear_exact_authority.py"
        trees = copy.deepcopy(TREES)
        registry = copy.deepcopy(REGISTRY)
        tree = trees[path]
        function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_blocked_progression"
        )
        function.body.insert(0, ast.ImportFrom(
            module="gear_canonical_kernel",
            names=[ast.alias(name="CanonicalIssue", asname="Ghost")],
            level=1,
        ))
        all_assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            )
        )
        all_assignment.value.elts.append(ast.Constant(value="Ghost"))
        target = _target_record(registry, path)
        target["imports"].append({
            "module": ".gear_canonical_kernel",
            "symbol": "CanonicalIssue",
            "alias": "Ghost",
        })
        target["exports"].append("Ghost")
        target["reexports"].append({
            "export": "Ghost",
            "module": ".gear_canonical_kernel",
            "symbol": "CanonicalIssue",
            "alias": "Ghost",
        })
        violations = _source_change_control_violations(
            trees,
            _repository_python_trees(),
            registry,
        )
        self.assertIn(
            "REEXPORT_MODULE_BINDING_REQUIRED",
            _codes(violations),
            _formatted(violations),
        )

        trees = copy.deepcopy(TREES)
        registry = copy.deepcopy(REGISTRY)
        tree = trees[path]
        all_assignment = next(
            node for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            )
        )
        all_assignment.value.elts.append(ast.Constant(value="Ghost"))
        _target_record(registry, path)["exports"].append("Ghost")
        violations = _registry_violations(registry, trees)
        self.assertIn(
            "UNDEFINED_EXPORT",
            _codes(violations),
            _formatted(violations),
        )

        path = "scripts/simc-item-effect-probe.py"
        trees = copy.deepcopy(TREES)
        registry = copy.deepcopy(REGISTRY)
        trees[path].body.append(ast.Assign(
            targets=[ast.Name(id="__all__", ctx=ast.Store())],
            value=ast.Tuple(elts=[ast.Constant(value="Path")], ctx=ast.Load()),
        ))
        target = _target_record(registry, path)
        target["exports"] = ["Path"]
        target["reexports"] = [{
            "export": "Path",
            "module": "pathlib",
            "symbol": "Path",
            "alias": "Path",
        }]
        self.assertEqual(
            [],
            _registry_violations(registry, trees),
            _formatted(_registry_violations(registry, trees)),
        )

        self.assertEqual(
            [],
            _registry_violations(REGISTRY, TREES),
            "real fallback re-export must remain valid",
        )

    def test_frozen_v1_direct_primitive_exceptions_have_exact_cardinality(self):
        path = "server/gear_exact_item_instance.py"
        tree = copy.deepcopy(TREES[path])
        legacy_hash = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_hash"
        )
        sha256_call = next(
            node for node in ast.walk(legacy_hash)
            if isinstance(node, ast.Call)
            and _call_name(node.func) == "hashlib.sha256"
        )
        legacy_hash.body.insert(0, ast.Expr(value=copy.deepcopy(sha256_call)))
        violations = _direct_primitive_violations(path, tree)
        self.assertIn(
            "FROZEN_V1_EXCEPTION_MULTIMATCH",
            _codes(violations),
            _formatted(violations),
        )

        tree = copy.deepcopy(TREES[path])
        canonical_bytes = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "_canonical_bytes"
        )
        json_call = next(
            node for node in ast.walk(canonical_bytes)
            if isinstance(node, ast.Call) and _call_name(node.func) == "json.dumps"
        )
        json_call.func = ast.Name(id="legacy_json", ctx=ast.Load())
        violations = _direct_primitive_violations(path, tree)
        self.assertIn(
            "FROZEN_V1_EXCEPTION_MISSING",
            _codes(violations),
            _formatted(violations),
        )

    def test_track_authority_provenance_is_hard_coded_not_registry_authorized(self):
        path = "server/gear_exact_authority.py"
        repository_trees = _repository_python_trees()
        trees = copy.deepcopy(TREES)
        registry = copy.deepcopy(REGISTRY)
        tree = trees[path]
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module == "gear_track_authority":
                node.module = "hidden_track_authority"
        target = _target_record(registry, path)
        for record in target["imports"]:
            if str(record["module"]).lstrip(".") == "gear_track_authority":
                prefix = "." if str(record["module"]).startswith(".") else ""
                record["module"] = prefix + "hidden_track_authority"
        for pair in target["importFallbackPairs"]:
            if str(pair["relative"]["module"]).lstrip(".") == "gear_track_authority":
                pair["relative"]["module"] = ".hidden_track_authority"
                pair["absolute"]["module"] = "hidden_track_authority"
        violations = _source_change_control_violations(
            trees,
            repository_trees,
            registry,
        )
        self.assertIn(
            "TRACK_AUTHORITY_PROVENANCE_INVALID",
            _codes(violations),
            _formatted(violations),
        )

        cases: list[tuple[str, dict[str, ast.Module], dict[str, object]]] = []
        for label, level in (("missing relative", 1), ("missing absolute", 0)):
            case_trees = copy.deepcopy(TREES)
            case_registry = copy.deepcopy(REGISTRY)
            for node in ast.walk(case_trees[path]):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "gear_track_authority"
                    and node.level == level
                ):
                    node.names = []
            cases.append((label, case_trees, case_registry))

        case_trees = copy.deepcopy(TREES)
        case_registry = copy.deepcopy(REGISTRY)
        for node in ast.walk(case_trees[path]):
            if isinstance(node, ast.ImportFrom) and node.module == "gear_track_authority":
                node.names[0].asname = "hidden_progression"
        case_target = _target_record(case_registry, path)
        for record in case_target["imports"]:
            if str(record["module"]).lstrip(".") == "gear_track_authority":
                record["alias"] = "hidden_progression"
        for pair in case_target["importFallbackPairs"]:
            if str(pair["relative"]["module"]).lstrip(".") == "gear_track_authority":
                pair["relative"]["alias"] = "hidden_progression"
                pair["absolute"]["alias"] = "hidden_progression"
        cases.append(("alias variation", case_trees, case_registry))

        for label, case_trees, case_registry in cases:
            with self.subTest(label=label):
                violations = _source_change_control_violations(
                    case_trees,
                    repository_trees,
                    case_registry,
                )
                self.assertIn(
                    "TRACK_AUTHORITY_PROVENANCE_INVALID",
                    _codes(violations),
                    _formatted(violations),
                )

    def test_track_authority_call_has_one_unshadowed_bare_name_in_owner_scope(self):
        path = "server/gear_exact_authority.py"
        owner_name = "resolve_exact_instance_progression"

        def mutation() -> tuple[dict[str, ast.Module], dict[str, object], ast.FunctionDef]:
            trees = copy.deepcopy(TREES)
            registry = copy.deepcopy(REGISTRY)
            progression = next(
                node for node in trees[path].body
                if isinstance(node, ast.FunctionDef)
                and node.name == "seal_exact_progression"
            )
            return trees, registry, progression

        scope_sources = {
            "lambda assignment": f"{owner_name} = lambda *args: {{}}",
            "local def": f"def {owner_name}(*args):\n    return {{}}",
            "assign": f"{owner_name} = hidden_owner",
            "annassign": f"{owner_name}: object",
            "augassign": f"{owner_name} += hidden_owner",
            "named expression": f"if ({owner_name} := hidden_owner):\n    pass",
            "destructuring": f"({owner_name}, other) = pair",
            "for": f"for {owner_name} in owners:\n    pass",
            "with": f"with manager as {owner_name}:\n    pass",
            "except": f"try:\n    pass\nexcept Exception as {owner_name}:\n    pass",
            "match": f"match value:\n    case {{'owner': {owner_name}}}:\n        pass",
            "local class": f"class {owner_name}:\n    pass",
            "delete": f"del {owner_name}",
            "global": f"global {owner_name}",
            "nonlocal": f"nonlocal {owner_name}",
            "comprehension named expression": (
                f"items = [({owner_name} := value) for value in values]"
            ),
        }
        if getattr(ast, "TypeAlias", None) is not None:
            scope_sources["type alias"] = f"type {owner_name} = int"
        for label, source in scope_sources.items():
            with self.subTest(label=label):
                trees, registry, progression = mutation()
                progression.body[0:0] = ast.parse(source).body
                violations = _ownership_violations(trees, registry)
                self.assertIn(
                    "TRACK_AUTHORITY_SCOPE_SHADOWED",
                    _codes(violations),
                    _formatted(violations),
                )

        parameter_mutations = {
            "posonly": lambda args: args.posonlyargs.append(ast.arg(arg=owner_name)),
            "positional": lambda args: args.args.append(ast.arg(arg=owner_name)),
            "kwonly": lambda args: (
                args.kwonlyargs.append(ast.arg(arg=owner_name)),
                args.kw_defaults.append(None),
            ),
            "vararg": lambda args: setattr(args, "vararg", ast.arg(arg=owner_name)),
            "kwarg": lambda args: setattr(args, "kwarg", ast.arg(arg=owner_name)),
        }
        for label, mutate_args in parameter_mutations.items():
            with self.subTest(label=label):
                trees, registry, progression = mutation()
                mutate_args(progression.args)
                violations = _ownership_violations(trees, registry)
                self.assertIn(
                    "TRACK_AUTHORITY_SCOPE_SHADOWED",
                    _codes(violations),
                    _formatted(violations),
                )

        type_parameter_cases = []
        for label, attribute in (
            ("typevar", "TypeVar"),
            ("typevartuple", "TypeVarTuple"),
            ("paramspec", "ParamSpec"),
        ):
            constructor = getattr(ast, attribute, None)
            if constructor is not None:
                type_parameter_cases.append((label, constructor(name=owner_name)))
        for label, type_parameter in type_parameter_cases:
            with self.subTest(label=label):
                trees, registry, progression = mutation()
                getattr(progression, "type_params").append(type_parameter)
                violations = _ownership_violations(trees, registry)
                self.assertIn(
                    "TRACK_AUTHORITY_SCOPE_SHADOWED",
                    _codes(violations),
                    _formatted(violations),
                )

        with self.subTest(label="function-local hidden import"):
            trees, registry, progression = mutation()
            progression.body.insert(0, ast.ImportFrom(
                module="hidden_track_authority",
                names=[ast.alias(name=owner_name, asname=None)],
                level=0,
            ))
            _target_record(registry, path)["imports"].append({
                "module": "hidden_track_authority",
                "symbol": owner_name,
                "alias": owner_name,
            })
            violations = _ownership_violations(trees, registry)
            self.assertIn(
                "TRACK_AUTHORITY_SCOPE_SHADOWED",
                _codes(violations),
                _formatted(violations),
            )

        for label, replacement in (
            (
                "attribute call",
                ast.Attribute(
                    value=ast.Name(id="hidden", ctx=ast.Load()),
                    attr=owner_name,
                    ctx=ast.Load(),
                ),
            ),
            (
                "subscript call",
                ast.Subscript(
                    value=ast.Name(id="owners", ctx=ast.Load()),
                    slice=ast.Constant(value=owner_name),
                    ctx=ast.Load(),
                ),
            ),
            ("alias call", ast.Name(id="owner_alias", ctx=ast.Load())),
        ):
            with self.subTest(label=label):
                trees, registry, progression = mutation()
                call = next(
                    node for node in ast.walk(progression)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == owner_name
                )
                call.func = replacement
                violations = _ownership_violations(trees, registry)
                self.assertIn(
                    "TRACK_AUTHORITY_CALL_INVALID",
                    _codes(violations),
                    _formatted(violations),
                )

        with self.subTest(label="duplicate bare call"):
            trees, registry, progression = mutation()
            progression.body.insert(0, ast.Expr(value=ast.Call(
                func=ast.Name(id=owner_name, ctx=ast.Load()),
                args=[],
                keywords=[],
            )))
            violations = _ownership_violations(trees, registry)
            self.assertIn(
                "TRACK_AUTHORITY_CALL_INVALID",
                _codes(violations),
                _formatted(violations),
            )

        for label, source in (
            (
                "nested function parameter",
                f"def nested({owner_name}):\n    return {owner_name}",
            ),
            (
                "comprehension target",
                f"items = [{owner_name} for {owner_name} in owners]",
            ),
        ):
            with self.subTest(label=label):
                trees, registry, progression = mutation()
                progression.body[0:0] = ast.parse(source).body
                violations = _ownership_violations(trees, registry)
                self.assertNotIn(
                    "TRACK_AUTHORITY_SCOPE_SHADOWED",
                    _codes(violations),
                    _formatted(violations),
                )

    def test_track_authority_call_counts_definition_time_outer_evaluation_only(self):
        path = "server/gear_exact_authority.py"
        owner_name = "resolve_exact_instance_progression"

        def mutation(source: str) -> tuple[dict[str, ast.Module], dict[str, object]]:
            trees = copy.deepcopy(TREES)
            registry = copy.deepcopy(REGISTRY)
            progression = next(
                node for node in trees[path].body
                if isinstance(node, ast.FunctionDef)
                and node.name == "seal_exact_progression"
            )
            progression.body[0:0] = ast.parse(source).body
            return trees, registry

        definition_time_sources = {
            "lambda default": f"handler = lambda value={owner_name}(): value",
            "nested positional default": f"def nested(value={owner_name}()):\n    pass",
            "nested keyword default": f"def nested(*, value={owner_name}()):\n    pass",
            "nested multilayer default": (
                f"def nested(value=(lambda inner={owner_name}(): inner)):\n    pass"
            ),
            "function decorator": f"@{owner_name}()\ndef nested():\n    pass",
            "async function default": f"async def nested(value={owner_name}()):\n    pass",
            "async function decorator": f"@{owner_name}()\nasync def nested():\n    pass",
            "class base": f"class Nested({owner_name}()):\n    pass",
            "class metaclass": f"class Nested(metaclass={owner_name}()):\n    pass",
            "class keyword": f"class Nested(flag={owner_name}()):\n    pass",
            "class decorator": f"@{owner_name}()\nclass Nested:\n    pass",
            "class body descriptor": f"class Nested:\n    field = {owner_name}()",
            "class method default": (
                f"class Nested:\n    def method(self, value={owner_name}()):\n        pass"
            ),
            "class method decorator": (
                f"class Nested:\n    @{owner_name}()\n    def method(self):\n        pass"
            ),
            "nested class body": (
                f"class Outer:\n    class Inner({owner_name}()):\n        pass"
            ),
            "list comprehension outer iterable": (
                f"items = [value for value in {owner_name}()]"
            ),
            "set comprehension outer iterable": (
                f"items = {{value for value in {owner_name}()}}"
            ),
            "dict comprehension outer iterable": (
                f"items = {{value: value for value in {owner_name}()}}"
            ),
            "generator outer iterable": (
                f"items = (value for value in {owner_name}())"
            ),
            "class comprehension outer iterable": (
                f"class Nested:\n    items = [value for value in {owner_name}()]"
            ),
        }
        for label, source in definition_time_sources.items():
            with self.subTest(label=label):
                trees, registry = mutation(source)
                violations = _ownership_violations(trees, registry)
                self.assertIn(
                    "TRACK_AUTHORITY_CALL_INVALID",
                    _codes(violations),
                    _formatted(violations),
                )

        nested_scope_sources = {
            "nested function body": f"def nested():\n    return {owner_name}()",
            "async function body": f"async def nested():\n    return {owner_name}()",
            "lambda body": f"handler = lambda: {owner_name}()",
            "class method body": (
                f"class Nested:\n    def method(self):\n        return {owner_name}()"
            ),
            "comprehension element": (
                f"items = [{owner_name}() for value in values]"
            ),
            "comprehension filter": (
                f"items = [value for value in values if {owner_name}()]"
            ),
            "comprehension later iterable": (
                f"items = [right for left in values for right in {owner_name}()]"
            ),
            "generator element": (
                f"items = ({owner_name}() for value in values)"
            ),
            "generator later iterable": (
                f"items = (right for left in values for right in {owner_name}())"
            ),
            "function annotation under future annotations": (
                f"def nested(value: {owner_name}()) -> {owner_name}():\n    pass"
            ),
            "class annotation under future annotations": (
                f"class Nested:\n    field: {owner_name}()"
            ),
        }
        if getattr(ast, "TypeAlias", None) is not None:
            nested_scope_sources["lazy type alias value"] = (
                f"type NestedAlias = {owner_name}()"
            )
        if getattr(ast, "TypeVar", None) is not None:
            nested_scope_sources["lazy type parameter bound"] = (
                f"def nested[T: {owner_name}()]():\n    pass"
            )
        for label, source in nested_scope_sources.items():
            with self.subTest(label=label):
                trees, registry = mutation(source)
                violations = _ownership_violations(trees, registry)
                self.assertNotIn(
                    "TRACK_AUTHORITY_CALL_INVALID",
                    _codes(violations),
                    _formatted(violations),
                )

    def test_track_authority_counts_bare_definition_time_invocations(self):
        path = "server/gear_exact_authority.py"
        owner_name = "resolve_exact_instance_progression"

        def mutation(
            source: str,
        ) -> tuple[
            dict[str, ast.Module],
            dict[str, object],
            ast.FunctionDef,
        ]:
            trees = copy.deepcopy(TREES)
            registry = copy.deepcopy(REGISTRY)
            progression = next(
                node for node in trees[path].body
                if isinstance(node, ast.FunctionDef)
                and node.name == "seal_exact_progression"
            )
            progression.body[0:0] = ast.parse(source).body
            return trees, registry, progression

        implicit_invocations = {
            "nested sync function bare decorator": (
                f"@{owner_name}\ndef nested():\n    pass",
                2,
            ),
            "nested async function bare decorator": (
                f"@{owner_name}\nasync def nested():\n    pass",
                2,
            ),
            "nested class bare decorator": (
                f"@{owner_name}\nclass Nested:\n    pass",
                2,
            ),
            "class method bare decorator": (
                f"class Nested:\n    @{owner_name}\n    def method(self):\n        pass",
                2,
            ),
            "stacked bare decorators": (
                f"@{owner_name}\n@{owner_name}\ndef nested():\n    pass",
                3,
            ),
            "parenthesized bare decorator": (
                f"@({owner_name})\ndef nested():\n    pass",
                2,
            ),
            "bare metaclass": (
                f"class Nested(metaclass={owner_name}):\n    pass",
                2,
            ),
        }
        for label, (source, expected_count) in implicit_invocations.items():
            with self.subTest(label=label):
                trees, registry, progression = mutation(source)
                production_count, extra_count, _, _ = (
                    _track_owner_scope_state(progression)
                )
                self.assertEqual(1, production_count)
                self.assertEqual(expected_count - 1, extra_count)
                violations = _ownership_violations(trees, registry)
                self.assertIn(
                    Violation(
                        path,
                        "seal_exact_progression",
                        "TRACK_AUTHORITY_CALL_INVALID",
                        (
                            "expected_production=1,actual=1;"
                            f"expected_extra=0,actual={expected_count - 1}"
                        ),
                    ),
                    violations,
                    _formatted(violations),
                )

        reference_only = {
            "bare default reference": (
                f"def nested(value={owner_name}):\n    pass"
            ),
            "bare class base reference": (
                f"class Nested({owner_name}):\n    pass"
            ),
            "bare ordinary class keyword reference": (
                f"class Nested(flag={owner_name}):\n    pass"
            ),
            "nested body not executed": (
                f"def nested():\n    return {owner_name}()"
            ),
        }
        for label, source in reference_only.items():
            with self.subTest(label=label):
                trees, registry, progression = mutation(source)
                production_count, extra_count, _, _ = (
                    _track_owner_scope_state(progression)
                )
                self.assertEqual(1, production_count)
                self.assertEqual(0, extra_count)
                violations = _ownership_violations(trees, registry)
                self.assertNotIn(
                    "TRACK_AUTHORITY_CALL_INVALID",
                    _codes(violations),
                    _formatted(violations),
                )

        with self.subTest(label="decorator factory counted only as explicit call"):
            trees, registry, progression = mutation(
                f"@{owner_name}()\ndef nested():\n    pass"
            )
            production_count, extra_count, _, _ = (
                _track_owner_scope_state(progression)
            )
            self.assertEqual(1, production_count)
            self.assertEqual(1, extra_count)
            violations = _ownership_violations(trees, registry)
            self.assertIn(
                Violation(
                    path,
                    "seal_exact_progression",
                    "TRACK_AUTHORITY_CALL_INVALID",
                    (
                        "expected_production=1,actual=1;"
                        "expected_extra=0,actual=1"
                    ),
                ),
                violations,
                _formatted(violations),
            )

    def test_track_authority_extra_invocation_cannot_replace_production_assignment(self):
        path = "server/gear_exact_authority.py"
        owner_name = TRACK_AUTHORITY_OWNER_NAME
        extra_sources = {
            "bare function decorator": (
                f"@{owner_name}\ndef nested():\n    pass"
            ),
            "bare metaclass": (
                f"class Nested(metaclass={owner_name}):\n    pass"
            ),
            "decorator factory": (
                f"@{owner_name}()\ndef nested():\n    pass"
            ),
            "nested default": (
                f"def nested(value={owner_name}()):\n    pass"
            ),
            "lambda default": (
                f"handler = lambda value={owner_name}(): value"
            ),
            "class base call": (
                f"class Nested({owner_name}()):\n    pass"
            ),
            "comprehension first iterable": (
                f"items = [value for value in {owner_name}()]"
            ),
            "class body call": (
                f"class Nested:\n    field = {owner_name}()"
            ),
        }

        for label, source in extra_sources.items():
            with self.subTest(label=label):
                trees = copy.deepcopy(TREES)
                progression = next(
                    node for node in trees[path].body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "seal_exact_progression"
                )
                production_call = next(
                    node for node in ast.walk(progression)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == owner_name
                )
                production_call.func.id = "hidden_owner"
                progression.body[0:0] = ast.parse(source).body

                violations = _ownership_violations(trees, REGISTRY)
                codes = _codes(violations)
                self.assertIn(
                    "MISSING_PRODUCTION_OWNER_CALL",
                    codes,
                    _formatted(violations),
                )
                self.assertIn(
                    "TRACK_AUTHORITY_EXTRA_CALL_INVALID",
                    codes,
                    _formatted(violations),
                )
                self.assertIn(
                    "TRACK_AUTHORITY_PROVENANCE_INVALID",
                    codes,
                    _formatted(violations),
                )

    def test_track_authority_deleted_production_assignment_is_not_satisfied_by_extra_invocation(self):
        path = "server/gear_exact_authority.py"
        owner_name = TRACK_AUTHORITY_OWNER_NAME
        extra_sources = {
            "bare decorator": f"@{owner_name}\ndef nested():\n    pass",
            "bare metaclass": f"class Nested(metaclass={owner_name}):\n    pass",
            "decorator factory": f"@{owner_name}()\ndef nested():\n    pass",
            "nested default": f"def nested(value={owner_name}()):\n    pass",
            "class base call": f"class Nested({owner_name}()):\n    pass",
            "lambda default": f"handler = lambda value={owner_name}(): value",
            "comprehension first iterable": (
                f"items = [value for value in {owner_name}()]"
            ),
            "class body call": f"class Nested:\n    field = {owner_name}()",
        }

        for label, source in extra_sources.items():
            with self.subTest(label=label):
                trees = copy.deepcopy(TREES)
                progression = next(
                    node for node in trees[path].body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "seal_exact_progression"
                )
                owner_statement = next(
                    node for node in ast.walk(progression)
                    if isinstance(node, ast.Assign)
                    and any(
                        isinstance(target, ast.Name) and target.id == "resolved"
                        for target in node.targets
                    )
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == owner_name
                )
                first_try = next(
                    node for node in progression.body if isinstance(node, ast.Try)
                )
                first_try.body.remove(owner_statement)
                progression.body[0:0] = ast.parse(source).body

                violations = _ownership_violations(trees, REGISTRY)
                codes = _codes(violations)
                self.assertIn(
                    "MISSING_PRODUCTION_OWNER_CALL",
                    codes,
                    _formatted(violations),
                )
                self.assertIn(
                    "TRACK_AUTHORITY_EXTRA_CALL_INVALID",
                    codes,
                    _formatted(violations),
                )
                self.assertIn(
                    "TRACK_AUTHORITY_PROVENANCE_INVALID",
                    codes,
                    _formatted(violations),
                )

    def test_track_authority_production_assignment_role_and_result_binding_are_exact(self):
        path = "server/gear_exact_authority.py"
        owner_name = TRACK_AUTHORITY_OWNER_NAME

        def mutation() -> tuple[
            dict[str, ast.Module],
            ast.FunctionDef,
            ast.Try,
            ast.Assign,
        ]:
            trees = copy.deepcopy(TREES)
            progression = next(
                node for node in trees[path].body
                if isinstance(node, ast.FunctionDef)
                and node.name == "seal_exact_progression"
            )
            first_try = next(
                node for node in progression.body if isinstance(node, ast.Try)
            )
            owner_statement = next(
                node for node in first_try.body
                if isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "resolved"
                and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id == owner_name
            )
            return trees, progression, first_try, owner_statement

        for label, replacement in (
            (
                "wrong assignment target",
                lambda statement: setattr(statement.targets[0], "id", "other"),
            ),
            (
                "attribute owner call",
                lambda statement: setattr(
                    statement.value,
                    "func",
                    ast.Attribute(
                        value=ast.Name(id="hidden", ctx=ast.Load()),
                        attr=owner_name,
                        ctx=ast.Load(),
                    ),
                ),
            ),
        ):
            with self.subTest(label=label):
                trees, _, _, owner_statement = mutation()
                replacement(owner_statement)
                violations = _ownership_violations(trees, REGISTRY)
                self.assertIn(
                    "MISSING_PRODUCTION_OWNER_CALL",
                    _codes(violations),
                    _formatted(violations),
                )
                if label == "wrong assignment target":
                    self.assertIn(
                        "TRACK_AUTHORITY_EXTRA_CALL_INVALID",
                        _codes(violations),
                        _formatted(violations),
                    )

        with self.subTest(label="expression call is only an extra invocation"):
            trees, _, first_try, owner_statement = mutation()
            index = first_try.body.index(owner_statement)
            first_try.body[index] = ast.Expr(value=owner_statement.value)
            violations = _ownership_violations(trees, REGISTRY)
            self.assertIn(
                "MISSING_PRODUCTION_OWNER_CALL",
                _codes(violations),
                _formatted(violations),
            )
            self.assertIn(
                "TRACK_AUTHORITY_EXTRA_CALL_INVALID",
                _codes(violations),
                _formatted(violations),
            )

        for label, wrapper in (
            (
                "nested function",
                lambda statement: ast.FunctionDef(
                    name="nested",
                    args=ast.arguments(
                        posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[],
                        defaults=[], vararg=None, kwarg=None,
                    ),
                    body=[statement],
                    decorator_list=[],
                ),
            ),
            (
                "dead branch",
                lambda statement: ast.If(
                    test=ast.Constant(value=False),
                    body=[statement],
                    orelse=[],
                ),
            ),
        ):
            with self.subTest(label=f"production assignment moved to {label}"):
                trees, _, first_try, owner_statement = mutation()
                index = first_try.body.index(owner_statement)
                first_try.body[index] = wrapper(owner_statement)
                violations = _ownership_violations(trees, REGISTRY)
                self.assertIn(
                    "MISSING_PRODUCTION_OWNER_CALL",
                    _codes(violations),
                    _formatted(violations),
                )

        for label, source in (
            ("second assignment", "resolved = hidden"),
            ("destructuring assignment", "resolved, other = pair"),
            ("hidden overwrite", "resolved = hidden()"),
            ("annotated binding", "resolved: object"),
            ("augmented binding", "resolved += hidden"),
            ("walrus binding", "if (resolved := hidden):\n    pass"),
            ("for binding", "for resolved in values:\n    pass"),
            ("with binding", "with manager as resolved:\n    pass"),
            ("except binding", "try:\n    pass\nexcept Exception as resolved:\n    pass"),
            ("match binding", "match value:\n    case {'resolved': resolved}:\n        pass"),
            ("delete binding", "del resolved"),
            ("import binding", "from hidden import value as resolved"),
            ("function binding", "def resolved():\n    pass"),
            ("class binding", "class resolved:\n    pass"),
            ("global binding", "global resolved"),
            ("nonlocal binding", "nonlocal resolved"),
        ):
            with self.subTest(label=label):
                trees, _, first_try, owner_statement = mutation()
                index = first_try.body.index(owner_statement)
                first_try.body[index + 1:index + 1] = ast.parse(source).body
                violations = _ownership_violations(trees, REGISTRY)
                self.assertIn(
                    "TRACK_AUTHORITY_RESULT_BINDING_INVALID",
                    _codes(violations),
                    _formatted(violations),
                )

        parameter_mutations = {
            "posonly parameter": lambda arguments: arguments.posonlyargs.append(
                ast.arg(arg="resolved")
            ),
            "positional parameter": lambda arguments: arguments.args.append(
                ast.arg(arg="resolved")
            ),
            "keyword-only parameter": lambda arguments: (
                arguments.kwonlyargs.append(ast.arg(arg="resolved")),
                arguments.kw_defaults.append(None),
            ),
            "variadic parameter": lambda arguments: setattr(
                arguments, "vararg", ast.arg(arg="resolved")
            ),
            "keyword variadic parameter": lambda arguments: setattr(
                arguments, "kwarg", ast.arg(arg="resolved")
            ),
        }
        for label, mutate_arguments in parameter_mutations.items():
            with self.subTest(label=label):
                trees, progression, _, _ = mutation()
                mutate_arguments(progression.args)
                violations = _ownership_violations(trees, REGISTRY)
                self.assertIn(
                    "TRACK_AUTHORITY_RESULT_BINDING_INVALID",
                    _codes(violations),
                    _formatted(violations),
                )

        type_var = getattr(ast, "TypeVar", None)
        if type_var is not None:
            with self.subTest(label="type parameter"):
                trees, progression, _, _ = mutation()
                getattr(progression, "type_params").append(
                    type_var(name="resolved")
                )
                violations = _ownership_violations(trees, REGISTRY)
                self.assertIn(
                    "TRACK_AUTHORITY_RESULT_BINDING_INVALID",
                    _codes(violations),
                    _formatted(violations),
                )

        with self.subTest(label="duplicate approved assignment"):
            trees, _, first_try, owner_statement = mutation()
            first_try.body.insert(
                first_try.body.index(owner_statement) + 1,
                copy.deepcopy(owner_statement),
            )
            violations = _ownership_violations(trees, REGISTRY)
            self.assertIn(
                "TRACK_AUTHORITY_CALL_INVALID",
                _codes(violations),
                _formatted(violations),
            )

        with self.subTest(label="legitimate production plus extra is invalid"):
            trees, progression, _, _ = mutation()
            progression.body.insert(0, ast.Expr(value=ast.Call(
                func=ast.Name(id=owner_name, ctx=ast.Load()),
                args=[],
                keywords=[],
            )))
            violations = _ownership_violations(trees, REGISTRY)
            self.assertIn(
                "TRACK_AUTHORITY_EXTRA_CALL_INVALID",
                _codes(violations),
                _formatted(violations),
            )

        with self.subTest(label="nested decoy cannot satisfy hidden production"):
            trees, progression, _, owner_statement = mutation()
            owner_statement.value.func.id = "hidden_owner"
            nested_statement = copy.deepcopy(owner_statement)
            nested_statement.value.func.id = owner_name
            progression.body.insert(0, ast.FunctionDef(
                name="nested",
                args=ast.arguments(
                    posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[],
                    defaults=[], vararg=None, kwarg=None,
                ),
                body=[nested_statement],
                decorator_list=[],
            ))
            violations = _ownership_violations(trees, REGISTRY)
            self.assertIn(
                "MISSING_PRODUCTION_OWNER_CALL",
                _codes(violations),
                _formatted(violations),
            )

        with self.subTest(label="current production statement is exact"):
            violations = _ownership_violations(copy.deepcopy(TREES), REGISTRY)
            self.assertNotIn(
                "MISSING_PRODUCTION_OWNER_CALL",
                _codes(violations),
                _formatted(violations),
            )
            self.assertNotIn(
                "TRACK_AUTHORITY_EXTRA_CALL_INVALID",
                _codes(violations),
                _formatted(violations),
            )
            self.assertNotIn(
                "TRACK_AUTHORITY_RESULT_BINDING_INVALID",
                _codes(violations),
                _formatted(violations),
            )

    def test_track_authority_pep695_support_is_capability_guarded(self):
        import sys
        import types
        from unittest import mock

        path = "server/gear_exact_authority.py"
        trees = copy.deepcopy(TREES)
        progression = next(
            node for node in trees[path].body
            if isinstance(node, ast.FunctionDef)
            and node.name == "seal_exact_progression"
        )
        if hasattr(progression, "type_params"):
            delattr(progression, "type_params")
        self.assertEqual(_ownership_violations(trees, REGISTRY), [])

        compatibility_ast = types.ModuleType("ast")
        pep695_names = {"TypeAlias", "TypeVar", "TypeVarTuple", "ParamSpec"}
        for name, value in vars(ast).items():
            if name not in pep695_names:
                setattr(compatibility_ast, name, value)
        source = (ROOT / "tests/gear_canonical_owner_gate_test.py").read_text(
            encoding="utf-8"
        )
        namespace = {
            "__name__": "gear_canonical_owner_gate_py311_compat",
            "__file__": str(ROOT / "tests/gear_canonical_owner_gate_test.py"),
        }
        with mock.patch.dict(sys.modules, {"ast": compatibility_ast}):
            exec(compile(source, namespace["__file__"], "exec"), namespace)
        case = namespace["GearCanonicalOwnerGateTest"](
            "test_track_authority_call_has_one_unshadowed_bare_name_in_owner_scope"
        )
        result = unittest.TestResult()
        case.run(result)
        self.assertTrue(result.wasSuccessful(), result.failures + result.errors)

    def test_exemption_orphan_multimatch_and_ast_change_fail_closed(self):
        path = "server/gear_exact_item_instance.py"

        trees = copy.deepcopy(TREES)
        trees[path].body = [
            node
            for node in trees[path].body
            if not (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER"
                    for target in node.targets
                )
            )
        ]
        self.assertIn(
            "EXEMPTION_ORPHAN",
            _codes(_registry_violations(REGISTRY, trees)),
        )

        trees = copy.deepcopy(TREES)
        node = next(
            node
            for node in trees[path].body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "EXACT_STATIC_FACTS_MAX_ABSOLUTE_NUMBER"
                for target in node.targets
            )
        )
        trees[path].body.insert(trees[path].body.index(node), copy.deepcopy(node))
        self.assertIn(
            "EXEMPTION_MULTIMATCH",
            _codes(_registry_violations(REGISTRY, trees)),
        )

        trees = copy.deepcopy(TREES)
        node = next(
            node
            for node in trees[path].body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "EXACT_STATIC_FACTS_MAX_CANONICAL_BYTES"
                for target in node.targets
            )
        )
        node.value = ast.Constant(value=65536)
        self.assertIn(
            "EXEMPTION_DIGEST_MISMATCH",
            _codes(_registry_violations(REGISTRY, trees)),
        )

    def test_physical_import_and_reexport_mutations_fail_closed(self):
        path = "server/gear_exact_item_instance.py"
        for label, source, expected in (
            ("module", "import os", "UNREGISTERED_PHYSICAL_IMPORT"),
            (
                "symbol",
                "from .gear_canonical_kernel import hidden",
                "UNREGISTERED_PHYSICAL_IMPORT",
            ),
            (
                "alias",
                "from .gear_canonical_kernel import CanonicalIssue as Hidden",
                "UNREGISTERED_PHYSICAL_IMPORT",
            ),
            (
                "star",
                "from .gear_canonical_kernel import *",
                "STAR_IMPORT_FORBIDDEN",
            ),
            (
                "approved module unknown symbol",
                "from .gear_canonical_kernel import hidden_owner",
                "UNREGISTERED_PHYSICAL_IMPORT",
            ),
        ):
            with self.subTest(label=label):
                self.assertModuleCode(path, source, expected)

        trees = copy.deepcopy(TREES)
        authority = trees["server/gear_exact_authority.py"]
        all_assignment = next(
            node
            for node in authority.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            )
        )
        all_assignment.value.elts.append(ast.Constant(value="CanonicalIssue"))
        self.assertIn(
            "REEXPORT_MISMATCH",
            _codes(_registry_violations(REGISTRY, trees)),
        )

    def test_module_load_expression_and_assignment_mutations_fail_closed(self):
        path = "server/gear_exact_item_instance.py"
        cases = (
            ("dynamic import", "__import__('server.hidden_owner')", "DYNAMIC_IMPORT_FORBIDDEN"),
            (
                "importlib",
                "import importlib\nimportlib.import_module('server.hidden_owner')",
                "DYNAMIC_IMPORT_FORBIDDEN",
            ),
            ("IIFE", "(lambda: 1)()", "MODULE_LOAD_CALL"),
            ("lambda assignment", "EXTRA = (lambda: 1)", "MODULE_ASSIGNMENT_FORBIDDEN"),
            ("comprehension", "EXTRA = [x for x in ()]", "MODULE_ASSIGNMENT_FORBIDDEN"),
            ("generator", "EXTRA = (x for x in ())", "MODULE_ASSIGNMENT_FORBIDDEN"),
            ("named expression", "EXTRA = (value := 1)", "MODULE_ASSIGNMENT_FORBIDDEN"),
            ("mutable list", "EXTRA = []", "MUTABLE_MODULE_STATE"),
            ("mutable dict", "EXTRA = {}", "MUTABLE_MODULE_STATE"),
            ("mutable set", "EXTRA = {1}", "MUTABLE_MODULE_STATE"),
            ("attribute mutation", "holder.value = 1", "MODULE_ASSIGNMENT_TARGET_FORBIDDEN"),
            ("subscript mutation", "globals()['value'] = 1", "MODULE_ASSIGNMENT_TARGET_FORBIDDEN"),
            ("augmented mutation", "value += 1", "MODULE_NAMESPACE_MUTATION"),
            ("delete", "del value", "MODULE_NAMESPACE_MUTATION"),
            ("loop", "for value in ():\n    pass", "MODULE_LOAD_NODE_FORBIDDEN"),
            ("with", "with manager:\n    pass", "MODULE_LOAD_NODE_FORBIDDEN"),
            ("conditional", "if condition:\n    pass", "MODULE_LOAD_NODE_FORBIDDEN"),
            ("setattr", "setattr(holder, 'value', 1)", "MODULE_LOAD_CALL"),
            ("delattr", "delattr(holder, 'value')", "MODULE_LOAD_CALL"),
            ("exec", "exec('value = 1')", "MODULE_LOAD_CALL"),
            ("eval", "eval('1')", "MODULE_LOAD_CALL"),
            ("compile", "compile('1', '<x>', 'eval')", "MODULE_LOAD_CALL"),
            ("intrinsic shadow", "frozenset = 1", "MODULE_ASSIGNMENT_FORBIDDEN"),
        )
        for label, source, expected in cases:
            with self.subTest(label=label):
                self.assertModuleCode(path, source, expected)

    def test_function_annotation_decorator_and_future_mutations_fail_closed(self):
        path = "server/gear_exact_item_instance.py"
        for label, source, expected in (
            (
                "call default",
                "def hidden(value=build()):\n    pass",
                "CALL_DEFAULT_FORBIDDEN",
            ),
            (
                "call annotation",
                "def hidden(value: build()):\n    pass",
                "DYNAMIC_ANNOTATION_FORBIDDEN",
            ),
            (
                "lambda annotation",
                "def hidden(value: (lambda: object)):\n    pass",
                "DYNAMIC_ANNOTATION_FORBIDDEN",
            ),
            (
                "comprehension annotation",
                "def hidden(value: [x for x in ()]):\n    pass",
                "DYNAMIC_ANNOTATION_FORBIDDEN",
            ),
            (
                "named expression annotation",
                "def hidden(value: (kind := object)):\n    pass",
                "DYNAMIC_ANNOTATION_FORBIDDEN",
            ),
            (
                "function decorator",
                "@decorator\ndef hidden():\n    pass",
                "FUNCTION_DECORATOR_FORBIDDEN",
            ),
            (
                "module annotation",
                "EXTRA: build() = 1",
                "DYNAMIC_ANNOTATION_FORBIDDEN",
            ),
            (
                "module getattr",
                "def __getattr__(name):\n    return name",
                "MODULE_HOOK_FORBIDDEN",
            ),
            (
                "module getattribute",
                "def __getattribute__(name):\n    return name",
                "MODULE_HOOK_FORBIDDEN",
            ),
            (
                "module dir",
                "def __dir__():\n    return ()",
                "MODULE_HOOK_FORBIDDEN",
            ),
        ):
            with self.subTest(label=label):
                self.assertModuleCode(path, source, expected)

        tree = copy.deepcopy(TREES[path])
        tree.body = [
            node
            for node in tree.body
            if not (
                isinstance(node, ast.ImportFrom)
                and node.module == "__future__"
            )
        ]
        violations = _module_load_violations(
            path,
            tree,
            PROFILE_BY_PATH[path],
            REGISTRY,
        )
        self.assertIn(
            "FUTURE_ANNOTATIONS_REQUIRED",
            _codes(violations),
            _formatted(violations),
        )

    def test_class_grammar_mutations_fail_closed(self):
        path = "server/simc_item_effect_support.py"
        cases = (
            (
                "unapproved decorator",
                "@decorator\nclass Hidden:\n    pass",
                "CLASS_DECORATOR_FORBIDDEN",
            ),
            (
                "class base",
                "class Hidden(Base):\n    pass",
                "CLASS_BASE_FORBIDDEN",
            ),
            (
                "metaclass",
                "class Hidden(metaclass=Meta):\n    pass",
                "CLASS_BASE_FORBIDDEN",
            ),
            (
                "class body call",
                "class Hidden:\n    VALUE = build()",
                "CLASS_BODY_NODE_FORBIDDEN",
            ),
            (
                "descriptor",
                "class Hidden:\n    value = property(read)",
                "CLASS_BODY_NODE_FORBIDDEN",
            ),
            (
                "dataclass arguments",
                "@dataclass(frozen=True, slots=True)\nclass Hidden:\n    value: str",
                "CLASS_DECORATOR_FORBIDDEN",
            ),
            (
                "class annotation call",
                "class Hidden:\n    value: build()",
                "DYNAMIC_ANNOTATION_FORBIDDEN",
            ),
        )
        for label, source, expected in cases:
            with self.subTest(label=label):
                self.assertModuleCode(path, source, expected)

    def test_cli_bootstrap_is_exact_and_cannot_expand(self):
        path = "scripts/simc-item-effect-probe.py"
        for label, source, expected in (
            (
                "extra path mutation",
                "sys.path.append(str(ROOT))",
                "MODULE_LOAD_CALL",
            ),
            (
                "second class base",
                "class Hidden(ValueError):\n    pass",
                "CLASS_BASE_FORBIDDEN",
            ),
            (
                "second main guard",
                "if __name__ == '__main__':\n    main()",
                "MODULE_LOAD_NODE_FORBIDDEN",
            ),
            (
                "bootstrap alias",
                "BOOTSTRAP = ROOT",
                "MODULE_ASSIGNMENT_FORBIDDEN",
            ),
        ):
            with self.subTest(label=label):
                self.assertModuleCode(path, source, expected)

    def test_module_checker_ignores_function_bodies_but_physical_import_scan_does_not(self):
        path = "server/gear_exact_item_instance.py"
        tree = _tree_with(
            path,
            (
                "def _hidden_runtime(value):\n"
                "    str(value).strip()\n"
                "    from server.hidden_owner import mutate\n"
                "    mutate()"
            ),
        )
        module_violations = _module_load_violations(
            path,
            tree,
            PROFILE_BY_PATH[path],
            REGISTRY,
        )
        self.assertIn(
            "UNREGISTERED_PHYSICAL_IMPORT",
            _codes(module_violations),
            _formatted(module_violations),
        )
        self.assertNotIn(
            "MODULE_LOAD_CALL",
            _codes(module_violations),
            _formatted(module_violations),
        )
        direct = _direct_primitive_violations(path, tree)
        self.assertIn("IDENTITY_COERCION", _codes(direct), _formatted(direct))
        self.assertIn("IDENTITY_TRIM", _codes(direct), _formatted(direct))

    def test_machine_gate_rejects_old_engine_symbols_and_preserves_runtime_owners(self):
        test_tree = ast.parse(
            (ROOT / "tests/gear_canonical_owner_gate_test.py").read_text(
                encoding="utf-8"
            )
        )
        defined = {
            node.name
            for node in ast.walk(test_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        assigned = {
            target.id
            for node in ast.walk(test_tree)
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
            if isinstance(target, ast.Name)
        }
        self.assertEqual(
            set(),
            FORBIDDEN_OLD_ENGINE_SYMBOLS.intersection(defined | assigned),
        )

        trees = copy.deepcopy(TREES)
        authority = trees["server/gear_exact_authority.py"]
        progression = next(
            node
            for node in authority.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "seal_exact_progression"
        )
        resolver_call = next(
            node
            for node in ast.walk(progression)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "resolve_exact_instance_progression"
        )
        resolver_call.func.id = "hidden_resolver"
        self.assertIn(
            "MISSING_PRODUCTION_OWNER_CALL",
            _codes(_ownership_violations(trees, REGISTRY)),
        )

        trees = copy.deepcopy(TREES)
        item = trees["server/gear_exact_item_instance.py"]
        item.body.append(ast.Assign(
            targets=[ast.Name(id="_SECOND_SLOT_OWNER", ctx=ast.Store())],
            value=ast.Tuple(
                elts=[
                    ast.Constant(value="head"),
                    ast.Constant(value="neck"),
                    ast.Constant(value="chest"),
                ],
                ctx=ast.Load(),
            ),
        ))
        self.assertIn(
            "DUPLICATE_SLOT_MEMBERSHIP",
            _codes(_ownership_violations(trees, REGISTRY)),
        )

    def test_sealed_signatures_and_deleted_raw_apis_are_machine_checked(self):
        trees = copy.deepcopy(TREES)
        item = trees["server/gear_exact_item_instance.py"]
        serializer = next(
            node
            for node in item.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "derive_simc_serializer_input"
        )
        serializer.args.args[0].annotation = ast.Name(id="object", ctx=ast.Load())
        self.assertIn(
            "SEALED_SIGNATURE_MISMATCH",
            _codes(_ownership_violations(trees, REGISTRY)),
        )

        repository = {"server/example.py": ast.parse(
            "def build_exact_item_identity(value):\n    return value\n"
        )}
        self.assertIn(
            "DELETED_DEFINITION",
            _codes(_deleted_name_violations(repository)),
        )

    def test_control_plane_records_stop_gate_before_task2(self):
        requirement = json.loads((
            ROOT
            / "artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual("implementation_allowed", requirement["status"])
        self.assertEqual([], requirement["ownership"]["runtimeConsumers"])
        self.assertFalse(requirement["ownership"]["originalTask3Activated"])

        project_map = json.loads(
            (ROOT / "docs/project-owner-map.json").read_text(encoding="utf-8")
        )
        gear_domain = next(
            domain
            for domain in project_map["criticalDomains"]
            if "canonicalKernelFoundations" in domain
        )
        self.assertEqual(
            "none_pending_source_change_control_replacement",
            gear_domain["canonicalKernelFoundations"]["proofClaim"],
        )

        backend_map = json.loads(
            (ROOT / "docs/backend-owner-map.json").read_text(encoding="utf-8")
        )
        kernel_hotspot = next(
            hotspot
            for hotspot in backend_map["hotspotFiles"]
            if hotspot["path"] == "server/gear_canonical_kernel.py"
        )
        self.assertEqual(
            "none_pending_source_change_control_replacement",
            kernel_hotspot["owners"][0]["proofClaim"],
        )


if __name__ == "__main__":
    unittest.main()
