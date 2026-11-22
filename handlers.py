from __future__ import annotations

from datetime import datetime, timedelta
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import database
from keyboards import channels_keyboard, main_menu, make_buttons, regions_keyboard
from scheduler import TASHKENT, cancel_job, publish_post, schedule_post, sync_published_post

router = Router()
ADMIN_IDS = {1255705034, 6201110478, 6960879913, 6683769327, 1697916196}
router.message.filter(F.from_user.id.in_(ADMIN_IDS))
router.callback_query.filter(F.from_user.id.in_(ADMIN_IDS))


class Wizard(StatesGroup):
    channel = State()
    region = State()
    post_content = State()
    once_time = State()
    recurring_time = State()
    channel_add = State()
    confirm = State()
    duration = State()
    interval = State()
    edit_text = State()
    edit_photo = State()
    edit_time = State()
    edit_channels = State()
    link_value = State()


@router.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✅ TugmaBot boshqaruv paneli.", reply_markup=main_menu())


@router.message(F.text.in_({"⚙️ Sozlamalar"}))
async def settings_menu(message: Message):
    await message.answer(
        "Havolalarni boshqarish komandalari:\n"
        "/qoida <URL>, /viloyat <URL>, /elon <URL>, /matnlink <URL>\n"
        "/show — ko‘rish; /qoida_off, /viloyat_off, /elon_off, /matnlink_off — o‘chirish"
    )


async def _set_link(message: Message, field: str, example: str):
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer(f"Foydalanish: /{example} https://t.me/kanal")
        return
    database.set_link(message.from_user.id, field, parts[1].strip())
    await message.answer("✅ Havola saqlandi.")


@router.message(Command("qoida"))
async def set_qoida(message: Message):
    await _set_link(message, "qoida", "qoida")


@router.message(Command("viloyat"))
async def set_viloyat(message: Message):
    await _set_link(message, "viloyat", "viloyat")


@router.message(Command("elon"))
async def set_elon(message: Message):
    await _set_link(message, "elon", "elon")


@router.message(Command("matnlink"))
async def set_matnlink(message: Message):
    await _set_link(message, "matnlink", "matnlink")


@router.message(Command("qoida_off"))
async def delete_qoida(message: Message):
    database.set_link(message.from_user.id, "qoida", None)
    await message.answer("✅ Qoida havolasi o‘chirildi.")


@router.message(Command("viloyat_off"))
async def delete_viloyat(message: Message):
    database.set_link(message.from_user.id, "viloyat", None)
    await message.answer("✅ Viloyat havolasi o‘chirildi.")


@router.message(Command("elon_off"))
async def delete_elon(message: Message):
    database.set_link(message.from_user.id, "elon", None)
    await message.answer("✅ E’lon havolasi o‘chirildi.")


@router.message(Command("matnlink_off"))
async def delete_matnlink(message: Message):
    database.set_link(message.from_user.id, "matnlink", None)
    await message.answer("✅ Ishtopchi havolasi o‘chirildi.")


@router.message(Command("show"))
async def show(message: Message):
    qoida, viloyat, elon, matnlink = database.get_links(message.from_user.id)
    await message.answer(
        f"❗️ Qoida: {qoida or 'Kiritilmagan'}\n🌍 Viloyat: {viloyat or 'Kiritilmagan'}\n"
        f"📩 E’lon: {elon or 'Kiritilmagan'}\n🔗 Ishtopchi: {matnlink or 'Kiritilmagan'}"
    )


