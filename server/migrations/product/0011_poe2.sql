ALTER TABLE chat.conversations
ADD COLUMN game text NOT NULL DEFAULT 'wow'
CHECK (game IN ('wow', 'poe2'));

CREATE INDEX idx_chat_conversations_user_game_updated
ON chat.conversations (user_id, game, updated_at DESC, id DESC)
WHERE status = 'active';
