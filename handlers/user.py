import re
from collections import Counter
from pathlib import Path
from random import choice, randint

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Users
from keyboards import menu

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
        await message.answer(f"📞Ваш номер телефона для регистрации в HypirGram:\n\n +<code>{phone}</code>\n\n"
                                    "<blockquote><i>❗Внимание, этот номер <b>только для регистрации в HypirGram</b>\n" \
                                    "В любом другом мессенджере номер <b>не будет работать!</b></i></blockquote>",
                                    parse_mode=ParseMode.HTML
                            )
    else:
        phone = user.phone
        await message.answer(
                   "✨ Твой HypirGram может больше!\n\n"
                   "<blockquote>" \
                   "Здесь можно заглянуть в свой профиль, открыть магазин и перейти к своим номерам.\n" \
                   "Всё под рукой, чтобы не приходилось искать нужный раздел дольше, чем выбирать текст для ответа.\n\n" \
                   "Хочешь узнать больше? Нажми «О боте». А если готов попробовать HypirGram — кнопка скачивания уже ждёт тебя."
                   "</blockquote>\n\n" \
                   "Выбирай, с чего начнем? 👇",
                   reply_markup=menu.main_menu(),
                   parse_mode=ParseMode.HTML
               )
    
@router.message(Command("help"))
async def help(message: Message):
    await message.answer("Пока нет помощи...")


@router.callback_query(F.data.startswith("back:"))
async def back(callback: CallbackQuery):
    destination = callback.data.split(":")[1]

    if destination == "main":
        await callback.message.edit_text(
                   "✨ Твой HypirGram может больше!\n\n"
                   "<blockquote>" \
                   "Здесь можно заглянуть в свой профиль, открыть магазин и перейти к своим номерам.\n" \
                   "Всё под рукой, чтобы не приходилось искать нужный раздел дольше, чем выбирать текст для ответа.\n\n" \
                   "Хочешь узнать больше? Нажми «О боте». А если готов попробовать HypirGram — кнопка скачивания уже ждёт тебя."
                   "</blockquote>\n\n" \
                   "Выбирай, с чего начнем? 👇",
            reply_markup=menu.main_menu(),
            parse_mode=ParseMode.HTML
        )

@router.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    username = str(callback.from_user.username)
    balance_of_hg = "скоро"

    await callback.message.edit_text(
        "Профиль\n\n"
        f"ID: <code>{user_id}</code>\n"
        f"Username: @{username}\n\n"
        f"Баланс в HypirGram: {balance_of_hg}\n",
        parse_mode=ParseMode.HTML,
        reply_markup=menu.back_main()
    )

@router.callback_query(F.data == "shop")
async def shop(callback: CallbackQuery):
    await callback.message.edit_text(
        "<b>Магазин</b>\n\n" \
        "<blockquote>"
        "🛍 Всё нужное для твоего HypirGram — в одном месте!\n\n"
        "Покупай Stars для подарков и любимых сервисов,\n"
        "выбирай NFT Username для запоминающегося профиля или загляни в раздел номеров +888.\n" 
        "А если интересуют верификации — для них тоже есть отдельная кнопка."
        "</blockquote>\n\n"
        "Выбирай нужный раздел ниже: пора найти что-нибудь для себя ✨",
        parse_mode=ParseMode.HTML,
        reply_markup=menu.shop()
    )

@router.callback_query(F.data == "my_number")
async def my_number(callback: CallbackQuery):
    await callback.message.edit_text("🛠️ В разработке...", reply_markup=menu.back_main())

@router.callback_query(F.data == "download")
async def download(callback: CallbackQuery):
    await callback.message.edit_text("🛠️ Клиент в разработке...", reply_markup=menu.back_main())

@router.callback_query(F.data == "about_bot")
async def about_bot(callback: CallbackQuery):
    await callback.message.edit_text("🛠️ В разработке...", reply_markup=menu.back_main())

@router.callback_query(F.data == "pay_stars")
async def pay_stars(callback: CallbackQuery):
    await callback.message.edit_text("🛠️ В разработке...", reply_markup=menu.back_shop())

@router.callback_query(F.data == "verification")
async def verification(callback: CallbackQuery):
    await callback.message.edit_text("🛠️ В разработке...", reply_markup=menu.back_shop())

@router.callback_query(F.data == "pay_nft")
async def pay_nft(callback: CallbackQuery):
    await callback.message.edit_text("🛠️ В разработке...", reply_markup=menu.back_shop())

@router.callback_query(F.data == "pay_nftu")
async def pay_nftu(callback: CallbackQuery):
    await callback.message.edit_text("🛠️ В разработке...", reply_markup=menu.back_shop())

@router.callback_query(F.data == "pay_anon")
async def pay_anon(callback: CallbackQuery):
    await callback.message.edit_text("🛠️ В разработке...", reply_markup=menu.back_shop())