@router.message(F.text == "📍 Hududlar va kanallar")
async def show_channels(message: Message):
    channels = database.all_channels()
    rows = [[InlineKeyboardButton(
        text=f"{'🟢' if row['active'] and row['can_post'] else '⚪'} {row['region_name']} — {row['name']}",
        callback_data=f"channel:view:{row['id']}",
    )] for row in channels]
    rows.append([InlineKeyboardButton(text="➕ Kanal qo‘shish", callback_data="channel:add")])
    await message.answer("Kanallarni boshqarish:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data == "channel:add")
async def begin_channel_add(call: CallbackQuery, state: FSMContext):
    await state.set_state(Wizard.channel_add)
    await call.message.answer("Hudud | kanal nomi | Telegram ID yuboring. Masalan:\nQo‘qon | Kanal 1 | -1001234567890")
    await call.answer()


@router.message(Wizard.channel_add)
async def save_channel(message: Message, state: FSMContext):
    parts = [x.strip() for x in (message.text or "").split("|", 2)]
    if len(parts) != 3:
        await message.answer("Uch qismni `Hudud | nom | -100...` shaklida yuboring.")
        return
    region, name, chat_id = parts
    try:
        chat = await message.bot.get_chat(chat_id)
        me = await message.bot.get_me()
        member = await message.bot.get_chat_member(chat.id, me.id)
        can_post = member.status == "creator" or (member.status == "administrator" and getattr(member, "can_post_messages", False))
        data = await state.get_data()
        if data.get("channel_id"):
            database.update_channel(data["channel_id"], region, name, str(chat.id), can_post)
            result = "✅ Kanal yangilandi."
        else:
            database.add_channel(region, name, str(chat.id))
            with database.connect() as db:
                db.execute("UPDATE channels SET can_post=? WHERE telegram_id=?", (int(can_post), str(chat.id)))
            result = "✅ Kanal saqlandi."
        await message.answer(result + (" Bot post joylay oladi." if can_post else " ⚠️ Bot kanal administratori emas yoki post huquqi yo‘q."))
    except Exception:
        await message.answer("Kanal topilmadi, botda kanalni ko‘rish huquqi yo‘q yoki ID band. Botni kanalga admin qilib, qayta urinib ko‘ring.")
    await state.clear()


def channel_detail_keyboard(channel_id: int, active: bool):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{'Faolsizlantirish' if active else 'Faollashtirish'}", callback_data=f"channel:toggle:{channel_id}")],
        [InlineKeyboardButton(text="✏️ Tahrirlash", callback_data=f"channel:edit:{channel_id}")],
        [InlineKeyboardButton(text="🗑 O‘chirish", callback_data=f"channel:delete:{channel_id}")],
    ])


@router.callback_query(F.data.startswith("channel:view:"))
async def view_channel(call: CallbackQuery):
    channel_id = int(call.data.rsplit(":", 1)[1])
    channel = next((c for c in database.all_channels() if c["id"] == channel_id), None)
    if not channel:
        await call.answer("Kanal topilmadi", show_alert=True)
        return
    await call.message.edit_text(
        f"{channel['region_name']} — {channel['name']}\nID: {channel['telegram_id']}\n"
        f"Holati: {'faol' if channel['active'] else 'nofaol'}\nPost huquqi: {'bor' if channel['can_post'] else 'yo‘q'}",
        reply_markup=channel_detail_keyboard(channel_id, bool(channel["active"])),
    )
    await call.answer()


@router.callback_query(F.data.startswith("channel:toggle:"))
async def channel_action(call: CallbackQuery):
    try:
        channel_id = int(call.data.rsplit(":", 1)[1])
        channel = next((c for c in database.all_channels() if c["id"] == channel_id), None)
        if not channel:
            await call.answer("Kanal topilmadi", show_alert=True)
            return
        active = not bool(channel["active"])
        database.set_channel_status(channel_id, active)
        if call.message:
            await call.message.edit_text(f"{channel['region_name']} — {channel['name']}\nHolati: {'faol' if active else 'nofaol'}",
                reply_markup=channel_detail_keyboard(channel_id, active))
        await call.answer("Holat o‘zgartirildi")
    except (ValueError, IndexError):
        await call.answer()


@router.callback_query(F.data.startswith("channel:edit:"))
async def edit_channel(call: CallbackQuery, state: FSMContext):
    channel_id = int(call.data.rsplit(":", 1)[1])
    channel = next((c for c in database.all_channels() if c["id"] == channel_id), None)
    if not channel:
        await call.answer("Kanal topilmadi", show_alert=True)
        return
    await state.set_state(Wizard.channel_add)
    await state.update_data(channel_id=channel_id)
    await call.message.answer("Hudud | kanal nomi | Telegram ID yuboring. Masalan:\nQo‘qon | Kanal 1 | -1001234567890")
    await call.answer()


@router.callback_query(F.data.startswith("channel:delete:"))
async def remove_channel(call: CallbackQuery):
    channel_id = int(call.data.rsplit(":", 1)[1])
    database.delete_channel(channel_id)
    if call.message:
        await call.message.edit_text("✅ Kanal o‘chirildi.")
    await call.answer()


