import asyncio

from aiogram import Bot, Dispatcher

from config import TOKEN
from database.engine import init_db
from handlers import user
from middlewares.db_middleware import DbSessionMiddleware


async def main():
    
    bot = Bot(TOKEN)
    dp = Dispatcher()

    dp.message.middleware(DbSessionMiddleware)
    dp.include_router(user.router)
    
    print("Бот запущен!")
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен!")
