import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import get_settings
from bot.handlers import router
from bot.workers import deliver_loop, reminder_loop

log = logging.getLogger("bot")


async def main():
    s = get_settings()
    logging.basicConfig(level=s.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    if not s.bot_token:
        raise SystemExit("BOT_TOKEN .env da ko'rsatilmagan")
    if s.redis_url:
        from aiogram.fsm.storage.redis import RedisStorage

        storage = RedisStorage.from_url(s.redis_url)
    else:
        storage = MemoryStorage()  # qayta ishga tushganda oqimlar yo'qoladi; production uchun REDIS_URL bering
    bot = Bot(token=s.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    tasks = [asyncio.create_task(deliver_loop(bot)), asyncio.create_task(reminder_loop())]
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot)  # long polling; webhook rejimi hozircha yo'q
    finally:
        for t in tasks:
            t.cancel()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
