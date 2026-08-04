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
FROZEN_V1_DIRECT_PRIMITIVE_EXCEPTIONS = frozenset({
    ("server/gear_exact_item_instance.py", "_canonical", "DUPLICATE_JSON_OWNER", "7231941be36f1e81041b1597a91a543b42f48c410be92ac9238de06fd4dc1058"),
    ("server/gear_exact_item_instance.py", "_canonical_bytes", "DUPLICATE_JSON_OWNER", "7231941be36f1e81041b1597a91a543b42f48c410be92ac9238de06fd4dc1058"),
    ("server/gear_exact_item_instance.py", "_hash", "DUPLICATE_HASH_OWNER", "72e0ca3c56475eb0e591218d85a12e77c8eec5e237feaf9a46148188e9ed1f38"),
    ("server/gear_exact_item_instance.py", "_text", "IDENTITY_TRIM", "76193f035544dbf4410d97b6bb66e790ce9a81005ca9626c99a8067972771351"),
    ("server/gear_exact_item_instance.py", "_text", "IDENTITY_COERCION", "88d3520b955995521e902e02cd7ed820574701d159c015fc2852eeaab3bd2e61"),
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
})


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


def _actual_fallback_pairs(
    tree: ast.Module,
) -> list[tuple[tuple[object, object, object], tuple[object, object, object]]]:
    pairs = []
    for node in tree.body:
        if not isinstance(node, ast.Try) or len(node.handlers) != 1:
            continue
        relative = [
            item
            for statement in node.body
            if isinstance(statement, (ast.Import, ast.ImportFrom))
            for item in _imports_from_statement(statement)
        ]
        absolute = [
            item
            for statement in node.handlers[0].body
            if isinstance(statement, (ast.Import, ast.ImportFrom))
            for item in _imports_from_statement(statement)
        ]
        absolute_by_binding = {
            (item[1], item[2]): item for item in absolute
        }
        for item in relative:
            match = absolute_by_binding.get((item[1], item[2]))
            if match is not None:
                pairs.append((item, match))
    return pairs


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


def _actual_reexports(tree: ast.Module) -> set[tuple[object, ...]]:
    exports = _exports(tree) or []
    local = _local_definitions(tree)
    by_alias: dict[str, list[tuple[object, object, object]]] = {}
    for item in _physical_imports(tree):
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
        if Counter(declared_pairs) != Counter(_actual_fallback_pairs(tree)):
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
        if declared_reexports != _actual_reexports(tree):
            violations.append(_registry_finding("REEXPORT_MISMATCH", str(path)))

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
    valid_handler = (
        len(node.handlers) == 1
        and isinstance(node.handlers[0].type, ast.Name)
        and node.handlers[0].type.id == "ImportError"
        and node.handlers[0].name is None
    )
    statements = [*node.body, *(node.handlers[0].body if node.handlers else [])]
    if (
        not valid_handler
        or node.orelse
        or node.finalbody
        or not statements
        or any(not isinstance(item, (ast.Import, ast.ImportFrom)) for item in statements)
    ):
        return [Violation(path, "<module>", "IMPORT_FALLBACK_FORBIDDEN", "Try")]
    return []


def _module_load_violations(
    path: str,
    tree: ast.Module,
    profile: str,
    registry: dict[str, object],
) -> list[Violation]:
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
            if (path, function.name, code, digest) in FROZEN_V1_DIRECT_PRIMITIVE_EXCEPTIONS:
                continue
            violations.append(Violation(path, function.name, code, name))
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
        for required in ("canonical_slot", "resolve_exact_instance_progression"):
            if required not in calls:
                violations.append(Violation("server/gear_exact_authority.py", "seal_exact_progression", "MISSING_PRODUCTION_OWNER_CALL", required))
    del registry
    return sorted(set(violations))


def _source_change_control_violations(
    target_trees: dict[str, ast.Module],
    repository_trees: dict[str, ast.Module],
    registry: dict[str, object],
) -> list[Violation]:
    violations = _registry_violations(registry, target_trees)
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
        cases.append(("target record", changed, "TARGET_RECORD_INVALID"))

        for field, expected in (
            ("publicCallables", "PUBLIC_CALLABLE_MISMATCH"),
            ("exports", "EXPORT_MISMATCH"),
            ("sealedEntrypoints", "SEALED_ENTRYPOINT_MISMATCH"),
        ):
            changed = copy.deepcopy(REGISTRY)
            changed["targets"][0][field].append([])
            cases.append((field, changed, expected))

        changed = copy.deepcopy(REGISTRY)
        changed["targets"][0]["imports"][0]["symbol"] = []
        cases.append(("import symbol", changed, "IMPORT_RECORD_INVALID"))

        for label, registry, expected in cases:
            with self.subTest(label=label):
                violations = _registry_violations(registry, TREES)
                self.assertIn(expected, _codes(violations), _formatted(violations))

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