@router.message(F.text == "➕ Yangi e'lon")
async def new_post(message: Message, state: FSMContext):
    regions = database.list_regions()
    if not regions:
        await message.answer("Avval ‘Hududlar va kanallar’ bo‘limidan kanal qo‘shing.")
        return
    await state.clear()
    await state.set_state(Wizard.region)
    await message.answer("Hududni tanlang:", reply_markup=regions_keyboard(regions))


@router.callback_query(Wizard.region, F.data.startswith("region:"))
async def select_region(call: CallbackQuery, state: FSMContext):
    region_id = int(call.data.split(":")[1])
    channels = database.channels_for_region(region_id)
    if not channels:
        await call.answer("Bu hududda faol va botga ruxsat berilgan kanal yo‘q", show_alert=True)
        return
    await state.update_data(region_id=region_id, channels=[c["id"] for c in channels], selected=[])
    await state.set_state(Wizard.channel)
    await call.message.edit_text("Kerakli kanallarni tanlang:", reply_markup=channels_keyboard(channels, set()))
    await call.answer()


@router.callback_query(StateFilter(Wizard.channel, Wizard.edit_channels), F.data.startswith("selectch:"))
async def toggle_channel(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    channel_id = int(call.data.split(":")[1])
    selected = set(data.get("selected", []))
    selected.symmetric_difference_update({channel_id})
    await state.update_data(selected=list(selected))
    channels = [c for c in database.all_channels() if c["active"] and c["can_post"]] if await state.get_state() == Wizard.edit_channels.state else database.channels_for_region(data["region_id"])
    await call.message.edit_reply_markup(reply_markup=channels_keyboard(channels, selected))
    await call.answer()


@router.callback_query(Wizard.channel, F.data == "channels:done")
async def selected_channels(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected"):
        await call.answer("Kamida bitta kanal tanlang", show_alert=True)
        return
    await state.set_state(Wizard.post_content)
    await call.message.answer("E’lon matnini yoki rasm bilan captionni yuboring:")
    await call.answer()


@router.callback_query(Wizard.edit_channels, F.data == "channels:done")
async def save_edited_channels(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected"):
        await call.answer("Kamida bitta kanal tanlang", show_alert=True)
        return
    database.replace_post_channels(data["post_id"], call.from_user.id, data["selected"])
    await state.clear()
    await call.message.edit_text("✅ E’lon kanallari yangilandi.")
    await call.answer()


@router.message(Wizard.post_content)
async def receive_post(message: Message, state: FSMContext):
    content = message.caption if message.photo else message.text
    if not content:
        await message.answer("Matn yoki rasm va caption yuboring.")
        return
    _, _, _, textlink = database.get_links(message.from_user.id)
    visible_link = "\n\n🔗 𝗜𝘀𝗵𝘁𝗼𝗽𝗰𝗵𝗶" if textlink else ""
    limit = 1024 if message.photo else 4096
    if len(content) + len(visible_link) > limit:
        await message.answer(f"Telegram bu post turi uchun {limit} belgigacha qabul qiladi. Matnni qisqartiring.")
        return
    await state.update_data(text=content, photo_file_id=message.photo[-1].file_id if message.photo else None)
    durations = [1, 2, 3, 5, 7, 10, 15, 30]
    rows = [
        [InlineKeyboardButton(text=f"{days} kun", callback_data=f"duration:{days}")
         for days in durations[index:index + 2]]
        for index in range(0, len(durations), 2)
    ]
    await state.set_state(Wizard.duration)
    await message.answer("E’lon necha kun davom etsin? Muddatni tanlang:",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(Wizard.duration, F.data.startswith("duration:"))
async def choose_duration(call: CallbackQuery, state: FSMContext):
    duration = int(call.data.split(":")[1])
    if duration not in {1, 2, 3, 5, 7, 10, 15, 30}:
        await call.answer("Muddat noto‘g‘ri", show_alert=True)
        return
    await state.update_data(occurrences_total=duration)
    await state.set_state(Wizard.interval)
    await call.message.edit_text(
        f"{duration} kunlik muddat tanlandi. Qanday joylansin?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Har kuni", callback_data="interval:1")],
            [InlineKeyboardButton(text="Kun ora", callback_data="interval:2")],
        ]),
    )
    await call.answer()


