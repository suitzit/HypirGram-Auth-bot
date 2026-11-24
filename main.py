import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import FILENAME, TOKEN
from database.engine import init_db
from handlers import user
from middlewares.db_middleware import DbSessionMiddleware

logging.basicConfig(filename=FILENAME, 
                    level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%d.%m.%Y %H.%M.%S",
                    encoding="utf-8",
                    )
logger = logging.getLogger()


async def main():

    bot = Bot(TOKEN)
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware())
    dp.include_router(user.router)

    logger.info("БОТ ЗАПУЩЕН!")
    print("Бот запущен!")
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("БОТ ВЫКЛЮЧЕН!")
        print("Бот выключен!")
