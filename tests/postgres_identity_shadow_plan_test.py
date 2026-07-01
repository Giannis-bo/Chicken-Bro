import importlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path


class PostgresIdentityShadowPlanTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.pop("WOW_DATABASE_URL", None)
        os.environ["WOW_NEWS_DB"] = str(Path(self.tmp.name) / "news.sqlite3")

        import server.news_backend as backend

        self.backend = importlib.reload(backend)
        self.backend.init_db()

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("WOW_DATABASE_URL", None)
        os.environ.pop("WOW_NEWS_DB", None)

    def login_formal_user(self, code="wx-code-formal", openid="openid-formal", unionid="union-formal"):
        return self.backend.login_with_wechat_code(
            code,
            exchange_code=lambda value: {"openid": openid, "unionid": unionid},
        )

    def insert_task(self, conn, task_id, user_id, mode="simcraft_template"):
        now = "2026-06-27T12:00:00+00:00"
        conn.execute(
            """
            INSERT INTO simulator_tasks (
                id, user_id, mode, status, request_json, analysis_json, summary_json,
                queued_at, started_at, finished_at, attempt, locked_by, heartbeat_at,
                cancel_requested, last_error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                user_id,
                mode,
                "queued",
                "{}",
                "{}",
                "{}",
                now,
                "",
                "",
                0,
                "",
                "",
                0,
                "",
                now,
                now,
            ),
        )

    def insert_chickenbro_rows(self, conn, user_id, prefix):
        now = "2026-06-27T12:00:00+00:00"
        session_id = f"{prefix}-session"
        conn.execute(
            """
            INSERT INTO chickenbro_sessions (
                id, user_id, title, product_phase, metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, "session", "retail", "{}", now, now),
        )
        conn.execute(
            """
            INSERT INTO chickenbro_messages (
                id, session_id, user_id, role, content, payload_json, agent_job_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (f"{prefix}-message", session_id, user_id, "user", "hello", "{}", "", now),
        )
        conn.execute(
            """
            INSERT INTO agent_jobs (
                id, user_id, session_id, kind, status, request_json, bounded_context_json,
                result_json, error, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (f"{prefix}-job", user_id, session_id, "chickenbro", "queued", "{}", "{}", "{}", "", now, now),
        )
        conn.execute(
            """
            INSERT INTO chickenbro_user_profiles (user_id, profile_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, json.dumps({"schemaRevision": "test"}, ensure_ascii=False), now, now),
        )

    def test_identity_plan_maps_formal_users_to_stable_pg_users_and_excludes_tokens_and_guests(self):
        from server.migrations.postgres import identity_shadow_plan

        login = self.login_formal_user()
        formal_user = login["user"]
        guest = self.backend.guest_simulator_user("device-a")

        with self.backend.db_connection() as conn:
            plan = identity_shadow_plan.build_identity_shadow_plan(conn)
            second_plan = identity_shadow_plan.build_identity_shadow_plan(conn)

        self.assertEqual(plan["schemaRevision"], "postgres-identity-shadow-plan-v1")
        self.assertEqual(plan["users"][0]["sqliteUserId"], formal_user["id"])
        self.assertEqual(
            plan["users"][0]["pgUserId"],
            identity_shadow_plan.stable_pg_uuid("identity.users", f"wechat_users:{formal_user['id']}"),
        )
        self.assertEqual(plan["users"], second_plan["users"])
        self.assertNotIn(guest["id"], {row["sqliteUserId"] for row in plan["users"]})

        identities = {(row["provider"], row["providerSubject"]) for row in plan["userIdentities"]}
        self.assertIn(("wechat_openid", "openid-formal"), identities)
        self.assertIn(("wechat_unionid", "union-formal"), identities)
        self.assertEqual(plan["skipped"]["guestUsers"][0]["sqliteUserId"], guest["id"])
        self.assertEqual(plan["skipped"]["authTokens"], 1)
        self.assertEqual(plan["errors"], [])

    def test_identity_plan_excludes_legacy_fixed_guest_simulator_openid(self):
        from server.migrations.postgres import data_copy_plan, identity_shadow_plan

        now = "2026-06-27T12:00:00+00:00"
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                INSERT INTO wechat_users (openid, unionid, nickname, avatar_url, created_at, updated_at)
                VALUES ('guest-simulator', '', '', '', ?, ?)
                """,
                (now, now),
            )
            guest_user_id = conn.execute("SELECT id FROM wechat_users WHERE openid = 'guest-simulator'").fetchone()[0]
            self.insert_task(conn, "legacy-fixed-guest-task", guest_user_id)
            conn.commit()

        with self.backend.db_connection() as conn:
            identity_plan = identity_shadow_plan.build_identity_shadow_plan(conn)
            copy_plan = data_copy_plan.build_postgres_copy_plan(conn)

        self.assertEqual(identity_plan["totals"]["formalUsers"], 0)
        self.assertEqual(identity_plan["totals"]["guestUsers"], 1)
        self.assertEqual(identity_plan["ownerTables"]["simulator_tasks"]["guestRows"], 1)
        self.assertEqual(identity_plan["skipped"]["guestUsers"][0]["openid"], "guest-simulator")
        self.assertEqual(copy_plan["tables"]["identity.users"], [])
        self.assertEqual(copy_plan["tables"]["identity.user_identities"], [])
        self.assertEqual(copy_plan["tables"]["app.simulator_tasks"], [])

    def test_identity_plan_counts_formal_and_guest_owned_rows_without_migrating_guest_assets(self):
        from server.migrations.postgres import identity_shadow_plan

        login = self.login_formal_user(openid="openid-owner", unionid="")
        formal_user_id = login["user"]["id"]
        guest_user_id = self.backend.guest_simulator_user("device-owned")["id"]
        self.backend.save_user_build_template(
            login["accessToken"],
            {
                "type": "talent",
                "title": "Formal Talent",
                "rawString": "websim:formal",
                "status": "saved",
                "source": "test",
            },
        )
        now = "2026-06-27T12:00:00+00:00"
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                INSERT INTO user_build_templates (
                    id, user_id, template_type, title, raw_string, simc_lines_json,
                    status, status_label, source, metadata_json, schema_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "guest-template",
                    guest_user_id,
                    "talent",
                    "Guest Talent",
                    "websim:guest",
                    "[]",
                    "saved",
                    "Saved",
                    "test",
                    "{}",
                    1,
                    now,
                    now,
                ),
            )
            self.insert_task(conn, "formal-task", formal_user_id)
            self.insert_task(conn, "guest-task", guest_user_id)
            self.insert_chickenbro_rows(conn, formal_user_id, "formal")
            self.insert_chickenbro_rows(conn, guest_user_id, "guest")
            conn.commit()

        with self.backend.db_connection() as conn:
            plan = identity_shadow_plan.build_identity_shadow_plan(conn)

        for table in (
            "user_build_templates",
            "simulator_tasks",
            "chickenbro_sessions",
            "chickenbro_messages",
            "agent_jobs",
            "chickenbro_user_profiles",
        ):
            self.assertEqual(plan["ownerTables"][table]["formalRows"], 1, table)
            self.assertEqual(plan["ownerTables"][table]["guestRows"], 1, table)
            self.assertEqual(plan["ownerTables"][table]["migratableRows"], 1, table)

        self.assertEqual(plan["skipped"]["guestOwnedRows"], 6)
        self.assertEqual(plan["totals"]["formalUsers"], 1)
        self.assertEqual(plan["totals"]["guestUsers"], 1)

    def test_identity_shadow_plan_cli_reads_sqlite_file_without_database_url(self):
        self.login_formal_user(openid="openid-cli", unionid="")
        script = Path("server/migrations/postgres/identity_shadow_plan.py")

        result = subprocess.run(
            [sys.executable, str(script), os.environ["WOW_NEWS_DB"]],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        payload = json.loads(result.stdout)
        self.assertEqual(payload["schemaRevision"], "postgres-identity-shadow-plan-v1")
        self.assertEqual(payload["totals"]["formalUsers"], 1)
        self.assertEqual(payload["userIdentities"][0]["provider"], "wechat_openid")

    def test_data_copy_plan_exports_formal_owner_rows_and_excludes_guest_rows(self):
        from server.migrations.postgres import data_copy_plan

        login = self.login_formal_user(openid="openid-copy", unionid="union-copy")
        formal_user_id = login["user"]["id"]
        guest_user_id = self.backend.guest_simulator_user("device-copy")["id"]
        self.backend.save_user_build_template(
            login["accessToken"],
            {
                "type": "talent",
                "title": "Formal Copy Talent",
                "rawString": "websim:copy:formal",
                "status": "saved",
                "source": "test",
                "metadata": {"specKey": "arcane"},
            },
        )
        now = "2026-06-27T12:30:00+00:00"
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                INSERT INTO user_build_templates (
                    id, user_id, template_type, title, raw_string, simc_lines_json,
                    status, status_label, source, metadata_json, schema_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "guest-copy-template",
                    guest_user_id,
                    "talent",
                    "Guest Copy Talent",
                    "websim:copy:guest",
                    "[]",
                    "saved",
                    "Saved",
                    "test",
                    "{}",
                    1,
                    now,
                    now,
                ),
            )
            self.insert_task(conn, "formal-copy-task", formal_user_id)
            self.insert_task(conn, "guest-copy-task", guest_user_id)
            self.insert_chickenbro_rows(conn, formal_user_id, "formal-copy")
            self.insert_chickenbro_rows(conn, guest_user_id, "guest-copy")
            conn.commit()

        with self.backend.db_connection() as conn:
            plan = data_copy_plan.build_postgres_copy_plan(conn)

        formal_pg_user_id = plan["tables"]["identity.users"][0]["id"]
        self.assertEqual(plan["schemaRevision"], "postgres-data-copy-plan-v1")
        self.assertEqual(plan["tables"]["app.build_templates"][0]["user_id"], formal_pg_user_id)
        self.assertEqual(plan["tables"]["app.simulator_tasks"][0]["user_id"], formal_pg_user_id)
        self.assertEqual(plan["tables"]["app.chickenbro_sessions"][0]["user_id"], formal_pg_user_id)
        self.assertEqual(plan["tables"]["app.chickenbro_messages"][0]["user_id"], formal_pg_user_id)
        self.assertEqual(plan["tables"]["app.agent_jobs"][0]["user_id"], formal_pg_user_id)
        self.assertEqual(plan["tables"]["knowledge.user_context_summaries"][0]["user_id"], formal_pg_user_id)
        self.assertEqual(plan["totals"]["rowsByTable"]["app.build_templates"], 1)
        self.assertEqual(plan["totals"]["rowsByTable"]["app.simulator_tasks"], 1)
        self.assertEqual(plan["skipped"]["guestOwnedRows"], 6)
        plan_json = json.dumps(plan, ensure_ascii=False)
        self.assertNotIn("guest-copy", plan_json)
        self.assertNotIn("websim:copy:guest", plan_json)

    def test_data_copy_plan_exports_public_content_and_cache_rows(self):
        from server.migrations.postgres import data_copy_plan
        from server.migrations.postgres import identity_shadow_plan
        from server.postgres_content_store import content_uuid
        from server import raiderio_payload
        from server import websim_payload

        now = "2026-06-27T12:45:00+00:00"
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            raiderio_payload.ensure_raiderio_tables(conn)
            websim_payload.ensure_websim_tables(conn)
            conn.execute(
                """
                INSERT OR REPLACE INTO news_sources (
                    source_id, source_name, tier, fetch_mode, retail_only, license_status,
                    rate_limit, enabled, hostnames_json, source_url, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "blizzard",
                    "Blizzard News",
                    "official",
                    "rss",
                    1,
                    "approved",
                    "low",
                    1,
                    json.dumps(["worldofwarcraft.blizzard.com"]),
                    "https://worldofwarcraft.blizzard.com/news",
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO news_raw_articles (
                    id, source_id, source_name, source_tier, canonical_url, original_title,
                    original_summary, original_body, body_blocks_json, published_at, fetched_at,
                    fetch_error, license_status, verification_status, canonical_topic_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "article-public-1",
                    "blizzard",
                    "Blizzard News",
                    "official",
                    "https://worldofwarcraft.blizzard.com/news/1",
                    "Original title",
                    "Original summary",
                    "Original body",
                    json.dumps([{"type": "paragraph", "text": "Original body"}]),
                    now,
                    now,
                    "",
                    "approved",
                    "official_verified",
                    "news:1",
                ),
            )
            conn.execute(
                """
                INSERT INTO news_article_evidence (
                    id, article_id, canonical_topic_id, source_id, source_name, source_tier,
                    evidence_url, verification_status, conflict_reason, checked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (7, "article-public-1", "news:1", "blizzard", "Blizzard News", "official", "https://evidence", "verified", "", now),
            )
            conn.execute(
                """
                INSERT INTO news_articles (
                    id, title, summary, channel, category, tags_json, importance,
                    source_name, source_url, published_at, source_note, updated_at,
                    body_zh, original_title, original_summary, original_body,
                    translation_status, content_status, tag_items_json, blocked_reason,
                    source_id, source_tier, license_status, verification_status,
                    source_badges_json, body_blocks_zh_json, canonical_topic_id,
                    reading_meta_json, translation_fidelity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "article-public-1",
                    "中文标题",
                    "中文摘要",
                    "官方资讯",
                    "update",
                    json.dumps(["patch"]),
                    90,
                    "Blizzard News",
                    "https://worldofwarcraft.blizzard.com/news/1",
                    now,
                    "Official source",
                    now,
                    "中文正文",
                    "Original title",
                    "Original summary",
                    "Original body",
                    "llm",
                    "ready",
                    json.dumps([{"id": "patch", "label": "Patch"}]),
                    "",
                    "blizzard",
                    "official",
                    "approved",
                    "official_verified",
                    json.dumps(["official"]),
                    json.dumps([{"type": "paragraph", "text": "中文正文"}]),
                    "news:1",
                    json.dumps({"estimatedReadingMinutes": 1}),
                    "source_translation",
                ),
            )
            conn.execute(
                """
                INSERT INTO news_discovery_queue (
                    id, canonical_topic_id, source_id, source_name, source_tier, source_url,
                    original_title, published_at, status, attempts, last_error, payload_json,
                    discovered_at, updated_at, processed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "article-public-1",
                    "news:1",
                    "blizzard",
                    "Blizzard News",
                    "official",
                    "https://worldofwarcraft.blizzard.com/news/1",
                    "Original title",
                    now,
                    "published",
                    1,
                    "",
                    json.dumps({"id": "article-public-1"}),
                    now,
                    now,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO news_refresh_runs (id, refresh_mode, refreshed_at, accepted_count, rejected_count, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (3, "scheduled", now, 1, 0, json.dumps({"publishedCount": 1})),
            )
            conn.execute(
                """
                INSERT INTO websim_sync_state (key, value_json, updated_at)
                VALUES (?, ?, ?)
                """,
                ("gearCatalog", json.dumps({"status": "partial", "itemCount": 756}), now),
            )
            conn.execute(
                """
                INSERT INTO websim_season_state (
                    key, season_id, season_label, season_revision, locale, data_status,
                    verified_at, expires_at, source_refs_json, payload_json, active, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "active",
                    "season-pg",
                    "Season PG",
                    "season-pg-1",
                    "zh_CN",
                    "verified",
                    now,
                    "2099-01-01T00:00:00+00:00",
                    json.dumps([{"type": "official"}]),
                    json.dumps({"seasonRevision": "season-pg-1"}),
                    1,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_season_dungeons (
                    id, season_id, season_revision, dungeon_id, instance_id, name,
                    short_name, timer_seconds, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "season-dungeon-a",
                    "season-pg",
                    "season-pg-1",
                    "dungeon-a",
                    "1300",
                    "Dungeon A",
                    "DA",
                    1800,
                    json.dumps({"sourceRefs": [{"type": "journal"}]}),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_instances (id, name, category, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("1300", "Dungeon A", "dungeon", json.dumps({"id": "1300"}), now),
            )
            conn.execute(
                """
                INSERT INTO websim_encounters (id, instance_id, name, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("encounter-a", "1300", "Encounter A", json.dumps({"id": "encounter-a"}), now),
            )
            conn.execute(
                """
                INSERT INTO websim_items (id, name, slot, quality, icon_url, payload_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "item-a",
                    "Item A",
                    "trinket1",
                    "epic",
                    "https://render.worldofwarcraft.com/icon-a.jpg",
                    json.dumps({"id": "item-a", "itemLevel": 678, "sourceStatus": "verified"}),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_gear_sources (
                    id, item_id, source_type, source_label, instance_id, encounter_id,
                    difficulty_key, season_revision, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "source-a",
                    "item-a",
                    "dungeon",
                    "Encounter A",
                    "1300",
                    "encounter-a",
                    "mythic",
                    "season-pg-1",
                    json.dumps({"recommendationScore": 88}),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_gear_variants (
                    id, item_id, slot, variant_key, label, source_type, difficulty_key,
                    item_level, simc_options_json, status, blockers_json, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "variant-a",
                    "item-a",
                    "trinket1",
                    "item-a-mythic",
                    "Mythic Item A",
                    "dungeon",
                    "mythic",
                    678,
                    json.dumps({"ilevel": 678}),
                    "verified",
                    json.dumps([]),
                    json.dumps({"sourceStatus": "verified"}),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_gear_mod_options (
                    id, option_type, name, applicable_slots_json, simc_options_json,
                    status, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "socket-a",
                    "socket",
                    "Gem A",
                    json.dumps(["trinket1"]),
                    json.dumps({"gem_id": "213743"}),
                    "verified",
                    json.dumps({"displayLabel": "Gem A"}),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_community_gear_templates (
                    id, class_key, spec_key, name, source_key, source_name, source_url,
                    source_status, status, signature, source_refs_json, gear_items_json,
                    raw_string, ready_slot_count, missing_slots_json, analysis_window,
                    payload_json, updated_at, expires_at, scan_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "community-gear-mage-frost",
                    "mage",
                    "frost",
                    "Raider.IO community gear",
                    "raiderio_observed_profile",
                    "Raider.IO observed gear",
                    "https://example.com/community-gear",
                    "synced",
                    "complete",
                    "sig-community-gear",
                    json.dumps([{"type": "raiderio"}]),
                    json.dumps([{"slot": "head", "itemId": "item-a", "simcReady": True}]),
                    "head=item-a,bonus_id=1",
                    16,
                    json.dumps([]),
                    "2026-W27",
                    json.dumps({"templateEvidence": {"sourceKey": "raiderio_observed_profile"}}),
                    now,
                    "2099-01-01T00:00:00+00:00",
                    "scan-pg",
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_community_gear_templates (
                    id, class_key, spec_key, name, source_key, source_name, source_url,
                    source_status, status, signature, source_refs_json, gear_items_json,
                    raw_string, ready_slot_count, missing_slots_json, analysis_window,
                    payload_json, updated_at, expires_at, scan_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "default-template-mage-frost-mplus-mixed-route",
                    "mage",
                    "frost",
                    "默认模板 · 法师冰霜",
                    "default_template",
                    "默认模板",
                    "",
                    "verified",
                    "complete",
                    "sig-default-gear",
                    json.dumps([{"type": "default_template"}]),
                    json.dumps([{"slot": "head", "itemId": "item-a", "simcReady": True}]),
                    "head=item-a,bonus_id=1",
                    16,
                    json.dumps([]),
                    "默认模板由 verified 当前赛季装备候选和 M+ mixed-route 绿字权重生成。",
                    json.dumps({"scenarioKey": "mplus_mixed_route", "templateEvidence": {"sourceKey": "default_template"}}),
                    now,
                    "2099-01-01T00:00:00+00:00",
                    "scan-pg",
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_loot (
                    id, instance_id, encounter_id, item_id, name, slot, quality, icon_url,
                    payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "loot-a",
                    "1300",
                    "encounter-a",
                    "item-a",
                    "Item A",
                    "trinket1",
                    "epic",
                    "https://render.worldofwarcraft.com/icon-a.jpg",
                    json.dumps({"id": "loot-a"}),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO raiderio_cache (key, value_json, updated_at, expires_at, stale_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                ("raiderio:season", json.dumps({"sourceStatus": "verified"}), now, now, now),
            )
            conn.commit()

        with self.backend.db_connection() as conn:
            plan = data_copy_plan.build_postgres_copy_plan(conn)

        self.assertEqual(plan["tables"]["content.sources"][0]["source_key"], "blizzard")
        self.assertEqual(plan["tables"]["content.sources"][0]["id"], content_uuid("content.sources", "blizzard"))
        self.assertEqual(plan["tables"]["content.raw_articles"][0]["id"], "article-public-1")
        self.assertEqual(
            plan["tables"]["content.raw_articles"][0]["source_id"],
            content_uuid("content.sources", "blizzard"),
        )
        self.assertEqual(
            plan["tables"]["content.article_evidence"][0]["id"],
            identity_shadow_plan.stable_pg_uuid("content.article_evidence", "7"),
        )
        self.assertEqual(plan["tables"]["content.article_evidence"][0]["article_id"], "article-public-1")
        self.assertEqual(plan["tables"]["content.articles"][0]["translation_fidelity"], "source_translation")
        self.assertEqual(plan["tables"]["content.discovery_queue"][0]["status"], "published")
        self.assertEqual(plan["tables"]["content.refresh_runs"][0]["id"], 3)
        self.assertEqual(plan["tables"]["cache.websim_sync_state"][0]["id"], "gearCatalog")
        self.assertEqual(plan["tables"]["cache.websim_season_state"][0]["season_revision"], "season-pg-1")
        self.assertEqual(plan["tables"]["cache.websim_season_dungeons"][0]["instance_id"], "1300")
        self.assertEqual(plan["tables"]["cache.websim_items"][0]["id"], "item-a")
        self.assertEqual(plan["tables"]["cache.websim_items"][0]["item_level"], 678)
        self.assertEqual(plan["tables"]["cache.websim_gear_sources"][0]["id"], identity_shadow_plan.stable_pg_uuid("cache.websim_gear_sources", "source-a"))
        self.assertEqual(plan["tables"]["cache.websim_gear_sources"][0]["source_label"], "Encounter A")
        self.assertEqual(plan["tables"]["cache.websim_gear_sources"][0]["season_revision"], "season-pg-1")
        self.assertEqual(plan["tables"]["cache.websim_gear_variants"][0]["id"], identity_shadow_plan.stable_pg_uuid("cache.websim_gear_variants", "variant-a"))
        self.assertEqual(plan["tables"]["cache.websim_gear_variants"][0]["status"], "verified")
        self.assertEqual(plan["tables"]["cache.websim_gear_variants"][0]["simc_options_json"], {"ilevel": 678})
        self.assertEqual(plan["tables"]["cache.websim_gear_mod_options"][0]["id"], identity_shadow_plan.stable_pg_uuid("cache.websim_gear_mod_options", "socket-a"))
        self.assertIsNone(plan["tables"]["cache.websim_gear_mod_options"][0]["variant_id"])
        self.assertTrue(plan["tables"]["cache.websim_gear_mod_options"][0]["is_visible"])
        self.assertEqual(plan["tables"]["cache.websim_gear_mod_options"][0]["applicable_slots_json"], ["trinket1"])
        self.assertIn("cache.websim_community_gear_templates", plan["tables"])
        self.assertEqual(
            {row["source_key"] for row in plan["tables"]["cache.websim_community_gear_templates"]},
            {"raiderio_observed_profile", "default_template"},
        )
        default_template = next(
            row for row in plan["tables"]["cache.websim_community_gear_templates"] if row["source_key"] == "default_template"
        )
        self.assertEqual(default_template["source_name"], "默认模板")
        self.assertEqual(default_template["ready_slot_count"], 16)
        self.assertEqual(default_template["payload_json"]["scenarioKey"], "mplus_mixed_route")
        self.assertEqual(plan["tables"]["cache.websim_instances"][0]["id"], "1300")
        self.assertEqual(plan["tables"]["cache.websim_encounters"][0]["instance_id"], "1300")
        self.assertEqual(plan["tables"]["cache.websim_loot"][0]["item_id"], "item-a")
        self.assertEqual(plan["tables"]["cache.raiderio_cache"][0]["cache_key"], "raiderio:season")
        self.assertEqual(plan["totals"]["rowsByTable"]["content.articles"], 1)
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_sync_state"], 1)
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_gear_sources"], 1)
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_gear_variants"], 1)
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_gear_mod_options"], 1)
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_community_gear_templates"], 2)
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_loot"], 1)

    def test_data_copy_plan_preserves_duplicate_content_evidence_rows_by_sqlite_id(self):
        from server.migrations.postgres import data_copy_plan

        now = "2026-06-27T12:45:00+00:00"
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            for evidence_id in (7, 8):
                conn.execute(
                    """
                    INSERT INTO news_article_evidence (
                        id, article_id, canonical_topic_id, source_id, source_name, source_tier,
                        evidence_url, verification_status, conflict_reason, checked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence_id,
                        "article-public-duplicate",
                        "news:duplicate",
                        "blizzard",
                        "Blizzard News",
                        "official",
                        "https://evidence",
                        "verified",
                        "",
                        now,
                    ),
                )
            conn.commit()

        with self.backend.db_connection() as conn:
            plan = data_copy_plan.build_postgres_copy_plan(conn)

        evidence_ids = [row["id"] for row in plan["tables"]["content.article_evidence"]]
        self.assertEqual(len(evidence_ids), 2)
        self.assertEqual(len(set(evidence_ids)), 2)

    def test_data_copy_plan_exports_websim_talent_cache_rows(self):
        from server.migrations.postgres import data_copy_plan
        from server.migrations.postgres import identity_shadow_plan

        now = "2026-06-28T03:30:00+00:00"
        with closing(sqlite3.connect(os.environ["WOW_NEWS_DB"])) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(
                """
                INSERT INTO websim_talents (
                    id, class_key, spec_key, tree_id, row_index, col_index, spell_id,
                    name, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "talent-a",
                    "mage",
                    "frost",
                    "spec",
                    1,
                    2,
                    12345,
                    "Talent A",
                    json.dumps({"treeType": "spec", "rankEntries": [{"spellId": 12345, "points": 1}]}),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_spell_details (
                    id, spell_id, name, description, icon_url, locale, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "spell-a",
                    12345,
                    "Talent A",
                    "Deals frost damage.",
                    "https://render.worldofwarcraft.com/spell-a.jpg",
                    "zh_CN",
                    json.dumps({"source": "simulationcraft"}),
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO websim_profile_presets (
                    id, class_key, spec_key, name, profile, payload_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("preset-a", "mage", "frost", "Preset A", "mage=Preset", json.dumps({"source": "simc"}), now),
            )
            conn.execute(
                """
                INSERT INTO websim_community_talent_templates (
                    id, class_key, spec_key, hero_key, scenario_key, name, flow_label,
                    source_key, source_name, source_url, raw_import_code, websim_export_code,
                    talent_state_json, sample_count, max_key_level, analysis_window,
                    source_status, status, payload_json, updated_at, expires_at,
                    signature, source_refs_json, scan_run_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "template-a",
                    "mage",
                    "frost",
                    "spellslinger",
                    "mythic_plus",
                    "Template A",
                    "M+",
                    "manual_fixture",
                    "Manual Fixture",
                    "https://example.test/template",
                    "talents=abc",
                    "websim:mage:frost",
                    json.dumps({"selectedNodes": [{"id": "talent-a", "rank": 1}]}),
                    12,
                    10,
                    "weekly",
                    "verified",
                    "verified",
                    json.dumps({"playerId": "mage-a"}),
                    now,
                    "2099-01-01T00:00:00+00:00",
                    "sig-a",
                    json.dumps([{"type": "manual"}]),
                    "scan-a",
                ),
            )
            conn.commit()

        with self.backend.db_connection() as conn:
            plan = data_copy_plan.build_postgres_copy_plan(conn)

        self.assertEqual(plan["tables"]["cache.websim_talents"][0]["id"], "talent-a")
        self.assertEqual(plan["tables"]["cache.websim_talents"][0]["spell_id"], 12345)
        self.assertEqual(plan["tables"]["cache.websim_spell_details"][0]["spell_id"], 12345)
        self.assertEqual(plan["tables"]["cache.websim_profile_presets"][0]["id"], "preset-a")
        self.assertEqual(
            plan["tables"]["cache.websim_community_talent_templates"][0]["id"],
            identity_shadow_plan.stable_pg_uuid("cache.websim_community_talent_templates", "template-a"),
        )
        self.assertEqual(plan["tables"]["cache.websim_community_talent_templates"][0]["talent_state_json"]["selectedNodes"][0]["id"], "talent-a")
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_talents"], 1)
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_spell_details"], 1)
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_profile_presets"], 1)
        self.assertEqual(plan["totals"]["rowsByTable"]["cache.websim_community_talent_templates"], 1)

    def test_data_copy_plan_cli_can_emit_sql_without_connecting_to_postgres(self):
        self.login_formal_user(openid="openid-sql", unionid="")
        script = Path("server/migrations/postgres/data_copy_plan.py")

        result = subprocess.run(
            [sys.executable, str(script), "--format", "sql", os.environ["WOW_NEWS_DB"]],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertIn("BEGIN;", result.stdout)
        self.assertIn("INSERT INTO identity.users", result.stdout)
        self.assertIn("INSERT INTO identity.user_identities", result.stdout)
        self.assertIn("COMMIT;", result.stdout)

    def test_data_copy_plan_supports_legacy_simulator_tasks_without_worker_columns(self):
        from server.migrations.postgres import data_copy_plan

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE wechat_users (
                id INTEGER PRIMARY KEY,
                openid TEXT NOT NULL,
                unionid TEXT NOT NULL DEFAULT '',
                nickname TEXT NOT NULL DEFAULT '',
                avatar_url TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE simulator_tasks (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                mode TEXT NOT NULL,
                status TEXT NOT NULL,
                request_json TEXT NOT NULL,
                analysis_json TEXT NOT NULL,
                summary_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO wechat_users (
                id, openid, unionid, nickname, avatar_url, created_at, updated_at
            ) VALUES (1, 'openid-legacy', '', 'Legacy', '', '2026-06-27T12:00:00+00:00', '2026-06-27T12:00:00+00:00')
            """
        )
        conn.execute(
            """
            INSERT INTO simulator_tasks (
                id, user_id, mode, status, request_json, analysis_json, summary_json, created_at, updated_at
            ) VALUES (
                'legacy-task', 1, 'simcraft_template', 'queued', '{}', '{}', '{"state":"queued"}',
                '2026-06-27T12:30:00+00:00', '2026-06-27T12:31:00+00:00'
            )
            """
        )

        plan = data_copy_plan.build_postgres_copy_plan(conn)

        task = plan["tables"]["app.simulator_tasks"][0]
        self.assertEqual(task["queued_at"], "2026-06-27T12:30:00+00:00")
        self.assertIsNone(task["started_at"])
        self.assertIsNone(task["finished_at"])
        self.assertEqual(task["attempt"], 0)
        self.assertEqual(task["locked_by"], "")
        self.assertIsNone(task["heartbeat_at"])
        self.assertFalse(task["cancel_requested"])
        self.assertEqual(task["last_error"], "")

    def test_data_copy_plan_dedupes_gear_variants_by_item_and_variant_key(self):
        from server.migrations.postgres import data_copy_plan, identity_shadow_plan

        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE websim_gear_variants (
                id TEXT PRIMARY KEY,
                item_id TEXT NOT NULL,
                slot TEXT NOT NULL,
                variant_key TEXT NOT NULL,
                label TEXT NOT NULL,
                source_type TEXT NOT NULL,
                difficulty_key TEXT NOT NULL,
                item_level INTEGER NOT NULL,
                simc_options_json TEXT NOT NULL,
                status TEXT NOT NULL,
                blockers_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO websim_gear_variants (
                id, item_id, slot, variant_key, label, source_type, difficulty_key,
                item_level, simc_options_json, status, blockers_json, payload_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "loot-partial-151299-shoulder",
                    "151299",
                    "shoulder",
                    "needs-variant",
                    "Dungeon partial",
                    "dungeon",
                    "needs-variant",
                    0,
                    "{}",
                    "partial",
                    "[]",
                    "{}",
                    "2026-06-28T12:02:00+00:00",
                ),
                (
                    "set-partial-1332-151299-shoulder",
                    "151299",
                    "shoulder",
                    "needs-variant",
                    "Tier partial",
                    "tier_set",
                    "needs-variant",
                    0,
                    "{}",
                    "partial",
                    "[]",
                    "{}",
                    "2026-06-28T12:01:00+00:00",
                ),
            ],
        )

        rows = data_copy_plan.build_websim_gear_variant_rows(conn)

        self.assertEqual(len(rows), 1)
        self.assertEqual(
            rows[0]["id"],
            identity_shadow_plan.stable_pg_uuid(
                "cache.websim_gear_variants",
                "set-partial-1332-151299-shoulder",
            ),
        )
        self.assertEqual(rows[0]["source_type"], "tier_set")
