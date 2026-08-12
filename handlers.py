from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from database import cursor, db
from keyboards import make_buttons

router = Router()


def get_links(user_id):
    cursor.execute(
        "SELECT qoida, viloyat, elon FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row:
        return row

    return None, None, None


@router.message(Command("start"))
async def start(message: Message):

    cursor.execute(
        "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
        (message.from_user.id,)
    )

    db.commit()

    await message.answer(
        "✅ TugmaBot tayyor.\n\n"
        "/qoida https://...\n"
        "/viloyat https://...\n"
        "/elon https://..."
    )


@router.message(Command("qoida"))
async def set_qoida(message: Message):

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Misol:\n/qoida https://t.me/kanal"
        )
        return

    cursor.execute(
        """
        INSERT OR IGNORE INTO users(user_id)
        VALUES(?)
        """,
        (message.from_user.id,)
    )

    cursor.execute(
        """
        UPDATE users
        SET qoida=?
        WHERE user_id=?
        """,
        (
            parts[1],
            message.from_user.id
        )
    )

    db.commit()

    await message.answer("✅ Qoida linki saqlandi.")


@router.message(Command("viloyat"))
async def set_viloyat(message: Message):

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Misol:\n/viloyat https://t.me/kanal"
        )
        return

    cursor.execute(
        """
        UPDATE users
        SET viloyat=?
        WHERE user_id=?
        """,
        (
            parts[1],
            message.from_user.id
        )
    )

    db.commit()

    await message.answer(
        "✅ Viloyatlar linki saqlandi."
    )


@router.message(Command("elon"))
async def set_elon(message: Message):

    parts = message.text.split(maxsplit=1)

    if len(parts) != 2:
        await message.answer(
            "Misol:\n/elon https://t.me/kanal"
        )
        return

    cursor.execute(
        """
        UPDATE users
        SET elon=?
        WHERE user_id=?
        """,
        (
            parts[1],
            message.from_user.id
        )
    )

    db.commit()

    await message.answer(
        "✅ E'lon linki saqlandi."
    )


@router.message(Command("show"))
async def show(message: Message):

    qoida, viloyat, elon = get_links(
        message.from_user.id
    )

    await message.answer(
        f"📜 {qoida}\n\n"
        f"🌍 {viloyat}\n\n"
        f"✅ {elon}"
    )

@router.message(lambda message: message.photo)
async def photo_handler(message: Message):

    qoida, viloyat, elon = get_links(
        message.from_user.id
    )

    if not qoida or not viloyat or not elon:
        await message.answer(
            "❌ Avval linklarni kiriting.\n\n"
            "/qoida https://...\n"
            "/viloyat https://...\n"
            "/elon https://..."
        )
        return

    photo = message.photo[-1].file_id

    caption = message.caption

    await message.answer_photo(
        photo=photo,
        caption=caption,
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


@router.channel_post()
async def channel_id(message: Message):
    print(
        f"CHANNEL: {message.chat.title} | "
        f"ID: {message.chat.id}"
    )
