#!/usr/bin/env python3
"""Append-only PostgreSQL owner for complete Exact Authority Bundles."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from server.gear_canonical_kernel import SealedCanonicalDocument
from server.gear_exact_item_instance import (
    reload_exact_item,
    reload_exact_static_facts,
)
from server.gear_exact_authority import (
    reload_exact_authority_envelope,
    reload_exact_progression,
)
from server.simc_item_effect_support import (
    reload_effect_aggregate,
    reload_effect_record,
)


_ENVELOPE_KEY = re.compile(r"^exact-authority:sha256:[0-9a-f]{64}$")
_RECORD_KEY = re.compile(r"^simc-item-effect-record:sha256:[0-9a-f]{64}$")


class GearExactAuthorityStoreIntegrityError(RuntimeError):
    """Stored authority is missing, partial, or no longer exactly verifiable."""


@dataclass(frozen=True)
class ExactAuthorityBundle:
    exact_item: SealedCanonicalDocument
    static_facts: SealedCanonicalDocument
    progression: SealedCanonicalDocument
    effect_records: tuple[SealedCanonicalDocument, ...]
    effect_support: SealedCanonicalDocument
    envelope: SealedCanonicalDocument


def _exact_text(value: object, *, field: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise GearExactAuthorityStoreIntegrityError(f"invalid {field}")
    return value


def _exact_bytes(value: object, *, field: str) -> bytes:
    if type(value) is bytes:
        return value
    if isinstance(value, memoryview):
        return value.tobytes()
    raise GearExactAuthorityStoreIntegrityError(f"invalid {field}")


class GearExactAuthorityStore:
    """Seal and fully rehydrate one immutable authority dependency closure."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def connection(self):
        return self._connection_factory()

    @staticmethod
    def _revision_projection(cur: Any, bundle: ExactAuthorityBundle) -> tuple[str, str, str]:
        cur.execute(
            """
            /* exact_authority_revision_projection */
            SELECT
                pg_catalog.convert_from(%s, 'UTF8')::jsonb ->> 'gearRuleRevision',
                pg_catalog.convert_from(%s, 'UTF8')::jsonb ->> 'simcRuntimeRevision',
                pg_catalog.convert_from(%s, 'UTF8')::jsonb ->> 'resolverRevision'
            """,
            (
                bundle.progression.canonical_bytes,
                bundle.effect_support.canonical_bytes,
                bundle.envelope.canonical_bytes,
            ),
        )
        row = cur.fetchone()
        if not row or len(row) != 3:
            raise GearExactAuthorityStoreIntegrityError(
                "authority revision projection is unavailable",
            )
        return (
            _exact_text(row[0], field="gear_rule_revision"),
            _exact_text(row[1], field="simc_runtime_revision"),
            _exact_text(row[2], field="resolver_revision"),
        )

    @staticmethod
    def _load_document_row(cur: Any, key: str) -> tuple[str, str, str, bytes]:
        cur.execute(
            """
            /* exact_authority_document_load */
            SELECT
                content_key,
                document_kind,
                schema_revision,
                canonical_bytes,
                canonical_sha256 = pg_catalog.encode(
                    pg_catalog.sha256(canonical_bytes), 'hex'
                )
                AND canonical_json = pg_catalog.convert_from(
                    canonical_bytes, 'UTF8'
                )::jsonb AS projection_valid
            FROM cache.websim_canonical_documents
            WHERE content_key = %s
            """,
            (key,),
        )
        row = cur.fetchone()
        if not row or len(row) != 5 or row[4] is not True:
            raise GearExactAuthorityStoreIntegrityError(
                f"canonical authority document missing: {key}",
            )
        return (
            _exact_text(row[0], field="content_key"),
            _exact_text(row[1], field="document_kind"),
            _exact_text(row[2], field="schema_revision"),
            _exact_bytes(row[3], field="canonical_bytes"),
        )

    @classmethod
    def _insert_document(cls, cur: Any, document: SealedCanonicalDocument) -> None:
        if type(document) is not SealedCanonicalDocument:
            raise GearExactAuthorityStoreIntegrityError(
                "bundle fields must be exact SealedCanonicalDocument values",
            )
        cur.execute(
            """
            /* exact_authority_document_insert */
            WITH input(content_key, document_kind, schema_revision, canonical_bytes) AS (
                VALUES (%s, %s, %s, %s)
            )
            INSERT INTO cache.websim_canonical_documents (
                content_key,
                document_kind,
                schema_revision,
                canonical_bytes,
                canonical_json,
                canonical_sha256
            )
            SELECT
                content_key,
                document_kind,
                schema_revision,
                canonical_bytes,
                pg_catalog.convert_from(canonical_bytes, 'UTF8')::jsonb,
                pg_catalog.encode(pg_catalog.sha256(canonical_bytes), 'hex')
            FROM input
            ON CONFLICT DO NOTHING
            """,
            (
                document.content_key,
                document.document_kind,
                document.schema_revision,
                document.canonical_bytes,
            ),
        )
        stored = cls._load_document_row(cur, document.content_key)
        expected = (
            document.content_key,
            document.document_kind,
            document.schema_revision,
            document.canonical_bytes,
        )
        if stored != expected:
            raise GearExactAuthorityStoreIntegrityError(
                f"canonical authority document collision: {document.content_key}",
            )

    @staticmethod
    def _load_bundle_row(cur: Any, envelope_key: str) -> tuple[str, ...]:
        cur.execute(
            """
            /* exact_authority_bundle_load */
            SELECT
                exact_authority_envelope_key,
                exact_item_instance_key,
                static_facts_key,
                progression_binding_key,
                effect_support_key,
                gear_rule_revision,
                simc_runtime_revision,
                resolver_revision
            FROM cache.websim_exact_authority_bundles
            WHERE exact_authority_envelope_key = %s
            """,
            (envelope_key,),
        )
        row = cur.fetchone()
        if not row or len(row) != 8:
            raise GearExactAuthorityStoreIntegrityError(
                f"Exact Authority Bundle missing: {envelope_key}",
            )
        return tuple(
            _exact_text(value, field=f"bundle[{index}]")
            for index, value in enumerate(row)
        )

    @staticmethod
    def _load_relation_rows(cur: Any, aggregate_key: str) -> tuple[tuple[int, str], ...]:
        cur.execute(
            """
            /* exact_authority_effect_relation_load */
            SELECT ordinal, effect_record_key
            FROM cache.websim_effect_aggregate_records
            WHERE effect_support_key = %s
            ORDER BY ordinal
            """,
            (aggregate_key,),
        )
        rows = tuple(cur.fetchall())
        if not rows:
            raise GearExactAuthorityStoreIntegrityError(
                "effect aggregate record closure is empty",
            )
        normalized: list[tuple[int, str]] = []
        for expected_ordinal, row in enumerate(rows):
            if (
                type(row) not in {tuple, list}
                or len(row) != 2
                or type(row[0]) is not int
                or row[0] != expected_ordinal
            ):
                raise GearExactAuthorityStoreIntegrityError(
                    "effect aggregate record ordinals are not contiguous",
                )
            normalized.append((
                row[0], _exact_text(row[1], field="effect_record_key"),
            ))
        return tuple(normalized)

    @classmethod
    def _load_verified_bundle_with_cursor(
        cls,
        cur: Any,
        envelope_key: str,
        *,
        gear_rule_revision: str,
        simc_runtime_revision: str,
        resolver_revision: str,
    ) -> ExactAuthorityBundle:
        row = cls._load_bundle_row(cur, envelope_key)
        if row[0] != envelope_key or row[5:] != (
            gear_rule_revision,
            simc_runtime_revision,
            resolver_revision,
        ):
            raise GearExactAuthorityStoreIntegrityError(
                "Exact Authority Bundle revision mismatch",
            )
        exact_row = cls._load_document_row(cur, row[1])
        exact = reload_exact_item(exact_row[3], exact_row[0])
        if exact_row[1:3] != (exact.document_kind, exact.schema_revision):
            raise GearExactAuthorityStoreIntegrityError("Exact metadata mismatch")
        static_row = cls._load_document_row(cur, row[2])
        static = reload_exact_static_facts(
            static_row[3], static_row[0], exact=exact,
        )
        if static_row[1:3] != (static.document_kind, static.schema_revision):
            raise GearExactAuthorityStoreIntegrityError("static facts metadata mismatch")
        progression_row = cls._load_document_row(cur, row[3])
        progression = reload_exact_progression(
            progression_row[3], progression_row[0], exact=exact,
        )
        if progression_row[1:3] != (
            progression.document_kind, progression.schema_revision,
        ):
            raise GearExactAuthorityStoreIntegrityError("progression metadata mismatch")
        relation_rows = cls._load_relation_rows(cur, row[4])
        records = tuple(
            cls._load_effect_record_with_cursor(
                cur, record_key, simc_runtime_revision=simc_runtime_revision,
            )
            for _, record_key in relation_rows
        )
        effect_row = cls._load_document_row(cur, row[4])
        effect = reload_effect_aggregate(
            effect_row[3],
            effect_row[0],
            exact=exact,
            runtime_revision=simc_runtime_revision,
            records=records,
        )
        if effect_row[1:3] != (effect.document_kind, effect.schema_revision):
            raise GearExactAuthorityStoreIntegrityError("effect aggregate metadata mismatch")
        envelope_row = cls._load_document_row(cur, row[0])
        envelope = reload_exact_authority_envelope(
            envelope_row[3],
            envelope_row[0],
            exact=exact,
            static_facts=static,
            progression=progression,
            effect_support=effect,
            resolver_revision=resolver_revision,
        )
        if envelope_row[1:3] != (
            envelope.document_kind, envelope.schema_revision,
        ):
            raise GearExactAuthorityStoreIntegrityError("envelope metadata mismatch")
        return ExactAuthorityBundle(
            exact_item=exact,
            static_facts=static,
            progression=progression,
            effect_records=records,
            effect_support=effect,
            envelope=envelope,
        )

    @classmethod
    def _load_effect_record_with_cursor(
        cls,
        cur: Any,
        record_key: str,
        *,
        simc_runtime_revision: str,
    ) -> SealedCanonicalDocument:
        row = cls._load_document_row(cur, record_key)
        record = reload_effect_record(
            row[3], row[0], runtime_revision=simc_runtime_revision,
        )
        if row[1:3] != (record.document_kind, record.schema_revision):
            raise GearExactAuthorityStoreIntegrityError("effect record metadata mismatch")
        return record

    def seal_authority_bundle(
        self,
        bundle: ExactAuthorityBundle,
    ) -> ExactAuthorityBundle:
        if type(bundle) is not ExactAuthorityBundle:
            raise TypeError("bundle must be an exact ExactAuthorityBundle")
        if type(bundle.effect_records) is not tuple or not bundle.effect_records:
            raise GearExactAuthorityStoreIntegrityError(
                "bundle requires a non-empty effect record tuple",
            )
        try:
            exact = reload_exact_item(
                bundle.exact_item.canonical_bytes,
                bundle.exact_item.content_key,
            )
            static = reload_exact_static_facts(
                bundle.static_facts.canonical_bytes,
                bundle.static_facts.content_key,
                exact=exact,
            )
            progression = reload_exact_progression(
                bundle.progression.canonical_bytes,
                bundle.progression.content_key,
                exact=exact,
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise GearExactAuthorityStoreIntegrityError(
                "bundle canonical dependency is invalid",
            ) from error
        with self.connection() as connection:
            with connection.cursor() as cur:
                gear_rule, runtime, resolver = self._revision_projection(cur, bundle)
                try:
                    records = tuple(
                        reload_effect_record(
                            document.canonical_bytes,
                            document.content_key,
                            runtime_revision=runtime,
                        )
                        for document in bundle.effect_records
                    )
                    effect = reload_effect_aggregate(
                        bundle.effect_support.canonical_bytes,
                        bundle.effect_support.content_key,
                        exact=exact,
                        runtime_revision=runtime,
                        records=records,
                    )
                    envelope = reload_exact_authority_envelope(
                        bundle.envelope.canonical_bytes,
                        bundle.envelope.content_key,
                        exact=exact,
                        static_facts=static,
                        progression=progression,
                        effect_support=effect,
                        resolver_revision=resolver,
                    )
                except (AttributeError, TypeError, ValueError) as error:
                    raise GearExactAuthorityStoreIntegrityError(
                        "bundle effect authority is invalid",
                    ) from error
                verified = ExactAuthorityBundle(
                    exact_item=exact,
                    static_facts=static,
                    progression=progression,
                    effect_records=records,
                    effect_support=effect,
                    envelope=envelope,
                )
                for document in (
                    exact,
                    static,
                    progression,
                    *records,
                    effect,
                    envelope,
                ):
                    self._insert_document(cur, document)
                for ordinal, record in enumerate(records):
                    cur.execute(
                        """
                        /* exact_authority_effect_relation_insert */
                        INSERT INTO cache.websim_effect_aggregate_records (
                            effect_support_key, ordinal, effect_record_key
                        ) VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (effect.content_key, ordinal, record.content_key),
                    )
                cur.execute(
                    """
                    /* exact_authority_bundle_insert */
                    INSERT INTO cache.websim_exact_authority_bundles (
                        exact_authority_envelope_key,
                        exact_item_instance_key,
                        static_facts_key,
                        progression_binding_key,
                        effect_support_key,
                        gear_rule_revision,
                        simc_runtime_revision,
                        resolver_revision
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        envelope.content_key,
                        exact.content_key,
                        static.content_key,
                        progression.content_key,
                        effect.content_key,
                        gear_rule,
                        runtime,
                        resolver,
                    ),
                )
                try:
                    readback = self._load_verified_bundle_with_cursor(
                        cur,
                        envelope.content_key,
                        gear_rule_revision=gear_rule,
                        simc_runtime_revision=runtime,
                        resolver_revision=resolver,
                    )
                except GearExactAuthorityStoreIntegrityError:
                    raise
                except (AttributeError, TypeError, ValueError) as error:
                    raise GearExactAuthorityStoreIntegrityError(
                        "Exact Authority Bundle failed typed readback",
                    ) from error
                if readback != verified:
                    raise GearExactAuthorityStoreIntegrityError(
                        "Exact Authority Bundle readback collision",
                    )
                return readback

    def load_verified_bundle(
        self,
        envelope_key: str,
        *,
        gear_rule_revision: str,
        simc_runtime_revision: str,
        resolver_revision: str,
    ) -> ExactAuthorityBundle:
        key = _exact_text(envelope_key, field="envelope_key")
        if _ENVELOPE_KEY.fullmatch(key) is None:
            raise GearExactAuthorityStoreIntegrityError("invalid envelope_key")
        gear_rule = _exact_text(gear_rule_revision, field="gear_rule_revision")
        runtime = _exact_text(
            simc_runtime_revision, field="simc_runtime_revision",
        )
        resolver = _exact_text(resolver_revision, field="resolver_revision")
        try:
            with self.connection() as connection:
                with connection.cursor() as cur:
                    return self._load_verified_bundle_with_cursor(
                        cur,
                        key,
                        gear_rule_revision=gear_rule,
                        simc_runtime_revision=runtime,
                        resolver_revision=resolver,
                    )
        except GearExactAuthorityStoreIntegrityError:
            raise
        except (AttributeError, TypeError, ValueError) as error:
            raise GearExactAuthorityStoreIntegrityError(
                "Exact Authority Bundle failed typed reload",
            ) from error

    def load_verified_bundles(
        self,
        envelope_keys,
        *,
        gear_rule_revision: str,
        simc_runtime_revision: str,
        resolver_revision: str,
    ) -> tuple[ExactAuthorityBundle, ...]:
        if type(envelope_keys) not in {tuple, list} or not envelope_keys:
            raise GearExactAuthorityStoreIntegrityError(
                "envelope_keys must be a non-empty ordered sequence",
            )
        return tuple(
            self.load_verified_bundle(
                key,
                gear_rule_revision=gear_rule_revision,
                simc_runtime_revision=simc_runtime_revision,
                resolver_revision=resolver_revision,
            )
            for key in envelope_keys
        )

    def load_effect_records(
        self,
        record_keys,
        *,
        simc_runtime_revision: str,
    ) -> tuple[SealedCanonicalDocument, ...]:
        if type(record_keys) not in {tuple, list} or not record_keys:
            raise GearExactAuthorityStoreIntegrityError(
                "record_keys must be a non-empty ordered sequence",
            )
        runtime = _exact_text(
            simc_runtime_revision, field="simc_runtime_revision",
        )
        keys = tuple(_exact_text(key, field="record_key") for key in record_keys)
        if any(_RECORD_KEY.fullmatch(key) is None for key in keys):
            raise GearExactAuthorityStoreIntegrityError("invalid record_key")
        try:
            with self.connection() as connection:
                with connection.cursor() as cur:
                    return tuple(
                        self._load_effect_record_with_cursor(
                            cur, key, simc_runtime_revision=runtime,
                        )
                        for key in keys
                    )
        except GearExactAuthorityStoreIntegrityError:
            raise
        except (AttributeError, TypeError, ValueError) as error:
            raise GearExactAuthorityStoreIntegrityError(
                "effect record failed typed reload",
            ) from error


__all__ = (
    "ExactAuthorityBundle",
    "GearExactAuthorityStore",
    "GearExactAuthorityStoreIntegrityError",
)
