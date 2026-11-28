from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery, 
    Message,
    LabeledPrice,
    PreCheckoutQuery
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Users
from keyboards import menu
from services.phone_generate import generate_phone
from texts import messages

router = Router()


@router.message(CommandStart())
async def start(message: Message, session: AsyncSession):

    user_id = str(message.from_user.id)
    phone = generate_phone()
    result = await session.execute(
        select(Users).where(Users.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        await message.answer(messages.EASTER_EGG_TEXT, parse_mode=ParseMode.HTML)

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
        await message.answer(messages.WELCOME_TEXT,
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
            messages.WELCOME_TEXT,
            reply_markup=menu.main_menu(),
            parse_mode=ParseMode.HTML
        )
    elif destination == "shop":
        await callback.message.edit_text(
            messages.SHOP_TEXT,
            reply_markup=menu.shop(),
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
        messages.SHOP_TEXT,
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
    await callback.message.edit_text("Здесь вы можете приобрести HypirGram Stars ⭐\nПросто выбирете пакет и проведи оплату!", reply_markup=menu.pay_stars())

@router.callback_query(F.data.startswith("stars:"))
async def stars(callback: CallbackQuery) -> None:
    destination = callback.data.split(":")[1]

    if destination == "1000":
        await callback.answer()
        await callback.message.answer_invoice(
            title="Покупка звезд:",
            description="1000 ⭐ на баланс в HypirGram",
            payload=f"vip:{callback.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=10)]
        )
    elif destination == "2000":
        await callback.answer()
        await callback.message.answer_invoice(
            title="Покупка звезд:",
            description="2000 ⭐ на баланс в HypirGram",
            payload=f"vip:{callback.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=20)]
        )
    elif destination == "4000":
        await callback.answer()
        await callback.message.answer_invoice(
            title="Покупка звезд:",
            description="4000 ⭐ на баланс в HypirGram",
            payload=f"vip:{callback.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=40)]
        )
    elif destination == "6000":
        await callback.answer()
        await callback.message.answer_invoice(
            title="Покупка звезд:",
            description="6000 ⭐ на баланс в HypirGram",
            payload=f"vip:{callback.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=60)]
        )
    elif destination == "8000":
        await callback.answer()
        await callback.message.answer_invoice(
            title="Покупка звезд:",
            description="8000 ⭐ на баланс в HypirGram",
            payload=f"vip:{callback.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=80)]
        )
    elif destination == "10000":
        await callback.answer()
        await callback.message.answer_invoice(
            title="Покупка звезд:",
            description="10000 ⭐ на баланс в HypirGram",
            payload=f"vip:{callback.from_user.id}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label="XTR", amount=100)]
        )
    elif destination == "user":
        await callback.answer()
        await callback.message.answer("🛠️ В разарботке", reply_markup=menu.back_shop())



@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    await message.answer(f"Оплата прошла успешно\n<code>{message.successful_payment.telegram_payment_charge_id}</code>")

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