@router.callback_query(Wizard.interval, F.data.startswith("interval:"))
async def choose_interval(call: CallbackQuery, state: FSMContext):
    interval_days = int(call.data.split(":")[1])
    if interval_days not in {1, 2}:
        await call.answer("Takrorlanish turi noto‘g‘ri", show_alert=True)
        return
    await state.update_data(interval_days=interval_days, schedule_type="daily")
    await state.set_state(Wizard.recurring_time)
    await call.message.answer("Joylash vaqtini Toshkent vaqti bilan bir marta kiriting: HH:MM")
    await call.answer()


@router.callback_query(F.data == "schedule:once")
async def once_prompt(call: CallbackQuery, state: FSMContext):
    await state.set_state(Wizard.once_time)
    await call.message.answer("Toshkent vaqti bilan sana va vaqtni yuboring: YYYY-MM-DD HH:MM")
    await call.answer()


@router.callback_query(F.data.in_({"schedule:daily", "schedule:weekly"}))
async def repeat_prompt(call: CallbackQuery, state: FSMContext):
    kind = call.data.split(":")[1]
    await state.update_data(schedule_type=kind)
    await state.set_state(Wizard.recurring_time)
    text = "Har bir kun va vaqtni alohida yozing: Du=09:30,Pa=18:00" if kind == "weekly" else "Har kuni uchun vaqtni yuboring: HH:MM"
    await call.message.answer(text)
    await call.answer()


async def _confirm_post(message: Message, state: FSMContext, schedule_type: str, run_at=None,
                        weekdays=None, run_time=None, duration=None, interval_days=1,
                        next_run_at=None):
    data = await state.get_data()
    if duration is not None:
        if interval_days == 1:
            when = f"{duration} kun, har kuni soat {run_time}"
        else:
            when = f"{duration} marta, kun ora (taxminan {duration * 2} kun), soat {run_time}"
    elif run_at:
        when = run_at
    elif schedule_type == "daily":
        when = f"Har kuni {run_time}"
    else:
        names = {0: "Du", 1: "Se", 2: "Ch", 3: "Pa", 4: "Ju", 5: "Sh", 6: "Ya"}
        times = __import__("json").loads(run_time)
        when = ", ".join(f"{names[int(day)]} {value}" for day, value in times.items())
    await state.update_data(schedule_type=schedule_type, run_at=run_at, weekdays=weekdays or [],
                            run_time=run_time, occurrences_total=duration,
                            interval_days=interval_days, next_run_at=next_run_at)
    await state.set_state(Wizard.confirm)
    preview = escape(data["text"])
    _, _, _, textlink = database.get_links(message.from_user.id)
    if textlink:
        preview += f'\n\n<a href="{escape(textlink, quote=True)}">🔗 𝗜𝘀𝗵𝘁𝗼𝗽𝗰𝗵𝗶</a>'
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash va rejalashtirish", callback_data="post:confirm")],
        [InlineKeyboardButton(text="Bekor qilish", callback_data="post:cancel")],
    ])
    heading = f"📝 E’lon ko‘rib chiqish\nJadval: {when}\nTanlangan kanal: {len(data['selected'])}"
    if data["photo_file_id"]:
        await message.answer(heading)
        await message.answer_photo(data["photo_file_id"], caption=preview or None,
                                   parse_mode="HTML", reply_markup=keyboard)
    else:
        await message.answer(f"{heading}\n\n{preview}\n\nTasdiqlaysizmi?",
                             parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(Wizard.confirm, F.data == "post:confirm")
async def confirm_post(call: CallbackQuery, state: FSMContext):
    await call.answer("E’lon rejalashtirilmoqda")
    data = await state.get_data()
    post_id = database.create_post(
        call.from_user.id, data["text"], data["photo_file_id"], data["schedule_type"],
        data["selected"], data["run_at"], data["weekdays"], data["run_time"],
        occurrences_total=data.get("occurrences_total"),
        interval_days=data.get("interval_days", 1),
        next_run_at=data.get("next_run_at"),
    )
    post, _ = database.get_post(post_id, call.from_user.id)
    schedule_post(call.bot, post)
    await state.clear()
    success = f"✅ Tasdiqlandi. E’lon #{post_id} rejaga qo‘shildi."
    if call.message.photo:
        await call.message.edit_caption(caption=success, reply_markup=None)
    else:
        await call.message.edit_text(success, reply_markup=None)
    await call.message.answer(
        "📅 Rejadagi e’lonlar bo‘limidan holatini ko‘rishingiz mumkin.",
        reply_markup=main_menu(),
    )


@router.callback_query(Wizard.confirm, F.data == "post:cancel")
async def cancel_post(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("E’lon bekor qilindi.")
    await call.answer()


@router.message(Wizard.once_time)
async def save_once(message: Message, state: FSMContext):
    try:
        run_at = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=TASHKENT)
        if run_at <= datetime.now(TASHKENT):
            raise ValueError
    except (ValueError, AttributeError):
        await message.answer("Sana kelajakda bo‘lsin. Format: YYYY-MM-DD HH:MM")
        return
    await _confirm_post(message, state, "once", run_at.isoformat())


@router.message(Wizard.recurring_time)
async def save_repeat(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        run_time = datetime.strptime(message.text.strip(), "%H:%M").strftime("%H:%M")
    except (ValueError, KeyError, AttributeError):
        await message.answer("Vaqt noto‘g‘ri. HH:MM ko‘rinishida yuboring, masalan 09:30.")
        return
    now = datetime.now(TASHKENT)
    first_run = datetime.combine(now.date(), datetime.strptime(run_time, "%H:%M").time()).replace(tzinfo=TASHKENT)
    if first_run <= now:
        first_run += timedelta(days=1)
    await _confirm_post(message, state, data["schedule_type"], run_time=run_time,
                        duration=data["occurrences_total"], interval_days=data["interval_days"],
                        next_run_at=first_run.isoformat())


@router.message(F.text == "📅 Rejadagi e'lonlar")
async def list_posts(message: Message):
    regions = database.list_regions()
    if not regions:
        await message.answer("Hududlar hali qo‘shilmagan. Avval 📍 Hududlar va kanallar bo‘limidan hudud qo‘shing.")
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=region["name"], callback_data=f"posts:region:{region['id']}")]
        for region in regions
    ])
    await message.answer("Rejadagi e’lonlarni ko‘rish uchun hududni tanlang:", reply_markup=keyboard)


