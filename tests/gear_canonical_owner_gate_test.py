import ast
import copy
from dataclasses import dataclass
from pathlib import Path
import unittest

from server.gear_contracts import CANONICAL_GEAR_SLOTS


ROOT = Path(__file__).resolve().parents[1]
TASK2_CONSUMERS = (
    "server/gear_exact_item_instance.py",
    "server/gear_exact_authority.py",
    "server/simc_item_effect_support.py",
    "server/simc_item_effect_probe.py",
    "scripts/simc-item-effect-probe.py",
)

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

SEALED_ENTRYPOINTS = {
    "server/gear_exact_item_instance.py": frozenset({
        "seal_exact_item",
        "seal_exact_static_facts",
        "derive_simc_serializer_input",
    }),
    "server/gear_exact_authority.py": frozenset({
        "seal_exact_progression",
        "seal_exact_authority_envelope",
    }),
    "server/simc_item_effect_support.py": frozenset({
        "derive_exact_effect_subjects",
        "seal_effect_record",
        "verify_effect_record",
        "resolve_exact_effect_support",
    }),
    "server/simc_item_effect_probe.py": frozenset({
        "evaluate_effect_probe",
    }),
    "scripts/simc-item-effect-probe.py": frozenset({"main"}),
}

PUBLIC_FUNCTION_ALLOWLIST = {
    "server/gear_exact_item_instance.py": frozenset({
        "canonical_enhancement_selection",
        "seal_exact_item",
        "seal_exact_static_facts",
        "derive_simc_serializer_input",
        "build_exact_item_instance",
    }),
    "server/gear_exact_authority.py": frozenset({
        "seal_exact_progression",
        "seal_exact_authority_envelope",
    }),
    "server/simc_item_effect_support.py": frozenset({
        "derive_exact_effect_subjects",
        "seal_effect_record",
        "verify_effect_record",
        "resolve_exact_effect_support",
    }),
    "server/simc_item_effect_probe.py": frozenset({"evaluate_effect_probe"}),
    "scripts/simc-item-effect-probe.py": frozenset({"main"}),
}

FILE_FORBIDDEN_DEFINITIONS = {
    "server/gear_exact_item_instance.py": frozenset({
        "_strict_identifier",
        "_strict_identifier_list",
        "_strict_level_list",
        "_strict_enchant",
        "_strict_v2_enhancement_selection",
        "_canonical_identifier_item",
        "_canonical_level_item",
    }),
    "server/gear_exact_authority.py": frozenset({
        "_canonical",
        "_hash",
        "_blocked",
        "_contains_forbidden",
        "_valid_exact",
        "_valid_token",
        "_expected_serializer",
        "_valid_static_facts",
        "_valid_progression",
        "_valid_effect_support",
    }),
    "server/simc_item_effect_support.py": frozenset({
        "_signature",
        "_legacy_to_canonical_record",
        "_legacy_subjects",
    }),
}

PRIMITIVE_OWNER_DEFINITIONS = frozenset({
    "_canonical",
    "_canonical_json",
    "_canonical_text",
    "_hash",
    "_valid_token",
    "valid_runtime_revision",
    "valid_effect_tokens",
})

SEALED_PARAMETER_CONTRACTS = {
    ("server/gear_exact_item_instance.py", "derive_simc_serializer_input"): {
        "exact": "SealedCanonicalDocument",
    },
    ("server/gear_exact_item_instance.py", "seal_exact_static_facts"): {
        "exact": "SealedCanonicalDocument",
    },
    ("server/gear_exact_authority.py", "seal_exact_progression"): {
        "exact": "SealedCanonicalDocument",
    },
    ("server/gear_exact_authority.py", "seal_exact_authority_envelope"): {
        "exact": "SealedCanonicalDocument",
        "static_facts": "SealedCanonicalDocument",
        "progression": "SealedCanonicalDocument",
        "effect_support": "SealedCanonicalDocument",
    },
    ("server/simc_item_effect_support.py", "derive_exact_effect_subjects"): {
        "exact": "SealedCanonicalDocument",
    },
    ("server/simc_item_effect_support.py", "resolve_exact_effect_support"): {
        "exact": "SealedCanonicalDocument",
        "records": "Sequence[SealedCanonicalDocument]",
    },
}


