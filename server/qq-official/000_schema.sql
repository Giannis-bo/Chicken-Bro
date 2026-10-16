-- Dedicated official QQ databases only; website migrations do not load this file.
CREATE SCHEMA IF NOT EXISTS qq_channel;
CREATE TABLE IF NOT EXISTS qq_channel.principals (
 user_id uuid PRIMARY KEY REFERENCES identity.users(id),
 bot_id text NOT NULL, group_id text NOT NULL, sender_id text NOT NULL,
 enabled boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(bot_id,group_id,sender_id)
);
CREATE TABLE IF NOT EXISTS qq_channel.inbox (
 id uuid PRIMARY KEY,
 bot_id text NOT NULL, group_id text NOT NULL, sender_id text NOT NULL, message_id text NOT NULL,
 user_id uuid NOT NULL REFERENCES qq_channel.principals(user_id),
 game text NOT NULL DEFAULT 'wow' CHECK(game='wow'), generation integer NOT NULL DEFAULT 0,
 content text NOT NULL CHECK(char_length(content)<=4000),
 state text NOT NULL CHECK(state IN ('pending','running','done','failed')),
 conversation_id uuid, run_id uuid REFERENCES chat.agent_runs(id),
 received_at timestamptz NOT NULL DEFAULT now(), UNIQUE(bot_id,group_id,message_id)
);
CREATE TABLE IF NOT EXISTS qq_channel.outbox (
 id uuid PRIMARY KEY, inbox_id uuid NOT NULL REFERENCES qq_channel.inbox(id),
 kind text NOT NULL, part integer NOT NULL CHECK(part BETWEEN 0 AND 4),
 content text NOT NULL CHECK(char_length(content)<=1500),
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','sending','sent','failed','uncertain')),
 receipt text, created_at timestamptz NOT NULL DEFAULT now(), sent_at timestamptz,
 UNIQUE(inbox_id,kind,part)
);
GRANT USAGE ON SCHEMA qq_channel TO wow_app;
GRANT SELECT,INSERT,UPDATE ON qq_channel.principals,qq_channel.inbox,qq_channel.outbox TO wow_app;
