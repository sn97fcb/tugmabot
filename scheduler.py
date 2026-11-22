"""Persistent scheduled delivery; jobs are rebuilt from SQLite on startup."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import InputMediaPhoto
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

import database
from keyboards import make_buttons

TASHKENT = ZoneInfo("Asia/Tashkent")
scheduler = AsyncIOScheduler(timezone=TASHKENT)


def _as_local(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=TASHKENT) if parsed.tzinfo is None else parsed.astimezone(TASHKENT)


def render_post(post):
    qoida, viloyat, elon, matnlink = database.get_links(post["admin_id"])
    text = escape(post["text"] or "")
    if matnlink:
        text += f'\n\n<a href="{escape(matnlink, quote=True)}">🔗 𝗜𝘀𝘩𝘵𝗼𝗽𝗰𝗵𝗶</a>'
    return text, make_buttons(qoida, viloyat, elon)


async def _send_to_channel(bot: Bot, post, channel, occurrence_key: str) -> bool:
    if not database.claim_delivery(post["id"], channel["id"], occurrence_key):
        return database.delivery_was_sent(post["id"], channel["id"], occurrence_key)
    text, keyboard = render_post(post)
    try:
        for attempt in range(3):
            try:
                if post["photo_file_id"]:
                    msg = await bot.send_photo(
                        chat_id=channel["telegram_id"], photo=post["photo_file_id"],
                        caption=text or None, parse_mode="HTML", reply_markup=keyboard,
                    )
                else:
                    msg = await bot.send_message(
                        chat_id=channel["telegram_id"], text=text,
                        parse_mode="HTML", reply_markup=keyboard,
                    )
                database.finish_delivery(post["id"], channel["id"], occurrence_key,
                                         msg.message_id, is_photo=bool(post["photo_file_id"]),
                                         telegram_chat_id=str(channel["telegram_id"]))
                return True
            except TelegramRetryAfter as exc:
                if attempt == 2:
                    raise
                await asyncio.sleep(exc.retry_after + 1)
    except Exception as exc:
        # Keep the unique claim after an ambiguous network error to avoid duplicate posts.
        database.finish_delivery(post["id"], channel["id"], occurrence_key, error=str(exc)[:500])
        return False
    return False


async def publish_post(bot: Bot, post_id: int, occurrence_key: str, once: bool = False,
                       count_limited: bool = False) -> None:
    with database.connect() as db:
        post = db.execute("SELECT * FROM scheduled_posts WHERE id=?", (post_id,)).fetchone()
        channels = db.execute(
            "SELECT c.* FROM channels c JOIN scheduled_post_channels pc ON pc.channel_id=c.id WHERE pc.post_id=? AND c.active=1 AND c.can_post=1",
            (post_id,),
        ).fetchall() if post else []
    if not post:
        return
    if occurrence_key == "recurring":
        occurrence_key = datetime.now(TASHKENT).replace(second=0, microsecond=0).isoformat(timespec="minutes")
    results = await asyncio.gather(*(
        _send_to_channel(bot, post, channel, occurrence_key) for channel in channels
    ), return_exceptions=True)
    succeeded = bool(channels) and all(result is True for result in results)
    if once:
        database.set_post_result(post_id, "published" if succeeded else "error")
    elif count_limited:
        if succeeded:
            next_post = database.advance_limited_post(post_id, occurrence_key)
            if next_post and next_post["status"] == "active":
                schedule_post(bot, next_post)
        else:
            database.set_post_result(post_id, "error")
    elif not succeeded:
        database.set_post_result(post_id, "error")


def schedule_post(bot: Bot, post) -> None:
    post_id = post["id"]
    job_id = f"post-{post_id}"
    cancel_job(post_id)
    if post["status"] in {"paused", "published", "deleted"}:
        return
    if post["occurrences_total"] is not None:
        if post["status"] != "active" or int(post["occurrences_sent"] or 0) >= int(post["occurrences_total"]):
            return
        if not post["next_run_at"]:
            database.set_post_result(post_id, "error")
            return
        run_at = _as_local(post["next_run_at"])
        if run_at <= datetime.now(TASHKENT):
            run_at = datetime.now(TASHKENT)
        scheduler.add_job(publish_post, DateTrigger(run_date=run_at),
                          id=job_id,
                          args=[bot, post_id, post["next_run_at"], False, True],
                          misfire_grace_time=86400, coalesce=True, max_instances=1)
        return
    if post["schedule_type"] == "once":
        if post["status"] != "pending" or not post["run_at"]:
            return
        run_at = _as_local(post["run_at"])
        if run_at <= datetime.now(TASHKENT):
            run_at = datetime.now(TASHKENT)
        scheduler.add_job(publish_post, DateTrigger(run_date=run_at),
                          id=job_id, args=[bot, post_id, "once", True],
                          misfire_grace_time=86400, coalesce=True, max_instances=1)
        database.update_post_status(post_id, post["admin_id"], "pending")
    elif post["schedule_type"] == "daily":
        hour, minute = (post["run_time"] or "09:00").split(":")
        trigger = CronTrigger(hour=int(hour), minute=int(minute), timezone=TASHKENT)
        scheduler.add_job(publish_post, trigger, id=job_id,
                          args=[bot, post_id, "recurring", False],
                          misfire_grace_time=3600, coalesce=True, max_instances=1)
    elif post["schedule_type"] == "weekly":
        weekdays = json.loads(post["weekdays"] or "[]")
        times = json.loads(post["run_time"] or "{}")
        for weekday in weekdays:
            value = times.get(str(weekday))
            if not value:
                continue
            hour, minute = value.split(":")
            trigger = CronTrigger(day_of_week=weekday, hour=int(hour), minute=int(minute), timezone=TASHKENT)
            scheduler.add_job(publish_post, trigger, id=f"{job_id}-w{weekday}",
                              args=[bot, post_id, "recurring", False],
                              misfire_grace_time=3600, coalesce=True, max_instances=1)


def restore_jobs(bot: Bot) -> None:
    with database.connect() as db:
        posts = db.execute("SELECT * FROM scheduled_posts WHERE status IN ('pending','active')").fetchall()
    for post in posts:
        try:
            schedule_post(bot, post)
        except (ValueError, TypeError):
            database.set_post_result(post["id"], "error")


def cancel_job(post_id: int) -> None:
    prefix = f"post-{post_id}"
    for job in scheduler.get_jobs():
        if job.id == prefix or job.id.startswith(prefix + "-"):
            scheduler.remove_job(job.id)


async def sync_published_post(bot: Bot, post_id: int) -> tuple[int, int]:
    """Update previously published messages after an admin edits the post."""
    with database.connect() as db:
        post = db.execute("SELECT * FROM scheduled_posts WHERE id=?", (post_id,)).fetchone()
    if not post:
        return 0, 0
    text, keyboard = render_post(post)
    rows = database.published_messages(post_id)
    changed = failed = 0
    for row in rows:
        try:
            if post["photo_file_id"]:
                media = InputMediaPhoto(media=post["photo_file_id"], caption=text or None, parse_mode="HTML")
                msg = await bot.edit_message_media(
                    chat_id=row["telegram_id"], message_id=row["telegram_message_id"],
                    media=media, reply_markup=keyboard,
                )
                database.update_published_message(row["id"], msg.message_id, True)
            elif row["is_photo"]:
                await bot.delete_message(chat_id=row["telegram_id"], message_id=row["telegram_message_id"])
                msg = await bot.send_message(chat_id=row["telegram_id"], text=text or " ",
                                             parse_mode="HTML", reply_markup=keyboard)
                database.update_published_message(row["id"], msg.message_id, False)
            else:
                await bot.edit_message_text(chat_id=row["telegram_id"], message_id=row["telegram_message_id"],
                                            text=text or " ", parse_mode="HTML", reply_markup=keyboard)
            changed += 1
        except Exception:
            failed += 1
    return changed, failed
