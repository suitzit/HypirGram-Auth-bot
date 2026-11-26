from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def back_main():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back:main")]
    ])
    return kb

def back_shop():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back:shop")]
    ])
    return kb

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
                InlineKeyboardButton(text="Скачать HypirGram", callback_data="download", style="success"),
                InlineKeyboardButton(text="О боте", callback_data="about_bot", style="primary")
            ]
    ])

    return kb

def shop():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Купить Stars", callback_data="pay_stars", style="success"),
            ],
            [
                InlineKeyboardButton(text="Верификации", callback_data="verification", style="success"),
                InlineKeyboardButton(text="Приобрести NFT", callback_data="pay_nft", style="success")
            ],
            [
                InlineKeyboardButton(text="NFT Username", callback_data="pay_nftu", style="success"),
                InlineKeyboardButton(text="Номера +888", callback_data="pay_anon", style="success")
            ],
            [
                InlineKeyboardButton(text="Назад", callback_data="back:main")
            ]
        ]
    )

    return kb