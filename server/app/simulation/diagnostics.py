"""Bounded engine diagnostic categories; raw log messages remain private."""

_LEVELS = frozenset({
    'implementation_not_yet_verified', 'using_unverified_values',
    'not_yet_implemented', 'implementation_notes', 'moderate', 'severe',
})


def public_engine_diagnostics(value):
    if not isinstance(value, list):
        return []
    return sorted({code for code in value[:256] if isinstance(code, str) and code in _LEVELS})


def engine_diagnostic_limitations(value):
    codes = public_engine_diagnostics(value)
    if not codes:
        return []
    return ['The engine reported simulation caveats (' + ', '.join(codes) +
            '). Reported sampling error does not include uncertainty in mechanics or their implementation.']
