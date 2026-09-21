ALTER TABLE poe2.builds ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
GRANT UPDATE (deleted_at) ON poe2.builds TO wow_app;
