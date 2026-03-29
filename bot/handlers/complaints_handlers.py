"""
Shikoyatlar tizimi handlerlari.

Foydalanuvchi oqimi:
  1. "Shikoyat qilish ⚠️" → matn kiritadi → skrinshot (ixtiyoriy) → DB ga saqlanadi.

Admin oqimi:
  1. "Shikoyatlar 📥" → o'qilmagan shikoyatlar bittadan ko'rsatiladi.
  2. Har birida: "Javob yozish" | "Ban" | "Yopish" tugmalari.
  3. Javob yozilsa → foydalanuvchiga Telegram xabar yetkaziladi.
"""
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import ComplaintSubmission, AdminComplaintReply
from bot.keyboards.admin_kb import admin_main_kb, complaint_action_kb
from bot.keyboards.user_kb import user_main_kb, cancel_kb, complaint_skip_kb
from bot.config import ADMIN_IDS
from bot.db.complaints import (
    add_complaint,
    get_unread_complaints,
    get_complaint,
    mark_complaint_read,
    reply_complaint,
    ban_complaint_user,
    ban_user,
    is_user_banned,
    get_unread_count,
)
from bot.db.participants import get_participant_by_user

logger = logging.getLogger(__name__)
router = Router()

MAX_COMPLAINT_LENGTH = 1000


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── Foydalanuvchi: shikoyat yuborish ─────────────────────────────────────

