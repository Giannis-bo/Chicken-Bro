-- 0037: keep the complete S2 tier-set index in the immutable Exact header.
--
-- S2 set membership is authoritative registry content, not display metadata.
-- The complete index is just over the original 128 KiB header bound, so raise
-- only this summary field's bound while retaining the JSON object contract.

DO $registry_summary_capacity$
DECLARE
    target_table pg_catalog.regclass;
    target_constraint name;
BEGIN
    FOR target_table IN
        SELECT table_name::pg_catalog.regclass
        FROM (VALUES
            ('cache.websim_gear_exact_registries'),
            ('cache.websim_gear_exact_instance_template_refs')
        ) AS target_tables(table_name)
    LOOP
        LOOP
            SELECT constraint_row.conname
            INTO target_constraint
            FROM pg_catalog.pg_constraint AS constraint_row
            WHERE constraint_row.conrelid = target_table
              AND constraint_row.contype = 'c'
              AND pg_catalog.pg_get_constraintdef(constraint_row.oid)
                  LIKE '%registry_summary_json%'
              AND pg_catalog.pg_get_constraintdef(constraint_row.oid)
                  LIKE '%octet_length%'
            ORDER BY constraint_row.conname
            LIMIT 1;

            EXIT WHEN target_constraint IS NULL;
            EXECUTE pg_catalog.format(
                'ALTER TABLE %s DROP CONSTRAINT %I',
                target_table,
                target_constraint
            );
        END LOOP;

        EXECUTE pg_catalog.format(
            'ALTER TABLE %s ADD CONSTRAINT %I CHECK ('
            'jsonb_typeof(registry_summary_json) = ''object'' '
            'AND octet_length(registry_summary_json::text) <= 262144)',
            target_table,
            CASE target_table::text
                WHEN 'cache.websim_gear_exact_registries'
                    THEN 'websim_exact_registries_summary_capacity_check'
                ELSE 'websim_exact_template_refs_summary_capacity_check'
            END
        );
    END LOOP;
END;
$registry_summary_capacity$;

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0037_websim_exact_registry_summary_capacity',
    'Allow the complete immutable S2 tier-set index in Exact registry summaries'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description;
