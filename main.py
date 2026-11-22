import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import TOKEN
from database import backup_database, init_db
from handlers import router
from scheduler import restore_jobs, scheduler


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    init_db()
    bot = Bot(token=TOKEN)
    dispatcher = Dispatcher()
    dispatcher.include_router(router)
    restore_jobs(bot)
    scheduler.add_job(backup_database, "cron", hour=3, minute=15,
                      id="sqlite-backup", replace_existing=True,
                      misfire_grace_time=86400)
    scheduler.start()
    logging.info("TugmaBot ishga tushdi")
    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