@dataclass(frozen=True, order=True)
class Violation:
    path: str
    function: str
    code: str
    detail: str


def _function_definitions(tree: ast.AST) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in getattr(tree, "body", ())
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _referenced_local_functions(
    node: ast.AST,
    definitions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
) -> set[str]:
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name)
        and isinstance(child.ctx, ast.Load)
        and child.id in definitions
    }


def _sealed_call_graph(
    tree: ast.AST,
    entrypoints: frozenset[str],
) -> tuple[dict[str, ast.FunctionDef | ast.AsyncFunctionDef], set[str]]:
    definitions = _function_definitions(tree)
    missing = set(entrypoints).difference(definitions)
    if missing:
        return definitions, set()
    reachable: set[str] = set()
    pending = list(entrypoints)
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(
            _referenced_local_functions(definitions[name], definitions).difference(reachable)
        )
    return definitions, reachable


def _annotation_text(node: ast.arg) -> str:
    return ast.unparse(node.annotation) if node.annotation is not None else ""


def _parameters(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, ast.arg]:
    args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
    if node.args.vararg is not None:
        args.append(node.args.vararg)
    if node.args.kwarg is not None:
        args.append(node.args.kwarg)
    return {argument.arg: argument for argument in args}


def _identity_primitive_violations(
    path: str,
    function: str,
    node: ast.AST,
) -> list[Violation]:
    violations: list[Violation] = []
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Name)
            and isinstance(child.ctx, ast.Load)
            and "catalog" in child.id.lower()
        ):
            violations.append(Violation(
                path,
                function,
                "CATALOG_DEPENDENCY",
                child.id,
            ))
        if (
            isinstance(child, ast.Attribute)
            and "catalog" in child.attr.lower()
        ):
            violations.append(Violation(
                path,
                function,
                "CATALOG_DEPENDENCY",
                ast.unparse(child),
            ))
        if not isinstance(child, ast.Call):
            continue
        if isinstance(child.func, ast.Attribute) and child.func.attr == "strip":
            violations.append(Violation(path, function, "IDENTITY_TRIM", ".strip()"))
        if isinstance(child.func, ast.Name) and child.func.id == "str":
            violations.append(Violation(path, function, "IDENTITY_COERCION", "str(...)"))
        if (
            isinstance(child.func, ast.Name)
            and child.func.id == "sorted"
            and child.args
            and isinstance(child.args[0], ast.Call)
            and isinstance(child.args[0].func, ast.Name)
            and child.args[0].func.id == "set"
        ):
            violations.append(
                Violation(path, function, "IDENTITY_SORT_DEDUPE", "sorted(set(...))")
            )
        if (
            isinstance(child.func, ast.Attribute)
            and isinstance(child.func.value, ast.Name)
            and child.func.value.id == "json"
            and child.func.attr == "dumps"
        ):
            detail = "json.dumps(...)"
            if any(
                keyword.arg == "default"
                and isinstance(keyword.value, ast.Name)
                and keyword.value.id == "str"
                for keyword in child.keywords
            ):
                detail = "json.dumps(..., default=str)"
            violations.append(Violation(path, function, "DUPLICATE_JSON_OWNER", detail))
        if (
            isinstance(child.func, ast.Attribute)
            and isinstance(child.func.value, ast.Name)
            and child.func.value.id == "hashlib"
        ):
            violations.append(
                Violation(path, function, "DUPLICATE_HASH_OWNER", ast.unparse(child.func))
            )
    return violations


def _collection_strings(node: ast.AST) -> set[str] | None:
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"frozenset", "set", "tuple", "list"}
        and len(node.args) == 1
        and not node.keywords
    ):
        return _collection_strings(node.args[0])
    if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return None
    values: set[str] = set()
    for element in node.elts:
        if not isinstance(element, ast.Constant) or type(element.value) is not str:
            return None
        values.add(element.value)
    return values