@router.message(F.text == "Shikoyat qilish ⚠️")
async def start_complaint(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # Ban tekshiruvi
    if await is_user_banned(user_id):
        await message.answer(
            "🚫 Siz ban ro'yxatidasiz. Shikoyat yuborishingiz mumkin emas.",
            reply_markup=user_main_kb(),
        )
        return

    await state.clear()
    await state.set_state(ComplaintSubmission.text)
    await message.answer(
        "⚠️ <b>Shikoyat yuborish</b>\n\n"
        "Shikoyatingizni batafsil yozing:\n"
        "<i>(Kim haqida, nima bo'ldi, qachon — batafsil yozing)</i>\n\n"
        f"Maksimal: {MAX_COMPLAINT_LENGTH} ta belgi",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(ComplaintSubmission.text, F.text == "❌ Bekor qilish")
@router.message(ComplaintSubmission.screenshot, F.text == "❌ Bekor qilish")
async def cancel_complaint(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    has_reg = await _check_registration(user_id)
    await message.answer(
        "❌ Shikoyat bekor qilindi.",
        reply_markup=user_main_kb(has_registration=has_reg),
    )


@router.message(ComplaintSubmission.text, F.text)
async def complaint_text_received(message: Message, state: FSMContext):
    text = message.text.strip()

    if len(text) < 10:
        await message.answer("⚠️ Shikoyat juda qisqa. Kamida 10 ta belgi kiriting.")
        return

    if len(text) > MAX_COMPLAINT_LENGTH:
        await message.answer(
            f"⚠️ Shikoyat juda uzun. Maksimal {MAX_COMPLAINT_LENGTH} ta belgi."
        )
        return

    await state.update_data(complaint_text=text)
    await state.set_state(ComplaintSubmission.screenshot)
    await message.answer(
        "📸 <b>Dalil (skrinshot)</b>\n\n"
        "Dalil sifatida skrinshot yuboring yoki o'tkazib yuboring:",
        parse_mode="HTML",
        reply_markup=complaint_skip_kb(),
    )


@router.message(ComplaintSubmission.screenshot, F.photo)
async def complaint_screenshot_received(message: Message, state: FSMContext):
    photo = message.photo[-1]
    screenshot_file_id = photo.file_id
    await _save_and_confirm_complaint(message, state, screenshot_file_id)


@router.message(ComplaintSubmission.screenshot, F.text == "⏭ Skrinshot o'tkazib yuborish")
async def complaint_skip_screenshot(message: Message, state: FSMContext):
    await _save_and_confirm_complaint(message, state, screenshot_file_id="")


async def _save_and_confirm_complaint(
    message: Message, state: FSMContext, screenshot_file_id: str
):
    data = await state.get_data()
    complaint_text = data.get("complaint_text", "")
    await state.clear()

    user = message.from_user
    username = user.username or ""
    full_name = user.full_name or ""

    complaint_id = await add_complaint(
        user_id=user.id,
        username=username,
        full_name=full_name,
        text=complaint_text,
        screenshot_file_id=screenshot_file_id,
    )

    has_reg = await _check_registration(user.id)
    await message.answer(
        f"✅ <b>Shikoyatingiz qabul qilindi!</b>\n\n"
        f"📋 Shikoyat raqami: <b>#{complaint_id}</b>\n\n"
        "Admin ko'rib chiqqach sizga javob beriladi.",
        parse_mode="HTML",
        reply_markup=user_main_kb(has_registration=has_reg),
    )
    logger.info(f"Yangi shikoyat #{complaint_id}: user_id={user.id}, username=@{username}")


# ─── Admin: shikoyatlarni ko'rish ──────────────────────────────────────────

@router.message(F.text == "Shikoyatlar 📥")
async def show_complaints(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    complaints = await get_unread_complaints()

    if not complaints:
        await message.answer(
            "📥 <b>O'qilmagan shikoyat yo'q</b>\n\nBarcha shikoyatlar ko'rib chiqilgan.",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
        return

    await message.answer(
        f"📥 <b>O'qilmagan shikoyatlar: {len(complaints)} ta</b>\n\n"
        "Har bir shikoyatni ko'rmoqdasiz 👇",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )

    for c in complaints:
        await _send_complaint_to_admin(message, c)


async def _send_complaint_to_admin(message: Message, complaint: dict):
    """Bitta shikoyatni admin uchun formatlaydi va yuboradi."""
    username_str = f"@{complaint['username']}" if complaint["username"] else "yo'q"
    has_screenshot = bool(complaint.get("screenshot_file_id"))
    status_map = {
        "unread": "🔴 O'qilmagan",
        "read": "🟡 O'qilgan",
        "replied": "🟢 Javob berilgan",
        "banned": "🚫 Ban qilingan",
    }
    status_str = status_map.get(complaint["status"], complaint["status"])

    caption = (
        f"📋 <b>Shikoyat #{complaint['id']}</b>\n"
        f"{'─' * 25}\n"
        f"👤 Foydalanuvchi: <b>{complaint['full_name']}</b>\n"
        f"🔗 Username: {username_str}\n"
        f"🆔 User ID: <code>{complaint['user_id']}</code>\n"
        f"📅 Sana: {complaint['created_at'][:16]}\n"
        f"📊 Holat: {status_str}\n"
        f"{'─' * 25}\n\n"
        f"💬 <b>Shikoyat matni:</b>\n{complaint['text']}"
    )

    kb = complaint_action_kb(complaint["id"], complaint["user_id"])

    try:
        if has_screenshot:
            await message.answer_photo(
                photo=complaint["screenshot_file_id"],
                caption=caption[:1024],
                parse_mode="HTML",
                reply_markup=kb,
            )
        else:
            await message.answer(caption, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"Shikoyat #{complaint['id']} ko'rsatishda xatolik: {e}")
        await message.answer(
            caption[:4000], parse_mode="HTML", reply_markup=kb
        )


# ─── Admin: shikoyat callback harakatlari ─────────────────────────────────

@router.callback_query(F.data.startswith("complaint_reply:"))
async def admin_start_reply(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    complaint_id = int(parts[1])
    user_id = int(parts[2])

    await state.set_state(AdminComplaintReply.reply_text)
    await state.update_data(complaint_id=complaint_id, target_user_id=user_id)

    await callback.message.answer(
        f"💬 <b>Shikoyat #{complaint_id} ga javob</b>\n\n"
        "Javob matnini yozing (foydalanuvchiga yuboriladi):",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(AdminComplaintReply.reply_text, F.text == "❌ Bekor qilish")
async def cancel_admin_reply(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ Javob bekor qilindi.", reply_markup=admin_main_kb())


@router.message(AdminComplaintReply.reply_text, F.text)
async def admin_send_reply(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    reply_text = message.text.strip()
    data = await state.get_data()
    complaint_id = data.get("complaint_id")
    target_user_id = data.get("target_user_id")
    await state.clear()

    # DB ga yozish
    try:
        await reply_complaint(complaint_id, reply_text)
    except Exception as e:
        logger.error(f"Javob saqlashda xatolik: {e}")

    # Foydalanuvchiga yuborish
    try:
        await bot.send_message(
            target_user_id,
            f"📩 <b>Shikoyatingizga admin javobi</b>\n\n"
            f"📋 Shikoyat #{complaint_id}\n"
            f"{'─' * 25}\n\n"
            f"{reply_text}",
            parse_mode="HTML",
        )
        sent_ok = True
    except Exception as e:
        logger.warning(f"Foydalanuvchi {target_user_id} ga javob yuborilmadi: {e}")
        sent_ok = False

    status_text = "✅ Foydalanuvchiga javob yuborildi!" if sent_ok else "⚠️ Foydalanuvchi botni bloklagan, javob yuborilmadi."
    await message.answer(
        f"{status_text}\n\n"
        f"📋 Shikoyat #{complaint_id} javob berilgan deb belgilandi.",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.callback_query(F.data.startswith("complaint_ban:"))
async def admin_ban_user(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return

    parts = callback.data.split(":")
    complaint_id = int(parts[1])
    user_id = int(parts[2])

    try:
        await ban_user(user_id, reason=f"Shikoyat #{complaint_id} asosida chetlatildi")
        await ban_complaint_user(complaint_id)
    except Exception as e:
        logger.error(f"Ban qilishda xatolik: {e}")
        await callback.answer("❌ Xatolik yuz berdi!", show_alert=True)
        return

    # Foydalanuvchiga xabar
    try:
        await bot.send_message(
            user_id,
            "🚫 <b>Siz turnirdan chetlatildingiz!</b>\n\n"
            "Qoidabuzarlik sababli akkauntingiz bloklanган.\n"
            "Murojaat uchun admin bilan bog'laning.",
            parse_mode="HTML",
        )
    except Exception:
        pass

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"🚫 <b>Foydalanuvchi ban qilindi!</b>\n"
            f"👤 User ID: <code>{user_id}</code>\n"
            f"📋 Shikoyat #{complaint_id} yopildi.",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
    except Exception as e:
        logger.warning(f"Edit reply markup xatosi: {e}")

    await callback.answer("🚫 Foydalanuvchi ban qilindi!")


@router.callback_query(F.data.startswith("complaint_close:"))
async def admin_close_complaint(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    complaint_id = int(callback.data.split(":")[1])

    try:
        await mark_complaint_read(complaint_id)
    except Exception as e:
        logger.error(f"Shikoyat yopishda xatolik: {e}")
        await callback.answer("❌ Xatolik!", show_alert=True)
        return

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer(f"✅ Shikoyat #{complaint_id} yopildi!")
    except Exception as e:
        logger.warning(f"Edit xatosi: {e}")
        await callback.answer("✅ Yopildi!")

    # Qolgan shikoyatlar sonini ko'rsatish
    remaining = await get_unread_count()
    if remaining > 0:
        await callback.message.answer(
            f"📥 Yana <b>{remaining}</b> ta o'qilmagan shikoyat bor.\n"
            "Ko'rish uchun \"Shikoyatlar 📥\" tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )


# ─── Yordamchi funksiya ────────────────────────────────────────────────────

async def _check_registration(user_id: int) -> bool:
    """Foydalanuvchi faol turnirga ro'yxatdan o'tganini tekshiradi."""
    try:
        from bot.db.tournaments import get_active_tournament
        tournament = await get_active_tournament()
        if not tournament:
            return False
        participant = await get_participant_by_user(tournament["id"], user_id)
        return participant is not None
    except Exception:
        return False
