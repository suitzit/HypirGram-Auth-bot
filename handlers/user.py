import re
from collections import Counter
from random import randint, choice
from pathlib import Path

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

def random_file(folder: str | Path) -> Path:
    folder = Path(folder)

    if not folder.is_dir():
        raise NotADirectoryError(f"Не папка: {folder}")

    files = [p for p in folder.iterdir() if p.is_file()]

    if not files:
        raise FileNotFoundError(f"Не файл: {files}")

    return choice(files)

def random_code(file_path: Path) -> str | None:
    with open(file_path, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        return None
    
    return choice(lines).strip()

def generate_phone():
    while True:
        f = random_file("handlers/area_code")
        code = random_code(f)

        if f.stem == "code_with_nine_digits":
            number = randint(100000000, 999999999)
        elif f.stem == "code_with_ten_digits":
            number = randint(1000000000, 9999999999)
        else:
            continue

        phone = f"{code}{number}"

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

    await message.answer(f"📞Ваш номер телефона для регистрации в HypirGram:\n\n +<code>{phone}</code>\n\n"
                         "<blockquote><i>❗Внимание, этот номер <b>только для HypirGram</b>\n" \
                         "В любом другом мессенджере номер <b>не будет работать!</b></i></blockquote>",
                         parse_mode=ParseMode.HTML
                         )
    
@router.message(Command("help"))
async def help(message: Message):
    await message.answer("Пока нет помощи...")

