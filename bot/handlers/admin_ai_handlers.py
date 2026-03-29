"""
AI yordamida turnir e'lonlari va qoidalar yaratish uchun handler.

Oqim:
  1. Admin "🤖 AI E'lon yaratish" tugmasini bosadi.
  2. Bot ovozli xabar yoki matn yuborishni so'raydi.
  3. Ovozli xabar → Whisper API → matn; oddiy matn → to'g'ridan.
  4. Matn → GPT-4 → chiroyli, emoji-li e'lon.
  5. Admin "✅ Tasdiqlash" yoki "🔄 Qaytadan kiritish" ni bosadi.
  6. Tasdiqlangach DB ga saqlanadi, ixtiyoriy ravishda broadcast qilinadi.
"""
import io
import logging
import tempfile
import os

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import AIAnnouncementCreation
from bot.keyboards.admin_kb import admin_main_kb, cancel_kb, ai_confirm_kb
from bot.config import ADMIN_IDS, OPENAI_API_KEY, ANTHROPIC_API_KEY
from bot.db.tournaments import get_active_tournament, get_all_tournaments
from bot.db.complaints import update_tournament_rules
from bot.db.participants import get_tournament_participants

logger = logging.getLogger(__name__)
router = Router()

AI_SYSTEM_PROMPT = (
    "Sen eFootball turnirlarini boshqaruvchi professional adminsan. "
    "Berilgan xom ma'lumotdan foydalanib, quyidagi formatda chiroyli turnir e'loni va "
    "rasmiy qoidalar matni yozib ber:\n\n"
    "1. E'lon boshida katta sarlavha (emoji bilan)\n"
    "2. Turnir tafsilotlari (sana, narx, sovg'alar, ro'yxatdan o'tish)\n"
    "3. Asosiy qoidalar ro'yxati (raqamlangan, har biri yangi qatorda)\n"
    "4. Muhim eslatmalar\n"
    "5. Oxirida motivatsion chaqiriq\n\n"
    "Faqat o'zbek tilida yoz. Telegram HTML formatlashdan foydalanma, "
    "faqat emoji va oddiy matndan foydalan."
)


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def transcribe_voice_openai(file_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Ovozli xabarni OpenAI Whisper orqali matnga o'giradi."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        audio_file = io.BytesIO(file_bytes)
        audio_file.name = filename
        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="uz",
        )
        return transcript.text.strip()
    except Exception as e:
        logger.error(f"Whisper transcription xatosi: {e}")
        raise RuntimeError(f"Ovozni matnga o'girishda xatolik: {e}")


async def generate_announcement_openai(raw_text: str) -> str:
    """OpenAI GPT-4 orqali chiroyli e'lon yaratadi."""
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            max_tokens=1500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"OpenAI GPT-4 xatosi: {e}")
        raise RuntimeError(f"AI e'lon yaratishda xatolik: {e}")


async def generate_announcement_anthropic(raw_text: str) -> str:
    """Anthropic Claude orqali chiroyli e'lon yaratadi (zaxira)."""
    try:
        import httpx
        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1500,
            "system": AI_SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": raw_text}],
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"].strip()
    except Exception as e:
        logger.error(f"Anthropic Claude xatosi: {e}")
        raise RuntimeError(f"Claude e'lon yaratishda xatolik: {e}")


async def generate_announcement(raw_text: str) -> str:
    """OpenAI ni sinab ko'radi, agar ishlamasa Anthropic ga o'tadi."""
    if OPENAI_API_KEY:
        try:
            return await generate_announcement_openai(raw_text)
        except Exception as e:
            logger.warning(f"OpenAI ishlamadi, Anthropic ga o'tilmoqda: {e}")
    if ANTHROPIC_API_KEY:
        try:
            return await generate_announcement_anthropic(raw_text)
        except Exception as e:
            logger.error(f"Anthropic ham ishlamadi: {e}")
            raise
    raise RuntimeError(
        "AI API kalitlari topilmadi. OPENAI_API_KEY yoki ANTHROPIC_API_KEY ni .env ga kiriting."
    )


# ─── Handlerlar ─────────────────────────────────────────────────────────────