@router.callback_query(F.data == "posts:regions")
async def show_post_regions(call: CallbackQuery):
    regions = database.list_regions()
    if not regions:
        await call.message.edit_text("Hududlar hali qo‘shilmagan.")
        await call.answer()
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=region["name"], callback_data=f"posts:region:{region['id']}")]
        for region in regions
    ])
    await call.message.edit_text("Rejadagi e’lonlarni ko‘rish uchun hududni tanlang:", reply_markup=keyboard)
    await call.answer()


@router.callback_query(F.data.startswith("posts:region:"))
async def list_region_posts(call: CallbackQuery):
    region_id = int(call.data.rsplit(":", 1)[1])
    region = next((row for row in database.list_regions() if row["id"] == region_id), None)
    if not region:
        await call.answer("Hudud topilmadi", show_alert=True)
        return
    posts = database.list_posts_for_region(call.from_user.id, region_id)
    back = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Hududlarga qaytish", callback_data="posts:regions")
    ]])
    if not posts:
        await call.message.edit_text(f"📅 {region['name']} hududida rejadagi e’lon yo‘q.", reply_markup=back)
        await call.answer()
        return
    await call.message.edit_text(f"📅 {region['name']} hududidagi rejadagi e’lonlar:", reply_markup=back)
    await _send_post_cards(call.message, posts)
    await call.answer()


async def _send_post_cards(message: Message, posts):
    for post in posts:
        status_labels = {
            "pending": "Kutilmoqda", "active": "Faol", "paused": "To‘xtatilgan",
            "published": "Joylandi", "error": "Xatolik",
        }
        if post["occurrences_total"] is not None:
            interval_text = "har kuni" if post["interval_days"] == 1 else "kun ora"
            approx_days = post["occurrences_total"] * post["interval_days"]
            schedule_text = (
                f"{post['occurrences_sent']}/{post['occurrences_total']} marta · {interval_text} · "
                f"taxminan {approx_days} kun · soat {post['run_time']}"
            )
            if post["next_run_at"]:
                schedule_text += f"\nKeyingi: {post['next_run_at']}"
        elif post["schedule_type"] == "once":
            schedule_text = f"Bir marta · {post['run_at']}"
        elif post["schedule_type"] == "weekly":
            schedule_text = f"Hafta jadvali · {post['run_time']}"
        else:
            schedule_text = f"Har kuni · {post['run_time']}"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⏸/▶️", callback_data=f"post:toggle:{post['id']}"),
            InlineKeyboardButton(text="📤 Hozir", callback_data=f"post:now:{post['id']}"),
            InlineKeyboardButton(text="🗑", callback_data=f"post:delete:{post['id']}"),
        ], [
            InlineKeyboardButton(text="✏️ Matn", callback_data=f"post:edit_text:{post['id']}"),
            InlineKeyboardButton(text="🖼 Rasm", callback_data=f"post:edit_photo:{post['id']}"),
            InlineKeyboardButton(text="📅 Vaqt", callback_data=f"post:edit_time:{post['id']}"),
            InlineKeyboardButton(text="📍 Kanallar", callback_data=f"post:channels:{post['id']}"),
        ]])
        await message.answer(
            f"E’lon #{post['id']} · {status_labels.get(post['status'], post['status'])}\n"
            f"{schedule_text}\n{post['text'][:300]}", reply_markup=keyboard,
        )


