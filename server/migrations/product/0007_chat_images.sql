ALTER TABLE chat.messages ADD COLUMN image_ids uuid[] NOT NULL DEFAULT '{}';
ALTER TABLE chat.messages DROP CONSTRAINT messages_content_check;
ALTER TABLE chat.messages ADD CONSTRAINT messages_content_check CHECK (
    length(content) BETWEEN 0 AND 100000 AND
    (length(content) > 0 OR (role = 'user' AND cardinality(image_ids) > 0)) AND
    cardinality(image_ids) <= 3 AND (role = 'user' OR cardinality(image_ids) = 0)
);
CREATE TABLE chat.images (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES identity.users(id) ON DELETE CASCADE,
    upload_key text NOT NULL CHECK (length(upload_key) BETWEEN 8 AND 128),
    sha256 text NOT NULL,
    mime_type text NOT NULL CHECK (mime_type IN ('image/png', 'image/jpeg')),
    width integer NOT NULL CHECK (width BETWEEN 1 AND 8192),
    height integer NOT NULL CHECK (height BETWEEN 1 AND 8192),
    data bytea CHECK (octet_length(data) BETWEEN 1 AND 5242880),
    message_id uuid,
    created_at timestamptz NOT NULL,
    expires_at timestamptz,
    UNIQUE(user_id, upload_key),
    FOREIGN KEY(message_id, user_id) REFERENCES chat.messages(id, user_id) ON DELETE CASCADE
);
CREATE INDEX images_owner ON chat.images(user_id);
CREATE INDEX images_expiry ON chat.images(expires_at) WHERE data IS NOT NULL;
GRANT SELECT, INSERT, UPDATE, DELETE ON chat.images TO wow_app;
