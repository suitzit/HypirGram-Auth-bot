from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Профиль", callback_data="profile", style="primary")
            ],
            [
                InlineKeyboardButton(text="Магазин", callback_data="shop", style="primary"),
                InlineKeyboardButton(text="Мои номера", callback_data="my_number", style="primary")
            ],
            [
                InlineKeyboardButton(text="О боте", callback_data="abuot_bot", style="primary")
            ]
    ])

    return kb
