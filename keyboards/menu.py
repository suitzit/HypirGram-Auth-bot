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

def pay_stars():
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1000 ⭐", callback_data="stars:1000", style="success"),
                InlineKeyboardButton(text="2000 ⭐", callback_data="stars:2000", style="success")
            ],
            [
                InlineKeyboardButton(text="4000 ⭐", callback_data="stars:4000", style="success"),
                InlineKeyboardButton(text="6000 ⭐", callback_data="stars:6000", style="success")
            ],
            [
                InlineKeyboardButton(text="8000 ⭐", callback_data="stars:8000", style="success"),
                InlineKeyboardButton(text="10000 ⭐", callback_data="stars:10000", style="success")
            ],
            [
                InlineKeyboardButton(text="Введите свою сумму", callback_data="stars:user", style="primary")
            ],
            [
                InlineKeyboardButton(text="Назад", callback_data="back:shop")
            ]
        ]
    )

    return kb