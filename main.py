import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiohttp import web

from config import FILENAME, TOKEN
from database.engine import init_db
from handlers import user
from middlewares.db_middleware import DbSessionMiddleware
from webhook import create_app

logging.basicConfig(filename=FILENAME, 
                    level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%d.%m.%Y %H.%M.%S",
                    encoding="utf-8",
                    )
logger = logging.getLogger(__name__ )


async def main():

    bot = Bot(TOKEN)
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware())
    dp.include_router(user.router)

    logger.info("БОТ ЗАПУЩЕН!")
    print("Бот запущен!")

    await init_db()

    # Подключение веб-хука
    app = create_app(bot)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        host="0.0.0.0",
        port=8080
    )

    await site.start()

    logger.info("HTTP WEBHOOK SERVER STARTED ON PORT 8080")

    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("БОТ ВЫКЛЮЧЕН!")
        print("Бот выключен!")
