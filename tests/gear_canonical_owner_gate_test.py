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


@dataclass(frozen=True)
class _ResolvedSymbol:
    qualified_name: str


@dataclass(frozen=True)
class _UnknownBinding:
    pass


@dataclass(frozen=True)
class _CallableTarget:
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
    label: str
    closure_scopes: tuple[dict[str, list[object]], ...]


_UNKNOWN_BINDING = _UnknownBinding()


def _argument_names(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda) -> set[str]:
    arguments = node.args
    names = {
        argument.arg
        for argument in (
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        )
    }
    if arguments.vararg is not None:
        names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        names.add(arguments.kwarg.arg)
    return names


class _ScopeBindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.bindings: dict[str, list[object]] = {}
        self.assignment_names: set[str] = set()

    def _add(self, name: str, value: object, *, assignment: bool = False) -> None:
        self.bindings.setdefault(name, []).append(value)
        if assignment:
            self.assignment_names.add(name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._add(node.name, node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._add(node.name, node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._add(node.name, _UNKNOWN_BINDING)

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._add(target.id, node.value, assignment=True)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
            self._add(node.target.id, node.value, assignment=True)
            self.visit(node.value)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".", 1)[0]
            qualified_name = alias.name if alias.asname else local_name
            self._add(local_name, _ResolvedSymbol(qualified_name))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            if alias.name == "*":
                continue
            local_name = alias.asname or alias.name
            qualified_name = f"{module}.{alias.name}" if module else alias.name
            self._add(local_name, _ResolvedSymbol(qualified_name))


def _scope_bindings(
    node: ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
) -> tuple[dict[str, list[object]], set[str]]:
    collector = _ScopeBindingCollector()
    if isinstance(node, ast.Module):
        statements = node.body
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for name in _argument_names(node):
            collector._add(name, _UNKNOWN_BINDING)
        statements = node.body
    else:
        for name in _argument_names(node):
            collector._add(name, _UNKNOWN_BINDING)
        statements = ()
    for statement in statements:
        collector.visit(statement)
    return collector.bindings, collector.assignment_names


def _resolve_expression(
    expression: object,
    scopes: tuple[dict[str, list[object]], ...],
    seen: frozenset[tuple[int, str]] = frozenset(),
) -> list[_ResolvedSymbol | _CallableTarget]:
    if isinstance(expression, _ResolvedSymbol):
        return [expression]
    if isinstance(expression, _UnknownBinding):
        return []
    if isinstance(expression, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return [_CallableTarget(expression, expression.name, scopes)]
    if isinstance(expression, ast.Lambda):
        return [_CallableTarget(expression, "<lambda>", scopes)]
    if isinstance(expression, ast.Name):
        for index, scope in enumerate(scopes):
            if expression.id not in scope:
                continue
            key = (id(scope), expression.id)
            if key in seen:
                return []
            resolved: list[_ResolvedSymbol | _CallableTarget] = []
            nested_scopes = scopes[index:]
            for value in scope[expression.id]:
                if isinstance(value, ast.Lambda):
                    resolved.append(_CallableTarget(
                        value,
                        expression.id,
                        nested_scopes,
                    ))
                elif isinstance(value, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    resolved.append(_CallableTarget(
                        value,
                        value.name,
                        nested_scopes,
                    ))
                else:
                    resolved.extend(_resolve_expression(
                        value,
                        nested_scopes,
                        seen | {key},
                    ))
            return resolved
        return [_ResolvedSymbol(expression.id)]
    if isinstance(expression, ast.Attribute):
        resolved = _resolve_expression(expression.value, scopes, seen)
        symbols = [
            _ResolvedSymbol(f"{item.qualified_name}.{expression.attr}")
            for item in resolved
            if isinstance(item, _ResolvedSymbol)
        ]
        if symbols:
            return symbols
        return [_ResolvedSymbol(ast.unparse(expression))]
    return []


class _DirectScopeUsage(ast.NodeVisitor):
    def __init__(self) -> None:
        self.calls: list[ast.Call] = []
        self.loaded_names: list[ast.Name] = []
        self.attributes: list[ast.Attribute] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Call(self, node: ast.Call) -> None:
        self.calls.append(node)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self.loaded_names.append(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.attributes.append(node)
        self.generic_visit(node)


def _direct_scope_usage(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
) -> _DirectScopeUsage:
    usage = _DirectScopeUsage()
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for statement in node.body:
            usage.visit(statement)
    else:
        usage.visit(node.body)
    return usage


def _called_targets(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    scopes: tuple[dict[str, list[object]], ...],
) -> list[_CallableTarget]:
    targets: list[_CallableTarget] = []
    for call in _direct_scope_usage(node).calls:
        targets.extend(
            item
            for item in _resolve_expression(call.func, scopes)
            if isinstance(item, _CallableTarget)
        )
    return targets


def _sealed_call_graph(
    tree: ast.AST,
    entrypoints: frozenset[str],
) -> tuple[
    dict[str, ast.FunctionDef | ast.AsyncFunctionDef],
    list[tuple[str, ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda, tuple[dict[str, list[object]], ...]]],
]:
    definitions = _function_definitions(tree)
    missing = set(entrypoints).difference(definitions)
    if missing:
        return definitions, []
    if not isinstance(tree, ast.Module):
        return definitions, []
    module_scope, _ = _scope_bindings(tree)
    pending: list[_CallableTarget] = []
    for entrypoint in sorted(entrypoints):
        pending.extend(
            item
            for item in _resolve_expression(
                ast.Name(id=entrypoint, ctx=ast.Load()),
                (module_scope,),
            )
            if isinstance(item, _CallableTarget)
        )
    reachable: list[
        tuple[
            str,
            ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
            tuple[dict[str, list[object]], ...],
        ]
    ] = []
    seen: set[tuple[int, tuple[int, ...]]] = set()
    while pending:
        target = pending.pop()
        key = (
            id(target.node),
            tuple(id(scope) for scope in target.closure_scopes),
        )
        if key in seen:
            continue
        seen.add(key)
        local_scope, _ = _scope_bindings(target.node)
        scopes = (local_scope, *target.closure_scopes)
        reachable.append((target.label, target.node, scopes))
        pending.extend(
            _called_targets(target.node, scopes)
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
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda,
    scopes: tuple[dict[str, list[object]], ...],
) -> list[Violation]:
    violations: list[Violation] = []
    usage = _direct_scope_usage(node)

    for loaded in usage.loaded_names:
        symbols = {
            item.qualified_name
            for item in _resolve_expression(loaded, scopes)
            if isinstance(item, _ResolvedSymbol)
        }
        for symbol in symbols:
            if "catalog" in symbol.lower():
                violations.append(Violation(
                    path,
                    function,
                    "CATALOG_DEPENDENCY",
                    symbol,
                ))

    for attribute in usage.attributes:
        symbols = {
            item.qualified_name
            for item in _resolve_expression(attribute, scopes)
            if isinstance(item, _ResolvedSymbol)
        }
        for symbol in symbols:
            if "catalog" in symbol.lower():
                violations.append(Violation(
                    path,
                    function,
                    "CATALOG_DEPENDENCY",
                    symbol,
                ))

    for child in usage.calls:
        callees = {
            item.qualified_name
            for item in _resolve_expression(child.func, scopes)
            if isinstance(item, _ResolvedSymbol)
        }
        if any(symbol.rsplit(".", 1)[-1] == "strip" for symbol in callees):
            violations.append(Violation(path, function, "IDENTITY_TRIM", ".strip()"))
        if any(symbol.rsplit(".", 1)[-1] == "str" for symbol in callees):
            violations.append(Violation(path, function, "IDENTITY_COERCION", "str(...)"))

        inner_callees: set[str] = set()
        if child.args and isinstance(child.args[0], ast.Call):
            inner_callees = {
                item.qualified_name
                for item in _resolve_expression(child.args[0].func, scopes)
                if isinstance(item, _ResolvedSymbol)
            }
        if (
            any(symbol.rsplit(".", 1)[-1] == "sorted" for symbol in callees)
            and any(symbol.rsplit(".", 1)[-1] == "set" for symbol in inner_callees)
        ):
            violations.append(
                Violation(path, function, "IDENTITY_SORT_DEDUPE", "sorted(set(...))")
            )
        if any(
            symbol == "json.dumps" or symbol.endswith(".json.dumps")
            for symbol in callees
        ):
            detail = "json.dumps(...)"
            if any(
                keyword.arg == "default"
                and any(
                    symbol.rsplit(".", 1)[-1] == "str"
                    for symbol in (
                        item.qualified_name
                        for item in _resolve_expression(keyword.value, scopes)
                        if isinstance(item, _ResolvedSymbol)
                    )
                )
                for keyword in child.keywords
            ):
                detail = "json.dumps(..., default=str)"
            violations.append(Violation(path, function, "DUPLICATE_JSON_OWNER", detail))
        for symbol in callees:
            if "hashlib" in symbol.lower().split("."):
                violations.append(Violation(
                    path,
                    function,
                    "DUPLICATE_HASH_OWNER",
                    symbol,
                ))
            if "catalog" in symbol.lower():
                violations.append(Violation(
                    path,
                    function,
                    "CATALOG_DEPENDENCY",
                    symbol,
                ))
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
        for function, callable_node, scopes in sorted(
            reachable,
            key=lambda item: item[0],
        ):
            if function in PRIMITIVE_OWNER_DEFINITIONS:
                violations.append(
                    Violation(path, function, "DUPLICATE_PRIMITIVE_OWNER", function)
                )
            violations.extend(
                _identity_primitive_violations(
                    path,
                    function,
                    callable_node,
                    scopes,
                )
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

        if isinstance(tree, ast.Module):
            module_scope, assignment_names = _scope_bindings(tree)
            for name in sorted(assignment_names):
                if name.startswith("_") or name in PUBLIC_FUNCTION_ALLOWLIST[path]:
                    continue
                resolved = _resolve_expression(
                    ast.Name(id=name, ctx=ast.Load()),
                    (module_scope,),
                )
                if any(isinstance(item, _CallableTarget) for item in resolved):
                    violations.append(Violation(
                        path,
                        name,
                        "UNAPPROVED_PUBLIC_API",
                        name,
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
            if alias.asname is not None:
                self._record(alias.asname, "DELETED_IMPORT")

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._record(alias.name, "DELETED_IMPORT")
            if alias.asname is not None:
                self._record(alias.asname, "DELETED_IMPORT")

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

    def test_gate_self_test_follows_callable_aliases_lambdas_and_import_asnames(self):
        trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        item_tree = trees["server/gear_exact_item_instance.py"]
        item_tree.body.extend(ast.parse("""
def _aliased_primitive_helper(value):
    coerce = str
    trim = value.strip
    canonical_sort = sorted
    deduplicate = set
    encode = json.dumps
    digest = hashlib.sha256
    catalog_first = catalog_lookup
    catalog_second = catalog_first
    coerce(value)
    trim()
    canonical_sort(deduplicate([value]))
    encode({"value": value}, default=coerce)
    digest(b"value")
    catalog_second(value)

_module_alias_first = _aliased_primitive_helper
_module_alias_second: object = _module_alias_first
_module_lambda = lambda value: catalog_lookup(str(value))
build_raw_lambda = lambda payload: payload
from safe_module import safe as build_exact_item_identity
import safe_module as valid_runtime_revision
""").body)
        serializer = _function_definitions(item_tree)["derive_simc_serializer_input"]
        serializer.body[:0] = ast.parse("""
_module_alias_second(exact)
_module_lambda(exact)
""").body

        violations = [
            *_consumer_violations(trees),
            *_deleted_name_violations(trees),
        ]
        observed = {
            (item.function, item.code, item.detail)
            for item in violations
            if item.path == "server/gear_exact_item_instance.py"
        }
        expected = {
            ("_aliased_primitive_helper", "IDENTITY_COERCION", "str(...)"),
            ("_aliased_primitive_helper", "IDENTITY_TRIM", ".strip()"),
            (
                "_aliased_primitive_helper",
                "IDENTITY_SORT_DEDUPE",
                "sorted(set(...))",
            ),
            (
                "_aliased_primitive_helper",
                "DUPLICATE_JSON_OWNER",
                "json.dumps(..., default=str)",
            ),
            (
                "_aliased_primitive_helper",
                "DUPLICATE_HASH_OWNER",
                "hashlib.sha256",
            ),
            (
                "_aliased_primitive_helper",
                "CATALOG_DEPENDENCY",
                "catalog_lookup",
            ),
            ("_module_lambda", "IDENTITY_COERCION", "str(...)"),
            ("_module_lambda", "CATALOG_DEPENDENCY", "catalog_lookup"),
            ("build_raw_lambda", "UNAPPROVED_PUBLIC_API", "build_raw_lambda"),
            ("<module>", "DELETED_IMPORT", "build_exact_item_identity"),
            ("<module>", "DELETED_IMPORT", "valid_runtime_revision"),
        }
        self.assertLessEqual(expected, observed, _formatted(violations))


if __name__ == "__main__":
    unittest.main()