@router.callback_query(F.data.startswith("post:"))
async def manage_post(call: CallbackQuery, state: FSMContext):
    _, action, raw_id = call.data.split(":", 2)
    post_id = int(raw_id)
    post, _ = database.get_post(post_id, call.from_user.id)
    if not post:
        await call.answer("E’lon topilmadi", show_alert=True)
        return
    if action == "delete":
        cancel_job(post_id)
        removed = 0
        for published in database.published_messages(post_id):
            try:
                await call.bot.delete_message(published["telegram_id"], published["telegram_message_id"])
                removed += 1
            except Exception:
                pass
        database.delete_post(post_id, call.from_user.id)
        await call.message.edit_text(f"E’lon #{post_id} o‘chirildi. Kanal xabarlaridan {removed} tasi ham o‘chirildi.")
    elif action == "toggle":
        if post["status"] == "paused":
            database.update_post_status(post_id, call.from_user.id, "active" if post["schedule_type"] != "once" else "pending")
            refreshed, _ = database.get_post(post_id, call.from_user.id)
            schedule_post(call.bot, refreshed)
            await call.answer("E’lon davom ettirildi")
        else:
            cancel_job(post_id)
            database.update_post_status(post_id, call.from_user.id, "paused")
            await call.answer("E’lon to‘xtatildi")
    elif action == "now":
        await publish_post(call.bot, post_id, f"manual-{datetime.now(TASHKENT).isoformat(timespec='seconds')}", once=False)
        await call.answer("Jo‘natish topshirildi")
    elif action == "edit_text":
        await call.message.answer(f"E’lon #{post_id} uchun yangi matnni yuboring:")
        await state.set_state(Wizard.edit_text)
        await state.update_data(post_id=post_id)
    elif action == "edit_photo":
        await call.message.answer("Yangi rasmni yuboring. Rasmsiz post qilish uchun /skip yuboring.")
        await state.set_state(Wizard.edit_photo)
        await state.update_data(post_id=post_id)
    elif action == "edit_time":
        if post["status"] == "published" and post["schedule_type"] == "once":
            await call.answer("Bu e’lon allaqachon joylangan.", show_alert=True)
            return
        prompt = ("Yangi sana-vaqtni yuboring: YYYY-MM-DD HH:MM" if post["schedule_type"] == "once"
                  else "Hafta kunlari uchun alohida vaqt yozing: Du=09:30,Pa=18:00" if post["schedule_type"] == "weekly"
                  else "Yangi takroriy vaqtni yuboring: HH:MM")
        await call.message.answer(prompt)
        await state.set_state(Wizard.edit_time)
        await state.update_data(post_id=post_id)
    elif action == "channels":
        channels = [c for c in database.all_channels() if c["active"] and c["can_post"]]
        selected = [c["id"] for c in database.get_post(post_id, call.from_user.id)[1]]
        await state.set_state(Wizard.edit_channels)
        await state.update_data(post_id=post_id, selected=selected)
        await call.message.answer("E’lon uchun kanallarni belgilang:", reply_markup=channels_keyboard(channels, set(selected)))
    if action not in {"toggle", "now"}:
        await call.answer()


