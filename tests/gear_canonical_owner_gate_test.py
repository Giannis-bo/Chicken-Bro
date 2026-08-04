import ast
import copy
from dataclasses import dataclass
import json
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

IMPORTED_CALLABLE_ALLOWLIST = {
    "server/gear_exact_item_instance.py": frozenset({
        "gear_canonical_kernel.CanonicalIssue",
        "gear_canonical_kernel.CanonicalResult",
        "gear_canonical_kernel.CanonicalValueError",
        "gear_canonical_kernel.canonical_identity_token",
        "gear_canonical_kernel.canonical_int",
        "gear_canonical_kernel.canonical_json_bytes",
        "gear_canonical_kernel.canonical_mapping",
        "gear_canonical_kernel.canonical_ordered_list",
        "gear_canonical_kernel.canonical_set_list",
        "gear_canonical_kernel.seal_canonical_document",
        "gear_canonical_kernel.verified_payload_copy",
        "gear_track_authority.resolve_exact_instance_progression",
        "math.isfinite",
    }),
    "server/gear_exact_authority.py": frozenset({
        "gear_canonical_kernel.CanonicalIssue",
        "gear_canonical_kernel.CanonicalResult",
        "gear_canonical_kernel.CanonicalValueError",
        "gear_canonical_kernel.canonical_identity_token",
        "gear_canonical_kernel.canonical_int",
        "gear_canonical_kernel.canonical_json_bytes",
        "gear_canonical_kernel.canonical_mapping",
        "gear_canonical_kernel.canonical_set_list",
        "gear_canonical_kernel.canonical_slot",
        "gear_canonical_kernel.seal_canonical_document",
        "gear_canonical_kernel.verified_payload_copy",
        "gear_exact_item_instance._verified_exact_payload_copy",
        "gear_exact_item_instance._validate_exact_item_payload",
        "gear_exact_item_instance._validate_exact_static_facts_payload",
        "gear_exact_item_instance.seal_exact_static_facts",
        "gear_track_authority.resolve_exact_instance_progression",
        "simc_item_effect_support._validate_effect_aggregate_payload",
    }),
    "server/simc_item_effect_support.py": frozenset({
        "datetime.datetime.fromisoformat",
        "gear_canonical_kernel.CanonicalIssue",
        "gear_canonical_kernel.CanonicalResult",
        "gear_canonical_kernel.CanonicalValueError",
        "gear_canonical_kernel.canonical_identity_token",
        "gear_canonical_kernel.canonical_mapping",
        "gear_canonical_kernel.canonical_ordered_list",
        "gear_canonical_kernel.canonical_report_token",
        "gear_canonical_kernel.seal_canonical_document",
        "gear_canonical_kernel.verified_payload_copy",
        "gear_canonical_kernel.verify_sealed_document",
        "gear_exact_item_instance._validate_exact_item_payload",
    }),
    "server/simc_item_effect_probe.py": frozenset({
        "gear_canonical_kernel.CanonicalIssue",
        "gear_canonical_kernel.CanonicalResult",
        "gear_canonical_kernel.CanonicalValueError",
        "gear_canonical_kernel.canonical_identity_token",
        "gear_canonical_kernel.canonical_int",
        "gear_canonical_kernel.canonical_mapping",
        "gear_canonical_kernel.canonical_ordered_list",
        "gear_canonical_kernel.canonical_report_token",
        "simc_item_effect_support._canonical_effect_tokens",
        "simc_item_effect_support._canonical_runtime",
        "simc_item_effect_support._canonical_snapshot_key",
        "simc_item_effect_support._canonical_subject_kind",
        "simc_item_effect_support._canonical_timestamp",
        "simc_item_effect_support._canonical_variant_signature",
        "simc_item_effect_support.seal_effect_record",
    }),
    "scripts/simc-item-effect-probe.py": frozenset({
        "json.loads",
        "math.isfinite",
        "pathlib.Path",
        "server.simc_item_effect_probe.evaluate_effect_probe",
        "sys.stderr.write",
        "sys.stdout.buffer.write",
    }),
}

CALLABLE_KEYWORD_ARGUMENTS = frozenset({
    "default",
    "item_rule",
    "key",
    "object_pairs_hook",
    "parse_constant",
    "parse_float",
    "parse_int",
    "payload_validator",
})

