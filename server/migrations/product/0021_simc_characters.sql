CREATE TABLE IF NOT EXISTS simc.character_preferences (
    user_id uuid PRIMARY KEY REFERENCES identity.users(id),
    preferences jsonb NOT NULL DEFAULT '{"items": [], "selectedId": null}',
    CHECK (jsonb_typeof(preferences->'items') = 'array'),
    CHECK (jsonb_array_length(preferences->'items') <= 3)
);
GRANT SELECT, INSERT, UPDATE ON simc.character_preferences TO wow_app;
