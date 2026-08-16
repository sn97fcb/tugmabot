from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def make_buttons(qoida, viloyat, elon):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📩 Еълон жойлаш",
                    url=elon
                ),
                InlineKeyboardButton(
                    text="❗️ Канал қоидаси",
                    url=qoida
                )
            ]
        ]
    )
