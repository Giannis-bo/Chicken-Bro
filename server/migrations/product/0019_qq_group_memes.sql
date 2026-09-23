-- Current-group media references only; URLs/rkeys are not stored.
CREATE TABLE qq_channel.memes (
 bot_id text NOT NULL,group_id text NOT NULL,id text NOT NULL,
 source_message_id text NOT NULL,source_sender_id text NOT NULL,file_key text NOT NULL,
 source text NOT NULL CHECK(source IN ('group','web')),summary text NOT NULL,
 content bytea,preview text,mime text,sha256 text,
 created_at timestamptz NOT NULL DEFAULT now(),failed boolean NOT NULL DEFAULT false,
 PRIMARY KEY(bot_id,group_id,id),
 CHECK(content IS NULL OR octet_length(content)<=2097152),
 CHECK(preview IS NULL OR length(preview)<=1000000)
);
GRANT SELECT,INSERT,UPDATE,DELETE ON qq_channel.memes TO wow_app;
