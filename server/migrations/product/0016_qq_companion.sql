-- Additive companion storage; existing website defaults and records are unchanged.
CREATE TABLE qq_channel.members (
 bot_id text NOT NULL, group_id text NOT NULL, sender_id text NOT NULL,
 display_name text NOT NULL CHECK(length(display_name)<=80), updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(bot_id,group_id,sender_id)
);
CREATE TABLE qq_channel.observations (
 seq bigserial PRIMARY KEY, bot_id text NOT NULL, group_id text NOT NULL, sender_id text NOT NULL,
 message_id text NOT NULL, occurred_at timestamptz NOT NULL, content text NOT NULL CHECK(length(content)<=4000),
 display_name text NOT NULL, mentioned boolean NOT NULL, reply_to text, attachment boolean NOT NULL,
 received_at timestamptz NOT NULL DEFAULT now(), UNIQUE(bot_id,group_id,message_id)
);
CREATE INDEX qq_observation_context ON qq_channel.observations(bot_id,group_id,seq DESC);
CREATE TABLE qq_channel.group_state (
 bot_id text NOT NULL,group_id text NOT NULL,observed_seq bigint NOT NULL DEFAULT 0,
 decided_seq bigint NOT NULL DEFAULT 0,pending_since timestamptz,last_new_at timestamptz,
 PRIMARY KEY(bot_id,group_id)
);
CREATE TABLE qq_channel.companion_responses (
 id uuid PRIMARY KEY,bot_id text NOT NULL,group_id text NOT NULL,sender_id text NOT NULL,message_id text NOT NULL,
 event_json jsonb NOT NULL,kind text NOT NULL CHECK(kind IN ('mention','proactive')),
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','running','done','failed','silent','professional')),
 lease_token uuid,lease_expires_at timestamptz,context_seq bigint NOT NULL DEFAULT 0,
 created_at timestamptz NOT NULL DEFAULT now(),started_at timestamptz,finished_at timestamptz,
 inbox_id uuid REFERENCES qq_channel.inbox(id),run_id uuid REFERENCES chat.agent_runs(id),error_code text,
 UNIQUE(bot_id,group_id,message_id)
);
CREATE TABLE qq_channel.member_facts (
 bot_id text NOT NULL,group_id text NOT NULL,sender_id text NOT NULL,fact_key text NOT NULL,
 value text NOT NULL CHECK(length(value)<=500),evidence text NOT NULL CHECK(length(evidence)<=1000),
 source_message_id text NOT NULL,active boolean NOT NULL DEFAULT true,updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(bot_id,group_id,sender_id,fact_key),
 FOREIGN KEY(bot_id,group_id,sender_id) REFERENCES qq_channel.members(bot_id,group_id,sender_id)
);
CREATE TABLE qq_channel.run_scopes (
 run_id uuid PRIMARY KEY REFERENCES chat.agent_runs(id),user_id uuid NOT NULL REFERENCES identity.users(id),
 scope text NOT NULL CHECK(scope IN ('wow_read','wow_sim')),inbox_id uuid NOT NULL REFERENCES qq_channel.inbox(id)
);
ALTER TABLE qq_channel.outbox ADD COLUMN sticker_id text;
GRANT SELECT,INSERT,UPDATE,DELETE ON qq_channel.members,qq_channel.observations,qq_channel.group_state,
 qq_channel.companion_responses,qq_channel.member_facts,qq_channel.run_scopes TO wow_app;
GRANT USAGE,SELECT ON SEQUENCE qq_channel.observations_seq_seq TO wow_app;
