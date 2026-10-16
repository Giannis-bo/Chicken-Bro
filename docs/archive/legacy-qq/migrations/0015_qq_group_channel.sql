-- Additive transport storage. No QQ website identity linking or session issuance.
CREATE SCHEMA qq_channel;
CREATE TABLE qq_channel.principals (
    user_id uuid PRIMARY KEY REFERENCES identity.users(id),
    bot_id text NOT NULL, group_id text NOT NULL, sender_id text NOT NULL,
    game text NOT NULL DEFAULT 'wow' CHECK (game IN ('wow','poe2')),
    wow_generation integer NOT NULL DEFAULT 0,
    poe2_generation integer NOT NULL DEFAULT 0,
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(bot_id,group_id,sender_id)
);
CREATE TABLE qq_channel.conversations (
    user_id uuid NOT NULL REFERENCES qq_channel.principals(user_id),
    game text NOT NULL CHECK (game IN ('wow','poe2')),
    generation integer NOT NULL,
    conversation_id uuid NOT NULL,
    PRIMARY KEY(user_id,game,generation),
    FOREIGN KEY(conversation_id,user_id) REFERENCES chat.conversations(id,user_id)
);
CREATE TABLE qq_channel.inbox (
    id uuid PRIMARY KEY,
    bot_id text NOT NULL, group_id text NOT NULL, sender_id text NOT NULL, message_id text NOT NULL,
    user_id uuid NOT NULL REFERENCES qq_channel.principals(user_id),
    game text NOT NULL, generation integer NOT NULL,
    content text NOT NULL CHECK(char_length(content)<=4000),
    state text NOT NULL CHECK(state IN ('pending','running','done','failed')),
    conversation_id uuid, run_id uuid REFERENCES chat.agent_runs(id),
    received_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(bot_id,group_id,message_id),
    FOREIGN KEY(conversation_id,user_id) REFERENCES chat.conversations(id,user_id)
);
CREATE INDEX qq_inbox_active ON qq_channel.inbox(bot_id,received_at) WHERE state IN ('pending','running');
CREATE TABLE qq_channel.outbox (
    id uuid PRIMARY KEY, inbox_id uuid NOT NULL REFERENCES qq_channel.inbox(id),
    kind text NOT NULL, part integer NOT NULL,
    content text NOT NULL CHECK(char_length(content)<=1500),
    state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','sending','sent','uncertain','failed')),
    receipt text, created_at timestamptz NOT NULL DEFAULT now(), sent_at timestamptz,
    UNIQUE(inbox_id,kind,part)
);
ALTER TABLE chat.executions ADD COLUMN actor_kind text NOT NULL DEFAULT 'web_cookie'
    CHECK(actor_kind IN ('web_cookie','qq_group'));
GRANT USAGE ON SCHEMA qq_channel TO wow_app;
GRANT SELECT,INSERT,UPDATE ON ALL TABLES IN SCHEMA qq_channel TO wow_app;
