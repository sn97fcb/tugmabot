
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def make_buttons(qoida=None, viloyat=None, elon=None):
    buttons = []

    if elon:
        buttons.append(
            InlineKeyboardButton(
                text="📩 Еълон жойлаш",
                url=elon
            )
        )

    if qoida:
        buttons.append(
            InlineKeyboardButton(
                text="❗️ Канал қоидаси",
                url=qoida
            )
        )

    if viloyat:
        buttons.append(
            InlineKeyboardButton(
                text="🌍 Бошқа вилоятлар",
                url=viloyat
            )
        )

    if not buttons:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[buttons]
    )
