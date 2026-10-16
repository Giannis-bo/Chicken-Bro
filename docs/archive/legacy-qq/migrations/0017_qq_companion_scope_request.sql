ALTER TABLE qq_channel.companion_responses ADD COLUMN requested_scope text
 CHECK(requested_scope IN ('wow_read','wow_sim'));
