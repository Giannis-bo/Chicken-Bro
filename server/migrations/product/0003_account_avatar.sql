-- Additive and compatible with the previous API; no new product table.
ALTER TABLE identity.users ADD COLUMN avatar_data_url text
    CHECK (avatar_data_url IS NULL OR (
        octet_length(avatar_data_url) <= 349551 AND
        avatar_data_url ~ '^data:image/(png|jpeg);base64,[A-Za-z0-9+/]+={0,2}$'
    ));
