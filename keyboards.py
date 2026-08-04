from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def make_buttons(qoida, viloyat, elon):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📜 Kanal qoidasi",
                    url=qoida
                ),
                InlineKeyboardButton(
                    text="🌍 Boshqa viloyatlar",
                    url=viloyat
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ E'lon joylash",
                    url=elon
                )
            ]
        ]
    )