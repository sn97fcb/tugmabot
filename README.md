# TugmaBot

Telegram bot for admin-specific link buttons and scheduled channel posts.

## Run locally

Use Python 3.12 and install `requirements.txt`. Set `TOKEN` in the environment, then run `python main.py`. The existing `tugmabot.db` is migrated in place: its `users` rows and saved links are retained, and the scheduling/channel tables are added.

Only the five admin IDs in `handlers.py` can use the bot. Link settings remain separate per admin. A new post can be scheduled for 1, 2, 3, 5, 7, 10, 15, or 30 occurrences. Choose daily or every other day, then enter one posting time; the post appears in the scheduled-posts list after confirmation. The bot rebuilds its schedule from SQLite after a restart. Older once, daily, and weekly schedules remain supported.

## Northflank deployment

Build from the repository's Dockerfile. Configure `TOKEN` as a secret environment variable and attach persistent storage mounted at `/app/data`. Keep the service at **one replica** and run only one bot service against that SQLite volume. On the first start, the entrypoint copies the repository's legacy database into the persistent volume; subsequent deploys use the persistent copy. A daily SQLite backup is kept under `/app/data/backups` for seven days.

For automatic GitHub deployments, connect this repository to the Northflank service, select the `main` branch, enable deploy-on-push, and ensure the service builds the Dockerfile. Those settings belong to the Northflank project and cannot be verified from this repository. Do not remove the persistent volume when redeploying.

The schedule uses `Asia/Tashkent`. Delivery claims are stored before the Telegram API call so concurrent scheduler instances and restarts do not resend the same occurrence. If Telegram returns an ambiguous network error, the post is marked as an error for admin review rather than automatically retried, because an automatic retry could create a duplicate. `TelegramRetryAfter` responses are retried up to three times.
