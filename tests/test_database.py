import sqlite3
import tempfile
import unittest
import json
from pathlib import Path

import database
from scheduler import cancel_job, schedule_post, scheduler


class DatabaseMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = Path(self.temp.name) / "tugmabot.db"
        conn = sqlite3.connect(database.DATABASE_PATH)
        try:
            conn.execute("CREATE TABLE users(user_id INTEGER PRIMARY KEY, qoida TEXT, viloyat TEXT, elon TEXT)")
            conn.execute("INSERT INTO users VALUES(1255705034, 'https://t.me/rule', NULL, 'https://t.me/ad')")
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_migration_preserves_existing_admin_links(self):
        database.init_db()
        self.assertEqual(database.get_links(1255705034),
                         ("https://t.me/rule", None, "https://t.me/ad", None))
        database.set_link(6201110478, "matnlink", "https://t.me/jobs")
        self.assertEqual(database.get_links(6201110478)[3], "https://t.me/jobs")
        self.assertEqual(database.get_links(1255705034)[3], None)

    def test_channel_schedule_and_delivery_claim_persist(self):
        database.init_db()
        database.add_channel("Qo‘qon", "Kanal 1", "-1001234567890")
        with database.connect() as conn:
            channel_id = conn.execute("SELECT id FROM channels").fetchone()[0]
            conn.execute("UPDATE channels SET can_post=1 WHERE id=?", (channel_id,))
        post_id = database.create_post(1255705034, "Sinov", None, "daily", [channel_id],
                                       weekdays=[], run_time="09:30")
        self.assertTrue(database.claim_delivery(post_id, channel_id, "2026-11-22T09:30"))
        self.assertFalse(database.claim_delivery(post_id, channel_id, "2026-11-22T09:30"))
        database.finish_delivery(post_id, channel_id, "2026-11-22T09:30", message_id=456)
        with database.connect() as conn:
            row = conn.execute("SELECT status,telegram_message_id FROM published_messages").fetchone()
        self.assertEqual(tuple(row), ("sent", 456))

    def test_weekly_job_keeps_an_individual_time_per_day(self):
        database.init_db()
        database.add_channel("Namangan", "Kanal", "-1001234567892")
        with database.connect() as conn:
            channel_id = conn.execute("SELECT id FROM channels").fetchone()[0]
            conn.execute("UPDATE channels SET can_post=1 WHERE id=?", (channel_id,))
        run_time = json.dumps({"0": "09:00", "3": "18:30"})
        post_id = database.create_post(1255705034, "Sinov", None, "weekly", [channel_id],
                                       weekdays=[0, 3], run_time=run_time)
        post, _ = database.get_post(post_id, 1255705034)
        schedule_post(object(), post)
        ids = {job.id for job in scheduler.get_jobs() if job.id.startswith(f"post-{post_id}-")}
        self.assertEqual(ids, {f"post-{post_id}-w0", f"post-{post_id}-w3"})
        cancel_job(post_id)


if __name__ == "__main__":
    unittest.main()
