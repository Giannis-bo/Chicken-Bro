ALTER TABLE app.build_templates
DROP CONSTRAINT IF EXISTS build_templates_user_id_template_type_name_key;

ALTER TABLE app.build_templates
ADD CONSTRAINT build_templates_user_id_template_type_config_hash_key
UNIQUE (user_id, template_type, config_hash);

INSERT INTO ops.schema_migrations (id, description)
VALUES (
    '0003_build_template_config_hash_unique',
    'Deduplicate PostgreSQL build templates by user, type, and config hash instead of display name'
)
ON CONFLICT (id) DO UPDATE
SET description = EXCLUDED.description,
    applied_at = now();