def _consumer_violations(trees: dict[str, ast.AST]) -> list[Violation]:
    violations: list[Violation] = []
    for path in TASK2_CONSUMERS:
        tree = trees.get(path)
        if tree is None:
            violations.append(Violation(path, "<module>", "MISSING_SCAN_TARGET", path))
            continue
        definitions, reachable = _sealed_call_graph(tree, SEALED_ENTRYPOINTS[path])
        missing = SEALED_ENTRYPOINTS[path].difference(definitions)
        for function in sorted(missing):
            violations.append(
                Violation(path, function, "MISSING_SEALED_ENTRYPOINT", function)
            )
        for function in sorted(reachable):
            if function in PRIMITIVE_OWNER_DEFINITIONS:
                violations.append(
                    Violation(path, function, "DUPLICATE_PRIMITIVE_OWNER", function)
                )
            violations.extend(
                _identity_primitive_violations(path, function, definitions[function])
            )
        forbidden = FILE_FORBIDDEN_DEFINITIONS.get(path, frozenset())
        for function in sorted(forbidden.intersection(definitions)):
            violations.append(
                Violation(path, function, "LEGACY_OR_DUPLICATE_DEFINITION", function)
            )
        for function in sorted(definitions):
            if (
                not function.startswith("_")
                and function not in PUBLIC_FUNCTION_ALLOWLIST[path]
            ):
                violations.append(Violation(
                    path,
                    function,
                    "UNAPPROVED_PUBLIC_API",
                    function,
                ))

        for node in getattr(tree, "body", ()):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            values = _collection_strings(value) if value is not None else None
            if values is None:
                continue
            slot_overlap = values.intersection(CANONICAL_GEAR_SLOTS)
            if len(slot_overlap) >= 3:
                violations.append(Violation(
                    path,
                    "<module>",
                    "DUPLICATE_SLOT_MEMBERSHIP",
                    ",".join(sorted(slot_overlap)),
                ))

    for (path, function), contract in SEALED_PARAMETER_CONTRACTS.items():
        tree = trees.get(path)
        if tree is None:
            continue
        definition = _function_definitions(tree).get(function)
        if definition is None:
            continue
        parameters = _parameters(definition)
        for parameter, expected_annotation in contract.items():
            actual = parameters.get(parameter)
            actual_annotation = _annotation_text(actual) if actual is not None else "<missing>"
            if actual_annotation != expected_annotation:
                violations.append(Violation(
                    path,
                    function,
                    "RAW_CROSS_DOMAIN_PARAMETER",
                    f"{parameter}: {actual_annotation}",
                ))

    authority = trees.get("server/gear_exact_authority.py")
    if authority is not None:
        definitions = _function_definitions(authority)
        progression = definitions.get("seal_exact_progression")
        if progression is not None:
            calls = {
                node.func.id
                for node in ast.walk(progression)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            }
            for required in ("canonical_slot", "resolve_exact_instance_progression"):
                if required not in calls:
                    violations.append(Violation(
                        "server/gear_exact_authority.py",
                        "seal_exact_progression",
                        "MISSING_PRODUCTION_OWNER_CALL",
                        required,
                    ))
        envelope = definitions.get("seal_exact_authority_envelope")
        if envelope is not None:
            actual = set(_parameters(envelope))
            expected = {
                "exact", "static_facts", "progression", "effect_support",
                "resolver_revision",
            }
            if actual != expected:
                violations.append(Violation(
                    "server/gear_exact_authority.py",
                    "seal_exact_authority_envelope",
                    "SECOND_ENVELOPE_PAYLOAD",
                    ",".join(sorted(actual.difference(expected))),
                ))

    item = trees.get("server/gear_exact_item_instance.py")
    if item is not None:
        serializer = _function_definitions(item).get("derive_simc_serializer_input")
        if serializer is not None and set(_parameters(serializer)) != {"exact"}:
            violations.append(Violation(
                "server/gear_exact_item_instance.py",
                "derive_simc_serializer_input",
                "SECOND_SERIALIZER_PAYLOAD",
                ",".join(sorted(_parameters(serializer))),
            ))
    return sorted(set(violations))


class _DeletedNameVisitor(ast.NodeVisitor):
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

    def visit_Assign(self, node: ast.Assign) -> None:
        if any(
            isinstance(target, ast.Name) and target.id == "__all__"
            for target in node.targets
        ) and isinstance(node.value, (ast.Tuple, ast.List, ast.Set)):
            for element in node.value.elts:
                if isinstance(element, ast.Constant) and type(element.value) is str:
                    self._record(element.value, "DELETED_EXPORT")
        self.generic_visit(node)