@router.message(F.text == "🤖 AI E'lon yaratish")
async def start_ai_announcement(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    if not (OPENAI_API_KEY or ANTHROPIC_API_KEY):
        await message.answer(
            "⚠️ <b>AI API kaliti topilmadi!</b>\n\n"
            "Iltimos, <code>OPENAI_API_KEY</code> yoki <code>ANTHROPIC_API_KEY</code>ni "
            ".env fayliga kiriting.",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
        return

    await state.set_state(AIAnnouncementCreation.waiting_input)
    await message.answer(
        "🤖 <b>AI Yordamchi — Turnir E'loni</b>\n\n"
        "Menga turnir haqida ma'lumot bering:\n\n"
        "📝 <b>Matn yuborish:</b> Oddiy xabar yozing\n"
        "🎤 <b>Ovozli xabar:</b> Gapirib yuboring\n\n"
        "<i>Misol: \"Ertaga kechki 8 da turnir, kirish 10 ming so'm, "
        "yutuq 100 ming, PSJ olinmasin, maq o'yin talab qilinadi...\"</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(AIAnnouncementCreation.waiting_input, F.text == "❌ Bekor qilish")
async def cancel_ai(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())


@router.message(AIAnnouncementCreation.waiting_input, F.text)
async def handle_text_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw_text = message.text.strip()
    if len(raw_text) < 10:
        await message.answer("⚠️ Iltimos, ko'proq ma'lumot kiriting (kamida 10 ta belgi).")
        return

    await message.answer("⏳ <b>AI e'lon yaratmoqda...</b> Bir oz kuting.", parse_mode="HTML")
    await _process_and_show_announcement(message, state, raw_text)


@router.message(AIAnnouncementCreation.waiting_input, F.voice)
async def handle_voice_input(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    if not OPENAI_API_KEY:
        await message.answer(
            "⚠️ Ovozni matnga o'girish uchun <code>OPENAI_API_KEY</code> kerak.\n"
            "Matn shaklida yuboring yoki API kalitini sozlang.",
            parse_mode="HTML",
        )
        return

    await message.answer("🎤 <b>Ovoz qabul qilindi, matnga o'girilmoqda...</b>", parse_mode="HTML")

    try:
        voice = message.voice
        file = await bot.get_file(voice.file_id)
        file_bytes = io.BytesIO()
        await bot.download_file(file.file_path, destination=file_bytes)
        file_bytes.seek(0)

        raw_text = await transcribe_voice_openai(file_bytes.read(), filename="voice.ogg")

        if not raw_text:
            await message.answer("⚠️ Ovoz aniqlanmadi. Iltimos qaytadan yuboring yoki matn kiriting.")
            return

        await message.answer(
            f"📝 <b>Ovozdan aniqlangan matn:</b>\n\n<i>{raw_text}</i>\n\n"
            "⏳ AI e'lon yaratmoqda...",
            parse_mode="HTML",
        )
        await _process_and_show_announcement(message, state, raw_text)

    except Exception as e:
        logger.error(f"Voice processing xatosi: {e}")
        await message.answer(
            f"❌ <b>Xatolik yuz berdi:</b> {e}\n\nIltimos matn shaklida yuboring.",
            parse_mode="HTML",
        )


async def _process_and_show_announcement(
    message: Message, state: FSMContext, raw_text: str
):
    """AI orqali e'lon yaratib adminga ko'rsatadi."""
    try:
        announcement = await generate_announcement(raw_text)
    except RuntimeError as e:
        await message.answer(f"❌ <b>AI xatosi:</b> {e}", parse_mode="HTML")
        await state.clear()
        await message.answer("Admin paneliga qaytildi.", reply_markup=admin_main_kb())
        return

    await state.update_data(raw_text=raw_text, announcement=announcement)
    await state.set_state(AIAnnouncementCreation.confirming)

    preview = (
        f"🤖 <b>AI yaratgan e'lon:</b>\n\n"
        f"{'─' * 30}\n\n"
        f"{announcement}\n\n"
        f"{'─' * 30}\n\n"
        "Tasdiqlaysizmi? Yoki qaytadan kiritasizmi?"
    )

    # Telegram 4096 belgi limiti
    if len(preview) > 4000:
        preview = preview[:4000] + "...\n\n(Matn qisqartirildi)"

    await message.answer(preview, parse_mode="HTML", reply_markup=ai_confirm_kb())


@router.callback_query(AIAnnouncementCreation.confirming, F.data == "ai_confirm")
async def confirm_announcement(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    announcement = data.get("announcement", "")
    raw_text = data.get("raw_text", "")
    await state.clear()

    tournament = await get_active_tournament()
    if not tournament:
        tournaments = await get_all_tournaments()
        tournament = tournaments[0] if tournaments else None

    if tournament:
        await update_tournament_rules(tournament["id"], raw_text, announcement)
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            f"✅ <b>E'lon tasdiqlandi va saqlandi!</b>\n\n"
            f"📛 Turnir: <b>{tournament['name']}</b>\n\n"
            "E'lonni ishtirokchilarga yuborish uchun yuqoridagi "
            "\"📢 Ishtirokchilarga yuborish\" tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
    else:
        await callback.message.answer(
            "✅ <b>E'lon tasdiqlandi!</b> (Faol turnir topilmadi — DB ga saqlanmadi)\n\n"
            f"<b>E'lon matni:</b>\n\n{announcement}",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
    await callback.answer("✅ Tasdiqlandi!")


@router.callback_query(AIAnnouncementCreation.confirming, F.data == "ai_retry")
async def retry_announcement(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await state.set_state(AIAnnouncementCreation.waiting_input)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "🔄 <b>Qaytadan kiritish</b>\n\n"
        "Turnir haqida ma'lumotni qaytadan yuboring (matn yoki ovoz):",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await callback.answer("🔄 Qaytadan kiritilmoqda")


@router.callback_query(AIAnnouncementCreation.confirming, F.data == "ai_broadcast")
async def broadcast_announcement(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    announcement = data.get("announcement", "")
    await state.clear()

    tournament = await get_active_tournament()
    if not tournament:
        tournaments = await get_all_tournaments()
        tournament = tournaments[0] if tournaments else None

    if not tournament:
        await callback.answer("⚠️ Faol turnir topilmadi!", show_alert=True)
        return

    # Saqlash
    await update_tournament_rules(tournament["id"], data.get("raw_text", ""), announcement)

    # Barcha ishtirokchilarga yuborish
    participants = await get_tournament_participants(tournament["id"])
    sent = 0
    failed = 0
    broadcast_text = (
        f"📢 <b>{tournament['name']} — Rasmiy E'lon</b>\n\n"
        f"{announcement}"
    )
    for p in participants:
        try:
            await bot.send_message(
                p["user_id"],
                broadcast_text[:4000],
                parse_mode="HTML",
            )
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast yuborilmadi user {p['user_id']}: {e}")
            failed += 1

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        f"📢 <b>E'lon yuborildi!</b>\n\n"
        f"✅ Muvaffaqiyatli: <b>{sent}</b> ta\n"
        f"❌ Yuborilmadi: <b>{failed}</b> ta",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )
    await callback.answer(f"📢 {sent} ta ishtirokchiga yuborildi!")
