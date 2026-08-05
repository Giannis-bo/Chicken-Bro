DO $$
DECLARE
    target_constraint_count integer;
BEGIN
    ALTER TABLE app.build_templates
    DROP CONSTRAINT IF EXISTS build_templates_user_id_template_type_name_key;

    SELECT pg_catalog.count(*)
    INTO target_constraint_count
    FROM pg_catalog.pg_constraint con
    JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
    JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace
    WHERE nsp.nspname = 'app'
      AND rel.relname = 'build_templates'
      AND con.conname = 'build_templates_user_id_template_type_config_hash_key';

    IF target_constraint_count = 0 THEN
        ALTER TABLE app.build_templates
        ADD CONSTRAINT build_templates_user_id_template_type_config_hash_key
        UNIQUE (user_id, template_type, config_hash);
    END IF;

    SELECT pg_catalog.count(*)
    INTO target_constraint_count
    FROM pg_catalog.pg_constraint con
    JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
    JOIN pg_catalog.pg_namespace nsp ON nsp.oid = rel.relnamespace
    WHERE nsp.nspname = 'app'
      AND rel.relname = 'build_templates'
      AND con.conname = 'build_templates_user_id_template_type_config_hash_key'
      AND con.contype = 'u'
      AND ARRAY(
          SELECT attr.attname::text
          FROM pg_catalog.unnest(con.conkey) WITH ORDINALITY AS keyed(attnum, ordinal)
          JOIN pg_catalog.pg_attribute attr
            ON attr.attrelid = con.conrelid
           AND attr.attnum = keyed.attnum
          ORDER BY keyed.ordinal
      ) = ARRAY['user_id', 'template_type', 'config_hash'];

    IF target_constraint_count <> 1 THEN
        RAISE EXCEPTION
            'build_templates config-hash unique constraint semantic drift';
    END IF;

    INSERT INTO ops.schema_migrations (id, description)
    VALUES (
        '0003_build_template_config_hash_unique',
        'Deduplicate PostgreSQL build templates by user, type, and config hash instead of display name'
    )
    ON CONFLICT (id) DO UPDATE
    SET description = EXCLUDED.description,
        applied_at = now();
END $$;