@router.message(Wizard.edit_text)
async def save_edited_text(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Yangi matnni yozma xabar qilib yuboring.")
        return
    data = await state.get_data()
    post, _ = database.get_post(data["post_id"], message.from_user.id)
    if len(message.text) > (1024 if post["photo_file_id"] else 4096):
        await message.answer("Matn Telegram limitidan uzun.")
        return
    database.update_post_content(data["post_id"], message.from_user.id, text=message.text)
    changed, failed = await sync_published_post(message.bot, data["post_id"])
    await state.clear()
    await message.answer(f"✅ Matn yangilandi. Avvalgi postlardan {changed} tasi tahrirlandi; xato: {failed}.")


@router.message(Wizard.edit_photo, F.photo)
async def save_edited_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    post, _ = database.get_post(data["post_id"], message.from_user.id)
    database.update_post_content(data["post_id"], message.from_user.id,
                                 text=message.caption if message.caption is not None else post["text"],
                                 photo_file_id=message.photo[-1].file_id, update_photo=True)
    changed, failed = await sync_published_post(message.bot, data["post_id"])
    await state.clear()
    await message.answer(f"✅ Rasm yangilandi. Avvalgi postlardan {changed} tasi yangilandi; xato: {failed}.")


@router.message(Wizard.edit_photo, Command("skip"))
async def remove_edited_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    post, _ = database.get_post(data["post_id"], message.from_user.id)
    database.update_post_content(data["post_id"], message.from_user.id,
                                 text=post["text"], photo_file_id=None, update_photo=True)
    changed, failed = await sync_published_post(message.bot, data["post_id"])
    await state.clear()
    await message.answer(f"✅ Rasm olib tashlandi. Avvalgi postlardan {changed} tasi yangilandi; xato: {failed}.")


@router.message(Wizard.edit_time)
async def save_edited_time(message: Message, state: FSMContext):
    data = await state.get_data()
    post, _ = database.get_post(data["post_id"], message.from_user.id)
    try:
        if post["schedule_type"] == "once":
            run_at = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=TASHKENT)
            if run_at <= datetime.now(TASHKENT):
                raise ValueError
            database.update_post_time(post["id"], message.from_user.id, run_at=run_at.isoformat())
        elif post["schedule_type"] == "weekly":
            labels = {"du": 0, "se": 1, "ch": 2, "pa": 3, "ju": 4, "sh": 5, "ya": 6}
            schedule = {}
            for item in message.text.split(","):
                day, time_value = item.split("=", maxsplit=1)
                weekday = labels[day.strip().lower()]
                schedule[str(weekday)] = datetime.strptime(time_value.strip(), "%H:%M").strftime("%H:%M")
            database.update_post_time(post["id"], message.from_user.id,
                                      weekdays=sorted(int(day) for day in schedule),
                                      run_time=__import__("json").dumps(schedule))
        else:
            run_time = datetime.strptime(message.text.strip(), "%H:%M").strftime("%H:%M")
            if post["occurrences_total"] is not None:
                start_date = datetime.fromisoformat(post["next_run_at"]).astimezone(TASHKENT).date() if post["next_run_at"] else datetime.now(TASHKENT).date()
                new_run_at = datetime.combine(start_date, datetime.strptime(run_time, "%H:%M").time()).replace(tzinfo=TASHKENT)
                while new_run_at <= datetime.now(TASHKENT):
                    new_run_at += timedelta(days=post["interval_days"])
                database.update_post_time(post["id"], message.from_user.id,
                                          run_time=run_time, next_run_at=new_run_at.isoformat())
            else:
                database.update_post_time(post["id"], message.from_user.id, run_time=run_time)
        cancel_job(post["id"])
        refreshed, _ = database.get_post(post["id"], message.from_user.id)
        schedule_post(message.bot, refreshed)
    except (ValueError, AttributeError):
        await message.answer("Sana yoki vaqt noto‘g‘ri.")
        return
    await state.clear()
    await message.answer("✅ E’lon vaqti yangilandi.")


@router.message(F.photo)
async def photo_preview(message: Message):
    qoida, viloyat, elon, matnlink = database.get_links(message.from_user.id)
    caption = escape(message.caption or "")
    if matnlink:
        caption += f'\n\n<a href="{escape(matnlink, quote=True)}">🔗 𝗜𝘀𝗵𝘁𝗼𝗽𝗰𝗵𝗶</a>'
    await message.answer_photo(message.photo[-1].file_id, caption=caption or None, parse_mode="HTML",
                               reply_markup=make_buttons(qoida, viloyat, elon))


@router.message()
async def help_message(message: Message):
    await message.answer("Menyudan foydalaning yoki sozlamalar uchun /show buyrug‘ini yuboring.", reply_markup=main_menu())