def _repository_python_trees() -> dict[str, ast.AST]:
    trees: dict[str, ast.AST] = {}
    for directory in ("server", "scripts", "tests"):
        for path in sorted((ROOT / directory).rglob("*.py")):
            relative = path.relative_to(ROOT).as_posix()
            trees[relative] = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
    return trees


def _deleted_name_violations(trees: dict[str, ast.AST]) -> list[Violation]:
    violations: list[Violation] = []
    for path, tree in trees.items():
        visitor = _DeletedNameVisitor(path)
        visitor.visit(tree)
        violations.extend(visitor.violations)
    return sorted(set(violations))


def _formatted(violations: list[Violation]) -> str:
    return "\n".join(
        f"{item.path}:{item.function}:{item.code}:{item.detail}"
        for item in violations
    )


class GearCanonicalOwnerGateTest(unittest.TestCase):
    def test_repository_has_only_kernel_primitives_and_sealed_cross_domain_owners(self):
        trees = _repository_python_trees()
        violations = [
            *_consumer_violations({path: trees[path] for path in TASK2_CONSUMERS}),
            *_deleted_name_violations(trees),
        ]
        self.assertEqual([], violations, _formatted(violations))

    def test_gate_self_test_catches_wrong_paths_and_mutated_sealed_consumer(self):
        trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        missing = dict(trees)
        missing.pop("server/simc_item_effect_probe.py")
        self.assertTrue(any(
            item.code == "MISSING_SCAN_TARGET"
            and item.path == "server/simc_item_effect_probe.py"
            for item in _consumer_violations(missing)
        ))

        mutated = copy.deepcopy(trees)
        item_tree = mutated["server/gear_exact_item_instance.py"]
        serializer = _function_definitions(item_tree)["derive_simc_serializer_input"]
        serializer.body.insert(0, ast.Expr(ast.Call(
            func=ast.Name(id="str", ctx=ast.Load()),
            args=[ast.Name(id="exact", ctx=ast.Load())],
            keywords=[],
        )))
        serializer.body.insert(0, ast.Expr(ast.Call(
            func=ast.Name(id="catalog_lookup", ctx=ast.Load()),
            args=[ast.Name(id="exact", ctx=ast.Load())],
            keywords=[],
        )))
        violations = _consumer_violations(mutated)
        self.assertTrue(any(
            item.path == "server/gear_exact_item_instance.py"
            and item.function == "derive_simc_serializer_input"
            and item.code == "IDENTITY_COERCION"
            for item in violations
        ), _formatted(violations))
        self.assertTrue(any(
            item.path == "server/gear_exact_item_instance.py"
            and item.function == "derive_simc_serializer_input"
            and item.code == "CATALOG_DEPENDENCY"
            for item in violations
        ), _formatted(violations))

        authority_tree = mutated["server/gear_exact_authority.py"]
        authority_tree.body.append(ast.FunctionDef(
            name="build_raw_authority",
            args=ast.arguments(
                posonlyargs=[],
                args=[ast.arg(
                    arg="payload",
                    annotation=ast.Subscript(
                        value=ast.Name(id="Mapping", ctx=ast.Load()),
                        slice=ast.Tuple(elts=[
                            ast.Name(id="str", ctx=ast.Load()),
                            ast.Name(id="object", ctx=ast.Load()),
                        ], ctx=ast.Load()),
                        ctx=ast.Load(),
                    ),
                )],
                kwonlyargs=[], kw_defaults=[], defaults=[],
            ),
            body=[ast.Pass()],
            decorator_list=[],
        ))
        item_tree.body.append(ast.Assign(
            targets=[ast.Name(id="FORGED_SLOTS", ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id="frozenset", ctx=ast.Load()),
                args=[ast.Set(elts=[
                    ast.Constant("head"),
                    ast.Constant("chest"),
                    ast.Constant("feet"),
                ])],
                keywords=[],
            ),
        ))
        violations = _consumer_violations(mutated)
        self.assertTrue(any(
            item.function == "build_raw_authority"
            and item.code == "UNAPPROVED_PUBLIC_API"
            for item in violations
        ), _formatted(violations))
        self.assertTrue(any(
            item.path == "server/gear_exact_item_instance.py"
            and item.code == "DUPLICATE_SLOT_MEMBERSHIP"
            for item in violations
        ), _formatted(violations))


if __name__ == "__main__":
    unittest.main()