LOCAL_CALLABLE_ALLOWLIST = {
    "server/gear_exact_item_instance.py": frozenset({
        ("_bounded_exact_static_facts_payload", "len"),
        ("_canonical_exact_slot_payload", "len"),
        ("_canonical_exact_slot_payload", "list"),
        ("_canonical_exact_static_facts", "abs"),
        ("_canonical_exact_static_facts", "facts.items"),
        ("_canonical_exact_static_facts", "len"),
        ("_canonical_exact_static_facts", "raw_amount.is_integer"),
        ("_canonical_exact_static_facts", "type"),
        ("_require_exact_mapping_keys", "any"),
        ("_require_exact_mapping_keys", "exact_keys.difference"),
        ("_require_exact_mapping_keys", "set"),
        ("_require_exact_mapping_keys", "set(value).difference"),
        ("_require_exact_mapping_keys", "sorted"),
        ("_require_exact_mapping_keys", "type"),
        (
            "_validate_exact_static_facts_payload",
            "EXACT_ITEM_INSTANCE_KEY_PATTERN.fullmatch",
        ),
        ("_validate_exact_static_facts_payload", "dict"),
        ("_validate_exact_static_facts_payload", "type"),
        ("_validate_exact_static_facts_payload", "value.get"),
        ("_validate_exact_item_payload", "dict"),
        ("derive_simc_serializer_input", "'/'.join"),
    }),
    "server/gear_exact_authority.py": frozenset({
        ("_validate_exact_progression_payload", "dict"),
        ("_validate_exact_progression_payload", "list"),
        ("_validate_exact_progression_payload", "resolved.get"),
        ("_validate_exact_progression_payload", "type"),
        ("_validate_effect_aggregate_for_envelope", "type"),
        ("_validate_effect_aggregate_for_envelope", "value.get"),
        ("seal_exact_authority_envelope", "TypeError"),
        ("seal_exact_authority_envelope", "documents.items"),
        ("seal_exact_authority_envelope", "type"),
        ("seal_exact_progression", "list"),
        ("seal_exact_progression", "problem.get"),
        ("seal_exact_progression", "resolved.get"),
        ("seal_exact_progression", "tuple"),
        ("seal_exact_progression", "type"),
    }),
    "server/simc_item_effect_support.py": frozenset({
        ("_canonical_effect_tokens", "len"),
        ("_canonical_effect_tokens", "list"),
        ("_canonical_effect_tokens", "sum"),
        ("_canonical_effect_tokens", "token.encode"),
        ("_canonical_snapshot_key", "_SNAPSHOT_KEY_PATTERN.fullmatch"),
        ("_canonical_timestamp", "timestamp.endswith"),
        ("_canonical_variant_signature", "_VARIANT_SIGNATURE_PATTERN.fullmatch"),
        ("_validate_effect_aggregate_payload", "_EXACT_KEY_PATTERN.fullmatch"),
        ("_validate_effect_aggregate_payload", "_RECORD_KEY_PATTERN.fullmatch"),
        ("_validate_effect_aggregate_payload", "dict"),
        ("_validate_effect_aggregate_payload", "enumerate"),
        ("_validate_effect_aggregate_payload", "len"),
        ("_validate_effect_aggregate_payload", "rebuilt_records.append"),
        ("_validate_effect_aggregate_payload", "rebuilt_subjects.append"),
        ("_validate_effect_aggregate_payload", "record.pop"),
        ("_validate_effect_aggregate_payload", "zip"),
        ("_validate_effect_record_payload", "dict"),
        ("_validate_effect_record_payload", "rebuilt.update"),
        ("_validate_effect_record_payload", "type"),
        ("_validate_effect_record_payload", "value.get"),
        ("<lambda>@541:18", "frozenset"),
        ("<lambda>@541:18", "frozenset(record).union"),
        ("<lambda>@541:18", "type"),
        ("derive_exact_effect_subjects", "enumerate"),
        ("derive_exact_effect_subjects", "list"),
        ("derive_exact_effect_subjects", "subjects.append"),
        ("derive_exact_effect_subjects", "tuple"),
        ("resolve_exact_effect_support", "aggregate_records.append"),
        ("resolve_exact_effect_support", "aggregate_subjects.append"),
        ("resolve_exact_effect_support", "enumerate"),
        ("resolve_exact_effect_support", "expected_positions.get"),
        ("resolve_exact_effect_support", "isinstance"),
    }),
    "server/simc_item_effect_probe.py": frozenset({
        ("_canonical_warnings", "len"),
        ("_canonical_warnings", "list"),
        ("_canonical_warnings", "sum"),
        ("_canonical_warnings", "warning.encode"),
        ("_validate_manifest", "dict"),
        ("_validate_report", "dict"),
        ("_validate_report", "type"),
        ("evaluate_effect_probe", "any"),
        ("evaluate_effect_probe", "next"),
        ("evaluate_effect_probe", "type"),
    }),
    "scripts/simc-item-effect-probe.py": frozenset({
        ("_read", "Path(path).read_text"),
        ("_parse_bounded_int", "int"),
        ("_parse_bounded_int", "len"),
        ("_parse_bounded_int", "value.startswith"),
        ("_parse_finite_float", "float"),
        ("main", "parser.add_argument"),
        ("main", "parser.parse_args"),
        ("main", "result.status.upper"),
    }),
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
    imported: bool = False


@dataclass(frozen=True)
class _UnknownBinding:
    pass


@dataclass(frozen=True)
class _UnknownValue:
    detail: str


@dataclass(frozen=True)
class _CallableTarget:
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
    label: str
    closure_scopes: tuple[dict[str, list[object]], ...]
    argument_bindings: tuple[tuple[str, tuple[object, ...]], ...] = ()


@dataclass(frozen=True)
class _ClassTarget:
    node: ast.ClassDef
    label: str
    closure_scopes: tuple[dict[str, list[object]], ...]


_UNKNOWN_BINDING = _UnknownBinding()


def _lambda_label(node: ast.Lambda) -> str:
    return f"<lambda>@{node.lineno}:{node.col_offset}"


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
        self._add(node.name, node)

    def _add_assignment_target(self, target: ast.expr, value: object) -> None:
        if isinstance(target, ast.Name):
            self._add(target.id, value, assignment=True)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            source_values: tuple[object, ...] | None = None
            if isinstance(value, (ast.Tuple, ast.List)):
                source_values = tuple(value.elts)
            if source_values is not None and len(source_values) == len(target.elts):
                for child, source in zip(target.elts, source_values, strict=True):
                    self._add_assignment_target(child, source)
                return
            for child in target.elts:
                self._add_assignment_target(
                    child,
                    _UnknownValue(f"unpacked assignment: {ast.unparse(target)}"),
                )

    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            self._add_assignment_target(target, node.value)
        self.visit(node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
            self._add(node.target.id, node.value, assignment=True)
            self.visit(node.value)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        self._add_assignment_target(node.target, node.value)
        self.visit(node.value)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            local_name = alias.asname or alias.name.split(".", 1)[0]
            qualified_name = alias.name if alias.asname else local_name
            self._add(local_name, _ResolvedSymbol(qualified_name, imported=True))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            if alias.name == "*":
                continue
            local_name = alias.asname or alias.name
            qualified_name = f"{module}.{alias.name}" if module else alias.name
            self._add(local_name, _ResolvedSymbol(qualified_name, imported=True))


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
) -> list[_ResolvedSymbol | _CallableTarget | _ClassTarget | _UnknownValue]:
    if isinstance(expression, _ResolvedSymbol):
        return [expression]
    if isinstance(expression, _CallableTarget):
        return [expression]
    if isinstance(expression, _ClassTarget):
        return [expression]
    if isinstance(expression, _UnknownValue):
        return [expression]
    if isinstance(expression, _UnknownBinding):
        return [_UnknownValue("dynamic parameter")]
    if isinstance(expression, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return [_CallableTarget(expression, expression.name, scopes)]
    if isinstance(expression, ast.ClassDef):
        return [_ClassTarget(expression, expression.name, scopes)]
    if isinstance(expression, ast.Lambda):
        return [_CallableTarget(expression, _lambda_label(expression), scopes)]
    if isinstance(expression, ast.Name):
        for index, scope in enumerate(scopes):
            if expression.id not in scope:
                continue
            key = (id(scope), expression.id)
            if key in seen:
                return []
            resolved: list[
                _ResolvedSymbol | _CallableTarget | _ClassTarget | _UnknownValue
            ] = []
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
        class_targets = [
            item for item in resolved if isinstance(item, _ClassTarget)
        ]
        class_members: list[_CallableTarget | _UnknownValue] = []
        for target in class_targets:
            methods = [
                statement
                for statement in target.node.body
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
                and statement.name == expression.attr
            ]
            if methods:
                class_members.extend(
                    _CallableTarget(
                        method,
                        f"{target.label}.{expression.attr}",
                        target.closure_scopes,
                    )
                    for method in methods
                )
            else:
                class_members.append(_UnknownValue(ast.unparse(expression)))
        if class_members:
            return class_members
        symbols = [
            _ResolvedSymbol(
                f"{item.qualified_name}.{expression.attr}",
                imported=item.imported,
            )
            for item in resolved
            if isinstance(item, _ResolvedSymbol)
        ]
        if symbols:
            return symbols
        return [_ResolvedSymbol(ast.unparse(expression))]
    if isinstance(expression, ast.IfExp):
        return [
            *_resolve_expression(expression.body, scopes, seen),
            *_resolve_expression(expression.orelse, scopes, seen),
        ]
    if isinstance(expression, ast.NamedExpr):
        return _resolve_expression(expression.value, scopes, seen)
    if isinstance(expression, ast.BoolOp):
        return [
            item
            for value in expression.values
            for item in _resolve_expression(value, scopes, seen)
        ]
    if isinstance(expression, ast.AST):
        return [_UnknownValue(ast.unparse(expression))]
    return [_UnknownValue(type(expression).__name__)]


def _resolve_callable_expression(
    expression: ast.expr,
    scopes: tuple[dict[str, list[object]], ...],
) -> list[_ResolvedSymbol | _CallableTarget | _ClassTarget | _UnknownValue]:
    resolved = _resolve_expression(expression, scopes)
    if resolved:
        return resolved
    return [_UnknownValue(ast.unparse(expression))]


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
        for item in _resolve_callable_expression(call.func, scopes):
            if isinstance(item, _CallableTarget):
                targets.append(_bind_callable_target(item, call, scopes))
            elif isinstance(item, _ClassTarget):
                for statement in item.node.body:
                    if (
                        isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
                        and statement.name in {"__new__", "__init__"}
                    ):
                        targets.append(_CallableTarget(
                            statement,
                            f"{item.label}.{statement.name}",
                            item.closure_scopes,
                        ))
        for argument in (
            *call.args,
            *(keyword.value for keyword in call.keywords),
        ):
            targets.extend(
                item
                for item in _resolve_expression(argument, scopes)
                if isinstance(item, _CallableTarget)
            )
    return targets


def _resolved_argument_values(
    expression: ast.expr,
    scopes: tuple[dict[str, list[object]], ...],
) -> tuple[object, ...]:
    resolved = tuple(_resolve_expression(expression, scopes))
    if resolved:
        return resolved
    return (_UnknownValue(ast.unparse(expression)),)


def _bind_callable_target(
    target: _CallableTarget,
    call: ast.Call,
    caller_scopes: tuple[dict[str, list[object]], ...],
) -> _CallableTarget:
    arguments = target.node.args
    positional = [*arguments.posonlyargs, *arguments.args]
    keyword_capable = {
        argument.arg
        for argument in (*arguments.args, *arguments.kwonlyargs)
    }
    bindings: dict[str, tuple[object, ...]] = {}
    for index, value in enumerate(call.args):
        if index >= len(positional) or isinstance(value, ast.Starred):
            continue
        bindings[positional[index].arg] = _resolved_argument_values(
            value,
            caller_scopes,
        )
    for keyword in call.keywords:
        if keyword.arg is None or keyword.arg not in keyword_capable:
            continue
        bindings[keyword.arg] = _resolved_argument_values(
            keyword.value,
            caller_scopes,
        )

    positional_defaults = positional[len(positional) - len(arguments.defaults):]
    for argument, default in zip(positional_defaults, arguments.defaults):
        if argument.arg not in bindings:
            bindings[argument.arg] = _resolved_argument_values(
                default,
                target.closure_scopes,
            )
    for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults):
        if default is not None and argument.arg not in bindings:
            bindings[argument.arg] = _resolved_argument_values(
                default,
                target.closure_scopes,
            )
    return _CallableTarget(
        target.node,
        target.label,
        target.closure_scopes,
        tuple(sorted(bindings.items())),
    )


def _binding_identity(target: _CallableTarget) -> tuple[object, ...]:
    identities: list[object] = []
    for name, values in target.argument_bindings:
        value_identities: list[object] = []
        for value in values:
            if isinstance(value, _ResolvedSymbol):
                value_identities.append(
                    ("symbol", value.qualified_name, value.imported)
                )
            elif isinstance(value, _CallableTarget):
                value_identities.append(("callable", id(value.node)))
            elif isinstance(value, _ClassTarget):
                value_identities.append(("class", id(value.node)))
            elif isinstance(value, _UnknownValue):
                value_identities.append(("unknown", value.detail))
        identities.append((name, tuple(value_identities)))
    return tuple(identities)


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
    seen: set[tuple[int, tuple[int, ...], tuple[object, ...]]] = set()
    while pending:
        target = pending.pop()
        key = (
            id(target.node),
            tuple(id(scope) for scope in target.closure_scopes),
            _binding_identity(target),
        )
        if key in seen:
            continue
        seen.add(key)
        local_scope, _ = _scope_bindings(target.node)
        for name, values in target.argument_bindings:
            local_scope[name] = [
                *values,
                *(
                    value
                    for value in local_scope.get(name, ())
                    if not isinstance(value, _UnknownBinding)
                ),
            ]
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
        resolved_callables = _resolve_callable_expression(child.func, scopes)
        resolved_callees = {
            item
            for item in resolved_callables
            if isinstance(item, _ResolvedSymbol)
        }
        for item in resolved_callables:
            if isinstance(item, _UnknownValue):
                violations.append(Violation(
                    path,
                    function,
                    "UNKNOWN_DYNAMIC_CALLABLE",
                    ast.unparse(child.func),
                ))
        callees = {item.qualified_name for item in resolved_callees}
        allowed_imported = IMPORTED_CALLABLE_ALLOWLIST[path]
        allowed_local = LOCAL_CALLABLE_ALLOWLIST[path]
        for keyword in child.keywords:
            if keyword.arg not in CALLABLE_KEYWORD_ARGUMENTS:
                continue
            callback_values = _resolve_callable_expression(
                keyword.value,
                scopes,
            )
            for callback in callback_values:
                if isinstance(callback, _UnknownValue):
                    violations.append(Violation(
                        path,
                        function,
                        "UNKNOWN_DYNAMIC_CALLABLE",
                        ast.unparse(keyword.value),
                    ))
                elif isinstance(callback, _ResolvedSymbol):
                    normalized_callback = callback.qualified_name.lstrip(".")
                    if (
                        callback.imported
                        and normalized_callback not in allowed_imported
                    ):
                        violations.append(Violation(
                            path,
                            function,
                            "UNAPPROVED_IMPORTED_CALLABLE",
                            normalized_callback,
                        ))
                    elif (
                        not callback.imported
                        and (function, normalized_callback) not in allowed_local
                    ):
                        violations.append(Violation(
                            path,
                            function,
                            "UNKNOWN_DYNAMIC_CALLABLE",
                            ast.unparse(keyword.value),
                        ))
        for item in resolved_callees:
            normalized = item.qualified_name.lstrip(".")
            if item.imported and normalized not in allowed_imported:
                violations.append(Violation(
                    path,
                    function,
                    "UNAPPROVED_IMPORTED_CALLABLE",
                    normalized,
                ))
            if (
                not item.imported
                and (function, normalized) not in allowed_local
                and normalized.rsplit(".", 1)[-1] not in {"str", "strip"}
                and not (
                    normalized == "json.dumps"
                    or normalized.endswith(".json.dumps")
                    or "hashlib" in normalized.lower().split(".")
                    or "catalog" in normalized.lower()
                )
            ):
                violations.append(Violation(
                    path,
                    function,
                    "UNKNOWN_DYNAMIC_CALLABLE",
                    ast.unparse(child.func),
                ))
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

    def test_gate_self_test_rejects_unknown_imported_callables(self):
        trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        item_tree = trees["server/gear_exact_item_instance.py"]
        item_tree.body.extend(ast.parse("""
from plugin_a import helper as hidden_str
from plugin_b import helper as hidden_strip
from plugin_c import helper as hidden_hash
from plugin_d import helper as hidden_json
from plugin_e import helper as hidden_catalog
from plugin_f import helper as hidden_unknown
import plugin_g as hidden_module
""").body)
        serializer = _function_definitions(item_tree)["derive_simc_serializer_input"]
        serializer.body[:0] = ast.parse("""
hidden_str(exact)
hidden_strip(exact)
hidden_hash(exact)
hidden_json(exact)
hidden_catalog(exact)
hidden_unknown(exact)
hidden_module.helper(exact)
""").body

        violations = _consumer_violations(trees)
        observed = {
            (item.code, item.detail)
            for item in violations
            if item.path == "server/gear_exact_item_instance.py"
            and item.function == "derive_simc_serializer_input"
        }
        expected = {
            ("UNAPPROVED_IMPORTED_CALLABLE", f"plugin_{suffix}.helper")
            for suffix in "abcdefg"
        }
        self.assertLessEqual(expected, observed, _formatted(violations))

    def test_gate_follows_higher_order_callbacks_and_blocks_unknown_invocation(self):
        trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        item_tree = trees["server/gear_exact_item_instance.py"]
        item_tree.body.extend(ast.parse("""
from builtins import str as hidden_str
from server.hidden_strip import strip as hidden_strip
from hashlib import sha256 as hidden_hash
from json import dumps as hidden_json
from server.hidden_catalog import lookup as hidden_catalog
from server.hidden_unknown import helper as hidden_unknown
from server.hidden_conditional_a import normalize as hidden_conditional_a
from server.hidden_conditional_b import normalize as hidden_conditional_b

def _invoke(callback, value):
    return callback(value)

def _forward(callback, value):
    return _invoke(callback, value)

def _invoke_default(value, callback=hidden_json):
    return callback(value)

_callback_lambda = lambda callback, value: _forward(callback, value)
""").body)
        serializer = _function_definitions(item_tree)["derive_simc_serializer_input"]
        serializer.body[:0] = ast.parse("""
_invoke(hidden_str, exact)
_forward(hidden_strip, exact)
_invoke(callback=hidden_hash, value=exact)
_invoke_default(exact)
_callback_lambda(hidden_catalog, exact)
_invoke(hidden_unknown, exact)
_invoke(exact, exact)
conditional = hidden_conditional_a if exact else hidden_conditional_b
conditional(exact)
""").body

        violations = _consumer_violations(trees)
        observed = {
            (item.function, item.code, item.detail)
            for item in violations
            if item.path == "server/gear_exact_item_instance.py"
        }
        for detail in (
            "builtins.str",
            "server.hidden_strip.strip",
            "hashlib.sha256",
            "json.dumps",
            "server.hidden_catalog.lookup",
            "server.hidden_unknown.helper",
            "server.hidden_conditional_a.normalize",
            "server.hidden_conditional_b.normalize",
        ):
            self.assertTrue(any(
                code == "UNAPPROVED_IMPORTED_CALLABLE" and found_detail == detail
                for _, code, found_detail in observed
            ), _formatted(violations))
        for code in (
            "IDENTITY_COERCION",
            "IDENTITY_TRIM",
            "DUPLICATE_HASH_OWNER",
            "DUPLICATE_JSON_OWNER",
            "CATALOG_DEPENDENCY",
            "UNKNOWN_DYNAMIC_CALLABLE",
        ):
            self.assertTrue(any(
                found_code == code
                for _, found_code, _ in observed
            ), _formatted(violations))

    def test_gate_fails_closed_for_dynamic_callable_expressions(self):
        base_trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        setup = """
from builtins import str as hidden_str
from server.hidden_strip import strip as hidden_strip
from hashlib import sha256 as hidden_hash
from json import dumps as hidden_json
from server.hidden_catalog import lookup as hidden_catalog
from server.hidden_unknown import helper as hidden_unknown
"""
        cases = {
            "tuple subscript": "(hidden_str,)[0](exact)",
            "list subscript": "[hidden_strip][0](exact)",
            "dict subscript": '{"hash": hidden_hash}["hash"](exact)',
            "walrus callable": "(callback := hidden_json)(exact)",
            "boolean callable": "(hidden_catalog or hidden_unknown)(exact)",
            "getattr bound method": 'getattr(exact, "strip")()',
            "unbound helper": "hidden_runtime_helper(exact)",
            "unknown bound method": "exact.hidden_helper()",
        }
        for label, invocation in cases.items():
            with self.subTest(label=label):
                trees = copy.deepcopy(base_trees)
                item_tree = trees["server/gear_exact_item_instance.py"]
                item_tree.body.extend(ast.parse(setup).body)
                serializer = _function_definitions(item_tree)[
                    "derive_simc_serializer_input"
                ]
                serializer.body[:0] = ast.parse(invocation).body
                violations = [
                    item
                    for item in _consumer_violations(trees)
                    if item.path == "server/gear_exact_item_instance.py"
                    and item.function == "derive_simc_serializer_input"
                ]
                self.assertTrue(any(
                    item.code in {
                        "UNKNOWN_DYNAMIC_CALLABLE",
                        "UNAPPROVED_IMPORTED_CALLABLE",
                    }
                    for item in violations
                ), f"{label}\n{_formatted(violations)}")

    def test_gate_fails_closed_for_container_unpacking_and_alias_chains(self):
        base_trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        setup = """
from builtins import str as hidden_str
from server.hidden_strip import strip as hidden_strip
from hashlib import sha256 as hidden_hash
from json import dumps as hidden_json
from server.hidden_catalog import lookup as hidden_catalog
from server.hidden_unknown import helper as hidden_unknown
"""
        cases = {
            "tuple alias chain": """
_callbacks = (hidden_str, hidden_strip)
_callbacks_alias = _callbacks
_callbacks_alias[0](exact)
""",
            "list alias chain": """
_callbacks = [hidden_hash, hidden_json]
_callbacks_alias = _callbacks
_callbacks_alias[1](exact)
""",
            "dict alias chain": """
_callbacks = {"catalog": hidden_catalog, "unknown": hidden_unknown}
_callbacks_alias = _callbacks
_callbacks_alias["catalog"](exact)
""",
            "unpacked alias": """
_callbacks = (hidden_str, hidden_strip)
_first, _second = _callbacks
_first(exact)
""",
            "walrus later alias": """
(callback := hidden_json)
callback(exact)
""",
        }
        for label, body in cases.items():
            with self.subTest(label=label):
                trees = copy.deepcopy(base_trees)
                item_tree = trees["server/gear_exact_item_instance.py"]
                item_tree.body.extend(ast.parse(setup).body)
                serializer = _function_definitions(item_tree)[
                    "derive_simc_serializer_input"
                ]
                serializer.body[:0] = ast.parse(body).body
                violations = [
                    item
                    for item in _consumer_violations(trees)
                    if item.path == "server/gear_exact_item_instance.py"
                    and item.function == "derive_simc_serializer_input"
                ]
                self.assertTrue(any(
                    item.code in {
                        "UNKNOWN_DYNAMIC_CALLABLE",
                        "UNAPPROVED_IMPORTED_CALLABLE",
                    }
                    for item in violations
                ), f"{label}\n{_formatted(violations)}")

    def test_gate_fails_closed_for_returned_and_wrapped_callables(self):
        base_trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        setup = """
import functools
from builtins import str as hidden_str
from json import dumps as hidden_json

def _factory(callback):
    return callback

def _lambda_wrapper(callback, value):
    return (lambda callbacks: callbacks[0](value))((callback,))
"""
        cases = {
            "factory return": (
                "_factory(hidden_str)(exact)",
                "_factory(hidden_str)",
            ),
            "partial return": (
                "functools.partial(hidden_str)(exact)",
                "functools.partial(hidden_str)",
            ),
            "lambda subscript callback": (
                "_lambda_wrapper(hidden_json, exact)",
                "callbacks[0]",
            ),
        }
        for label, (invocation, dynamic_callable) in cases.items():
            with self.subTest(label=label):
                trees = copy.deepcopy(base_trees)
                item_tree = trees["server/gear_exact_item_instance.py"]
                item_tree.body.extend(ast.parse(setup).body)
                serializer = _function_definitions(item_tree)[
                    "derive_simc_serializer_input"
                ]
                serializer.body[:0] = ast.parse(invocation).body
                violations = [
                    item
                    for item in _consumer_violations(trees)
                    if item.path == "server/gear_exact_item_instance.py"
                ]
                self.assertTrue(any(
                    item.code == "UNKNOWN_DYNAMIC_CALLABLE"
                    and item.detail == dynamic_callable
                    for item in violations
                ), f"{label}\n{_formatted(violations)}")

    def test_gate_follows_local_staticmethods_and_blocks_local_instances(self):
        base_trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        setup = """
from builtins import str as hidden_str
from server.hidden_strip import strip as hidden_strip

class _HiddenStatic:
    @staticmethod
    def invoke(value):
        return hidden_str(value)

class _HiddenCallable:
    def __call__(self, value):
        return hidden_strip(value)
"""
        cases = {
            "local staticmethod": ("_HiddenStatic.invoke(exact)", False),
            "local callable instance": ("_HiddenCallable()(exact)", True),
            "local callable alias": (
                "callback = _HiddenCallable()\ncallback(exact)",
                True,
            ),
        }
        for label, (body, expects_unknown) in cases.items():
            with self.subTest(label=label):
                trees = copy.deepcopy(base_trees)
                item_tree = trees["server/gear_exact_item_instance.py"]
                item_tree.body.extend(ast.parse(setup).body)
                serializer = _function_definitions(item_tree)[
                    "derive_simc_serializer_input"
                ]
                serializer.body[:0] = ast.parse(body).body
                violations = [
                    item
                    for item in _consumer_violations(trees)
                    if item.path == "server/gear_exact_item_instance.py"
                ]
                if expects_unknown:
                    self.assertTrue(any(
                        item.code == "UNKNOWN_DYNAMIC_CALLABLE"
                        for item in violations
                    ), f"{label}\n{_formatted(violations)}")
                else:
                    self.assertTrue(any(
                        item.code in {
                            "IDENTITY_COERCION",
                            "UNAPPROVED_IMPORTED_CALLABLE",
                        }
                        and item.detail in {"str(...)", "builtins.str"}
                        for item in violations
                    ), f"{label}\n{_formatted(violations)}")

    def test_gate_does_not_approve_local_callable_by_spelling_in_another_helper(self):
        trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        item_tree = trees["server/gear_exact_item_instance.py"]
        item_tree.body.extend(ast.parse("""
def _shadow_safe_spelling(value):
    return value.get("hidden")
""").body)
        serializer = _function_definitions(item_tree)[
            "derive_simc_serializer_input"
        ]
        serializer.body.insert(0, ast.parse("_shadow_safe_spelling(exact)").body[0])

        violations = _consumer_violations(trees)
        self.assertTrue(any(
            item.path == "server/gear_exact_item_instance.py"
            and item.function == "_shadow_safe_spelling"
            and item.code == "UNKNOWN_DYNAMIC_CALLABLE"
            and item.detail == "value.get"
            for item in violations
        ), _formatted(violations))

    def test_gate_follows_inline_lambda_passed_to_an_approved_owner(self):
        trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        item_tree = trees["server/gear_exact_item_instance.py"]
        item_tree.body.extend(ast.parse("""
from builtins import str as hidden_str
""").body)
        serializer = _function_definitions(item_tree)[
            "derive_simc_serializer_input"
        ]
        serializer.body.insert(0, ast.parse("""
canonical_ordered_list(
    [],
    path="hidden",
    item_rule=lambda value, path: (hidden_str,)[0](value),
)
""").body[0])

        violations = _consumer_violations(trees)
        self.assertTrue(any(
            item.path == "server/gear_exact_item_instance.py"
            and item.function.startswith("<lambda>@")
            and item.code == "UNKNOWN_DYNAMIC_CALLABLE"
            and item.detail == "(hidden_str,)[0]"
            for item in violations
        ), _formatted(violations))

    def test_gate_rejects_an_imported_callable_passed_to_an_approved_owner(self):
        trees = {
            path: ast.parse((ROOT / path).read_text(encoding="utf-8"), filename=path)
            for path in TASK2_CONSUMERS
        }
        item_tree = trees["server/gear_exact_item_instance.py"]
        item_tree.body.extend(ast.parse("""
from server.hidden_owner import normalize as hidden_callback
""").body)
        serializer = _function_definitions(item_tree)[
            "derive_simc_serializer_input"
        ]
        serializer.body.insert(0, ast.parse("""
canonical_ordered_list(
    [],
    path="hidden",
    item_rule=hidden_callback,
)
""").body[0])

        violations = _consumer_violations(trees)
        self.assertTrue(any(
            item.path == "server/gear_exact_item_instance.py"
            and item.function == "derive_simc_serializer_input"
            and item.code == "UNAPPROVED_IMPORTED_CALLABLE"
            and item.detail == "server.hidden_owner.normalize"
            for item in violations
        ), _formatted(violations))

    def test_task5_control_plane_matches_the_implemented_pure_foundation(self):
        requirement = json.loads((
            ROOT
            / "artifacts/releases/2026-08-04-equipment-simulator-exact-first/requirement.json"
        ).read_text(encoding="utf-8"))
        self.assertEqual(requirement["status"], "implementation_allowed")
        must_change = "\n".join(requirement["impactMap"]["mustChange"])
        for owner in (
            "gear_canonical_kernel.py",
            "gear_contracts.py",
            "gear-intent.ts",
            "gear_canonical_mutations.json",
            "gear_exact_item_instance.py",
            "gear_exact_authority.py",
            "simc_item_effect_support.py",
            "simc_item_effect_probe.py",
            "simc-item-effect-probe.py",
            "gear_canonical_owner_gate_test.py",
        ):
            self.assertIn(owner, must_change)
        must_not_change = "\n".join(requirement["impactMap"]["mustNotChange"])
        for boundary in (
            "generation 35", "Catalog", "pointer", "persistence", "worker",
            "Resolver", "API", "UI", "raw plugin", "v1",
        ):
            self.assertIn(boundary, must_not_change)
        evidence = "\n".join(requirement["impactMap"]["evidenceRequired"])
        self.assertIn("Task 1-5", evidence)
        self.assertIn("owner gate", evidence)
        self.assertNotIn("candidate", evidence.lower())
        self.assertNotIn("wechat", evidence.lower())
        self.assertEqual(requirement["ownership"]["runtimeConsumers"], [])
        self.assertFalse(requirement["ownership"]["originalTask3Activated"])
        self.assertEqual(
            requirement["engineeringHealth"]["status"],
            "implementation_allowed",
        )
        self.assertIn("Task 1-5", requirement["decisionLog"][-1]["decision"])

        project_map = json.loads(
            (ROOT / "docs/project-owner-map.json").read_text(encoding="utf-8")
        )
        gear_domain = next(
            domain
            for domain in project_map["criticalDomains"]
            if "canonicalKernelFoundations" in domain
        )
        project_boundary = gear_domain["canonicalKernelFoundations"][
            "activationBoundary"
        ]
        self.assertNotIn("pending controller", project_boundary.lower())
        self.assertIn("original Task 3 is not activated", project_boundary)

        backend_map = json.loads(
            (ROOT / "docs/backend-owner-map.json").read_text(encoding="utf-8")
        )
        kernel_hotspot = next(
            hotspot
            for hotspot in backend_map["hotspotFiles"]
            if hotspot["path"] == "server/gear_canonical_kernel.py"
        )
        kernel_owner = kernel_hotspot["owners"][0]
        self.assertNotIn(
            "pending controller",
            kernel_owner["capabilityBoundary"].lower(),
        )
        self.assertIn(
            "original Task 3 is not activated",
            kernel_owner["capabilityBoundary"],
        )

        exact_foundation = gear_domain["exactItemInstanceFoundations"]
        catalog_hotspot = next(
            hotspot
            for hotspot in backend_map["hotspotFiles"]
            if hotspot["path"] == "server/gear_catalog_migration_audit.py"
        )
        exact_owner = next(
            owner
            for owner in catalog_hotspot["owners"]
            if owner["id"] == "equipment_simulator_exact_item_instance_phase2"
        )
        import_hotspot = next(
            hotspot
            for hotspot in backend_map["hotspotFiles"]
            if hotspot["path"] == "server/simc_gear_import.py"
        )
        import_owner = import_hotspot["owners"][0]
        current_control_plane = json.dumps(
            [
                requirement,
                gear_domain["canonicalKernelFoundations"],
                exact_foundation,
                kernel_owner,
                exact_owner,
                import_owner,
            ],
            ensure_ascii=False,
            sort_keys=True,
        ).lower()
        for stale_narrative in (
            "task1_contract_only",
            "task 1 only",
            "task 1 仅",
            "task 2 consumes only",
            "replacement task 2",
            "later tasks own authority",
            "future exact authority",
            "pending controller",
        ):
            self.assertNotIn(stale_narrative, current_control_plane)
        import_boundary = import_owner["capabilityBoundary"]
        self.assertIn("Replacement Task 1-5", import_boundary)
        self.assertIn("original Task 3 is not activated", import_boundary)
        self.assertIn(
            "persistence/store/migration/worker/runtime activation",
            import_boundary,
        )


if __name__ == "__main__":
    unittest.main()
