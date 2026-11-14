
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from html import escape

from database import cursor, db
from keyboards import make_buttons

router = Router()


# FAQAT SHU 5 TA AKKAUNT FOYDALANA OLADI
ADMIN_IDS = {
    1255705034,
    6201110478,
    6960879913,
    6683769327,
    1697916196
}


# Begona foydalanuvchilarga javob bermaydi
@router.message(lambda message: message.from_user.id not in ADMIN_IDS)
async def blocked_user(message: Message):
    return


def get_links(user_id):
    cursor.execute(
        "SELECT qoida, viloyat, elon, matnlink FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row:
        return row

    return None, None, None, None


@router.message(Command("start"))
async def start(message: Message):

    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (message.from_user.id,)
    )

    db.commit()

    await message.answer(
        "✅ TugmaBot tayyor.\n\n"
        "Havolalarni sozlash:\n"
        "/qoida https://...\n"
        "/viloyat https://...\n"
        "/elon https://...\n\n"
        "Oddiy matnli havola:\n"
        "/matnlink https://t.me/kanal\n"
        "/matnlink_off — havolani o'chirish\n\n"
        "/show — sozlamalarni ko'rish"
    )


@router.message(Command("qoida"))
async def set_qoida(message: Message):

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Misol:\n/qoida https://t.me/kanal")
        return

    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (message.from_user.id,)
    )

    cursor.execute(
        "UPDATE users SET qoida=? WHERE user_id=?",
        (parts[1].strip(), message.from_user.id)
    )

db.commit()
    await message.answer("✅ Qoida linki saqlandi.")


@router.message(Command("viloyat"))
async def set_viloyat(message: Message):

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer("Misol:\n/viloyat https://t.me/kanal")
        return

    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (message.from_user.id,)
    )

    cursor.execute(
        "UPDATE users SET viloyat=? WHERE user_id=?",
        (parts[1].strip(), message.from_user.id)
    )

    db.commit()
    await message.answer("✅ Viloyatlar linki saqlandi.")


@router.message(Command("viloyat_off"))
async def delete_viloyat(message: Message):

    cursor.execute(
        "UPDATE users SET viloyat=NULL WHERE user_id=?",
        (message.from_user.id,)
    )

    db.commit()

    await message.answer("✅ Viloyat tugmasi o'chirildi.")


@router.message(Command("elon"))
async def set_elon(message: Message):

    parts = message.text.split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Misol:\n/elon https://t.me/kanal")
        return

    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (message.from_user.id,)
    )

    cursor.execute(
        "UPDATE users SET elon=? WHERE user_id=?",
        (parts[1].strip(), message.from_user.id)
    )

    db.commit()
    await message.answer("✅ E'lon linki saqlandi.")


# Oddiy matn ichidagi Ishtopchi havolasini saqlash
@router.message(Command("matnlink"))
async def set_matnlink(message: Message):

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Misol:\n/matnlink https://t.me/kanal"
        )
        return

    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (message.from_user.id,)
    )

    cursor.execute(
        "UPDATE users SET matnlink=? WHERE user_id=?",
        (parts[1].strip(), message.from_user.id)
    )

    db.commit()

    await message.answer(
        "✅ Ishtopchi matn havolasi saqlandi."
    )


# Oddiy matn havolasini o'chirish
@router.message(Command("matnlink_off"))
async def delete_matnlink(message: Message):

    cursor.execute(
        "UPDATE users SET matnlink=NULL WHERE user_id=?",
        (message.from_user.id,)
    )

    db.commit()

    await message.answer(
        "✅ Ishtopchi matn havolasi o'chirildi."
    )


# Barcha sozlamalarni ko'rish
@router.message(Command("show"))
async def show(message: Message):

    qoida, viloyat, elon, matnlink = get_links(
        message.from_user.id
    )

    await message.answer(
        f"❗️ Qoida: {qoida or 'Kiritilmagan'}\n\n"
        f"🌍 Viloyat: {viloyat or 'Kiritilmagan'}\n\n"
        f"📩 E'lon: {elon or 'Kiritilmagan'}\n\n"
        f"🔗 Ishtopchi matn havolasi: {matnlink or 'Kiritilmagan'}"
    )


# Rasmli post tayyorlash
@router.message(lambda message: message.photo)
async def photo_handler(message: Message):

    qoida, viloyat, elon, matnlink = get_links(
        message.from_user.id
    )

    photo = message.photo[-1].file_id

    # Asl caption matnini HTML uchun xavfsiz formatlash
    caption = escape(message.caption or "")

    # Ishtopchi havolasini caption oxiriga qo'shish
    if matnlink:
        caption += (
            '\n\n<a href="' + escape(matnlink, quote=True) +
            '">🔗 𝗜𝘀𝗵𝘁𝗼𝗽𝗰𝗵𝗶</a>'
        )

    await message.answer_photo(
        photo=photo,
        caption=caption or None,
        parse_mode="HTML",
        reply_markup=make_buttons(
            qoida,
            viloyat,
            elon
        )
    )


@router.message()
async def other(message: Message):

    await message.answer(
        "❌ Faqat rasm + matn (caption) yuboring."
    )
