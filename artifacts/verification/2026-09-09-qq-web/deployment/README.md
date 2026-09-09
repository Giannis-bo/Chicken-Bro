# QQ Web production release — 2026-09-09

Production API and Web now use QQ login, source `7a893c383d09f1a3a46e2d5cea66309bf7a74cff`. This includes the deployed screenshot-input and chat-reliability changes. Mini login endpoints return 404; no Mini build/upload was performed.

Real QQ login succeeded in candidate and production through the user’s current QQ account. Candidate logout/relogin and production refresh preserved the expected account history. Production Chat returned the requested acceptance reply; a new production SimC task produced 161630.27 DPS over 299 iterations. A second real QQ account was not used; automated PostgreSQL/API tests verify second-account isolation. Manual user product acceptance is not claimed.

470 backend, 269 Web, 42 PostgreSQL and 62 control tests passed. Typecheck/lint passed. Both H5 builds passed with two existing bundle-size warnings. All 13 production files matched their local build bytes.

QQ’s real token JSON uses a numeric string for expires_in. The added regression failed before the three-line compatibility fix and passed after. Candidate model access also required copying the existing production proxy configuration; QQ token exchange remains direct with trust_env=False.

The candidate has its own database, credentials, Cookie names, port 8794 and service namespace binding `/var/lib/chickenbro-qq-candidate` onto `/var/lib/chickenbro`, isolating heartbeat and job paths. It is not a copy of production user data.

Before production migration, a consistent pg_dump snapshot was independently restored and table counts matched. Applying QQ migration to that restore preserved all prior business counts. After release, all original users, identities, conversations, messages and SimC records matched the restored rows exactly. No old-account linking, business-data deletion or historical retirement was performed.

## Recovery

See promotion.json and recovery.json for exact paths and identities. Prior source/Web are retained as images-72e6224f21eb0d5fb0635237d454eebe8b845884. The snapshot remains cloud-only in a private PostgreSQL-owned backup directory. To roll back application code, first drain active Chat/SimC work and verify current pointers, restore both prior source/Web symlinks, disable only the QQ release drop-in, reload systemd and restart API/worker. Keep the additive QQ schema and all data; do not blindly restore the old dump over new production writes. Database restore was tested; an actual runtime rollback switch was not performed.

The shared QQ secret remains in root-owned mode-0600 `/etc/chickenbro-qq.env`; never print it. Nginx access and error logging is disabled for candidate and production callback prefixes. Preserve both registered callback URLs.
