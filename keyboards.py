from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def make_buttons(qoida=None, viloyat=None, elon=None):
    buttons = []
    if elon:
        buttons.append(InlineKeyboardButton(text="📩 Еълон жойлаш", url=elon))
    if qoida:
        buttons.append(InlineKeyboardButton(text="❗️ Канал қоидаси", url=qoida))
    if viloyat:
        buttons.append(InlineKeyboardButton(text="🌍 Бошқа вилоятлар", url=viloyat))
    if not buttons:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Yangi e'lon"), KeyboardButton(text="📅 Rejadagi e'lonlar")],
        [KeyboardButton(text="📍 Hududlar va kanallar"), KeyboardButton(text="⚙️ Sozlamalar")],
    ], resize_keyboard=True)


def regions_keyboard(regions):
    rows = [[InlineKeyboardButton(text=row["name"], callback_data=f"region:{row['id']}")] for row in regions]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channels_keyboard(channels, selected):
    rows = [[InlineKeyboardButton(
        text=f"{'✅' if row['id'] in selected else '▫️'} {row['name']}",
        callback_data=f"selectch:{row['id']}",
    )] for row in channels]
    rows.append([InlineKeyboardButton(text="Davom etish ➡️", callback_data="channels:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
