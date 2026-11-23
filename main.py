import asyncio

from aiogram import Bot, Dispatcher

from config import TOKEN
from handlers import user


async def main():

    bot = Bot(TOKEN)
    dp = Dispatcher()

    dp.include_router(user.router)
    
    print("Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот выключен!")
    