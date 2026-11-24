import asyncio
import re
from collections import Counter
from random import randint

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Users

router = Router()


def is_valid(phone: str) -> bool:
    if re.search(r"(\d)\1", phone):
        return False

    counts = Counter(phone)

    return max(counts.values()) <= 4

def generate_phone():
    while True:
        phone = str(randint(10000000000, 999999999999))

        if not is_valid(phone):
            continue

        return phone


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession):
    user_id = str(message.from_user.id)
    phone = generate_phone()
    result = await session.execute(
        select(Users).where(Users.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = Users(user_id=user_id, phone=phone)
        session.add(user)
        await session.commit()
    else:
        phone = user.phone

    await message.answer(f"📞Ваш номер телефона для регистрации в HypirGram: +<code>{phone}</code>\n\n"
                         "<blockquote><i>❗Внимание, этот номер <b>только для HypirGram</b>\n" \
                         "В любом другом мессенджере номер <b>не будет работать!</b></i></blockquote>",
                         parse_mode=ParseMode.HTML
                         )
    
    await asyncio.sleep(2)

    code = 12345

    await message.answer(f"💬Ваш код для входа в аккаунт: <code>{code}</code>\n"
                         "<blockquote><i>❗Данный код для входа <b>в HypirGram</b></i></blockquote>",
                         parse_mode=ParseMode.HTML
                         )

@router.message(Command("help"))
async def help(message: Message):
    await message.answer("Пока нет помощи...")

