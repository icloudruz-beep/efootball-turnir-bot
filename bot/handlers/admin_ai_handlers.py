"""
AI yordamida turnir e'lonlari va qoidalar yaratish.

Ustuvorlik tartibi:
  1. Groq  — whisper-large-v3 (ovoz→matn) + llama-3.3-70b (matn yaratish) [BEPUL, TEZ]
  2. OpenAI — whisper-1 + gpt-4o [to'lovli, zaxira]
  3. Anthropic Claude — faqat matn yaratish uchun [zaxira]
"""
import io
import logging

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import AIAnnouncementCreation
from bot.keyboards.admin_kb import admin_main_kb, cancel_kb, ai_confirm_kb
from bot.config import ADMIN_IDS, OPENAI_API_KEY, ANTHROPIC_API_KEY, GROQ_API_KEY
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


# ─── Groq funksiyalari ─────────────────────────────────────────────────────────

async def transcribe_voice_groq(file_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Groq Whisper orqali ovozni matnga o'giradi (bepul, tez)."""
    try:
        import httpx
        audio_io = io.BytesIO(file_bytes)
        audio_io.name = filename

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                data={
                    "model": "whisper-large-v3",
                    "language": "uz",
                    "response_format": "text",
                },
                files={"file": (filename, audio_io, "audio/ogg")},
            )
            response.raise_for_status()
            return response.text.strip()
    except Exception as e:
        logger.error(f"Groq Whisper xatosi: {e}")
        raise RuntimeError(f"Groq ovoz→matn xatosi: {e}")


async def generate_announcement_groq(raw_text: str) -> str:
    """Groq LLaMA-3.3-70b orqali e'lon yaratadi (bepul, tez)."""
    try:
        import httpx
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": raw_text},
            ],
            "max_tokens": 1500,
            "temperature": 0.7,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Groq LLaMA xatosi: {e}")
        raise RuntimeError(f"Groq e'lon yaratish xatosi: {e}")


# ─── OpenAI zaxira funksiyalari ────────────────────────────────────────────────

async def transcribe_voice_openai(file_bytes: bytes, filename: str = "voice.ogg") -> str:
    """OpenAI Whisper orqali ovozni matnga o'giradi (zaxira)."""
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
        logger.error(f"OpenAI Whisper xatosi: {e}")
        raise RuntimeError(f"OpenAI ovoz→matn xatosi: {e}")


async def generate_announcement_openai(raw_text: str) -> str:
    """OpenAI GPT-4o orqali e'lon yaratadi (zaxira)."""
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
        raise RuntimeError(f"OpenAI e'lon yaratish xatosi: {e}")


async def generate_announcement_anthropic(raw_text: str) -> str:
    """Anthropic Claude orqali e'lon yaratadi (zaxira)."""
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
        raise RuntimeError(f"Claude e'lon yaratish xatosi: {e}")


# ─── Aqlli tanlov funksiyalari ────────────────────────────────────────────────

async def transcribe_voice(file_bytes: bytes, filename: str = "voice.ogg") -> str:
    """Groq → OpenAI ustuvorlik bilan ovozni matnga o'giradi."""
    if GROQ_API_KEY:
        try:
            logger.info("Groq Whisper ishlatilmoqda...")
            return await transcribe_voice_groq(file_bytes, filename)
        except Exception as e:
            logger.warning(f"Groq Whisper ishlamadi: {e}. OpenAI ga o'tilmoqda.")

    if OPENAI_API_KEY:
        try:
            logger.info("OpenAI Whisper ishlatilmoqda...")
            return await transcribe_voice_openai(file_bytes, filename)
        except Exception as e:
            raise RuntimeError(f"Ovozni matnga o'girishda barcha API lar ishlamadi. Oxirgi xato: {e}")

    raise RuntimeError(
        "Ovozni matnga o'girish uchun GROQ_API_KEY yoki OPENAI_API_KEY kerak."
    )


async def generate_announcement(raw_text: str) -> str:
    """Groq → OpenAI → Anthropic ustuvorlik bilan e'lon yaratadi."""
    if GROQ_API_KEY:
        try:
            logger.info("Groq LLaMA ishlatilmoqda...")
            return await generate_announcement_groq(raw_text)
        except Exception as e:
            logger.warning(f"Groq ishlamadi: {e}. OpenAI ga o'tilmoqda.")

    if OPENAI_API_KEY:
        try:
            logger.info("OpenAI GPT-4o ishlatilmoqda...")
            return await generate_announcement_openai(raw_text)
        except Exception as e:
            logger.warning(f"OpenAI ishlamadi: {e}. Anthropic ga o'tilmoqda.")

    if ANTHROPIC_API_KEY:
        try:
            logger.info("Anthropic Claude ishlatilmoqda...")
            return await generate_announcement_anthropic(raw_text)
        except Exception as e:
            raise RuntimeError(f"Barcha AI API lar ishlamadi. Oxirgi xato: {e}")

    raise RuntimeError(
        "AI API kalitlari topilmadi. GROQ_API_KEY, OPENAI_API_KEY yoki "
        "ANTHROPIC_API_KEY ni .env ga kiriting."
    )


def _has_any_api_key() -> bool:
    return bool(GROQ_API_KEY or OPENAI_API_KEY or ANTHROPIC_API_KEY)


def _active_ai_name() -> str:
    if GROQ_API_KEY:
        return "Groq LLaMA-3.3"
    if OPENAI_API_KEY:
        return "OpenAI GPT-4o"
    if ANTHROPIC_API_KEY:
        return "Anthropic Claude"
    return "Noma'lum"


# ─── Handlerlar ───────────────────────────────────────────────────────────────

@router.message(F.text == "🤖 AI E'lon yaratish")
async def start_ai_announcement(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    if not _has_any_api_key():
        await message.answer(
            "⚠️ <b>AI API kaliti topilmadi!</b>\n\n"
            "Iltimos, quyidagilardan birini .env ga kiriting:\n"
            "• <code>GROQ_API_KEY</code> — bepul, tez (tavsiya etiladi)\n"
            "• <code>OPENAI_API_KEY</code> — to'lovli\n"
            "• <code>ANTHROPIC_API_KEY</code> — to'lovli",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
        return

    await state.set_state(AIAnnouncementCreation.waiting_input)
    await message.answer(
        f"🤖 <b>AI Yordamchi — Turnir E'loni</b>\n"
        f"<i>Faol AI: {_active_ai_name()}</i>\n\n"
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

    wait_msg = await message.answer(
        f"⏳ <b>{_active_ai_name()} e'lon yaratmoqda...</b> Bir oz kuting.",
        parse_mode="HTML",
    )
    await _process_and_show_announcement(message, state, raw_text)
    try:
        await wait_msg.delete()
    except Exception:
        pass


@router.message(AIAnnouncementCreation.waiting_input, F.voice)
async def handle_voice_input(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    if not (GROQ_API_KEY or OPENAI_API_KEY):
        await message.answer(
            "⚠️ Ovozni matnga o'girish uchun <code>GROQ_API_KEY</code> yoki "
            "<code>OPENAI_API_KEY</code> kerak.\n"
            "Matn shaklida yuboring yoki Groq API kalitini sozlang.",
            parse_mode="HTML",
        )
        return

    stt_name = "Groq Whisper" if GROQ_API_KEY else "OpenAI Whisper"
    wait_msg = await message.answer(
        f"🎤 <b>Ovoz qabul qilindi!</b>\n"
        f"<i>{stt_name} orqali matnga o'girilmoqda...</i>",
        parse_mode="HTML",
    )

    try:
        voice = message.voice
        file = await bot.get_file(voice.file_id)
        file_bytes_io = io.BytesIO()
        await bot.download_file(file.file_path, destination=file_bytes_io)
        file_bytes_io.seek(0)

        raw_text = await transcribe_voice(file_bytes_io.read(), filename="voice.ogg")

        if not raw_text:
            await wait_msg.edit_text("⚠️ Ovoz aniqlanmadi. Iltimos qaytadan yuboring yoki matn kiriting.")
            return

        await wait_msg.edit_text(
            f"📝 <b>Ovozdan aniqlangan matn:</b>\n\n<i>{raw_text}</i>\n\n"
            f"⏳ <b>{_active_ai_name()}</b> e'lon yaratmoqda...",
            parse_mode="HTML",
        )
        await _process_and_show_announcement(message, state, raw_text)
        try:
            await wait_msg.delete()
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Voice processing xatosi: {e}")
        try:
            await wait_msg.edit_text(
                f"❌ <b>Xatolik:</b> {e}\n\nIltimos matn shaklida yuboring.",
                parse_mode="HTML",
            )
        except Exception:
            await message.answer(
                f"❌ <b>Xatolik:</b> {e}\n\nIltimos matn shaklida yuboring.",
                parse_mode="HTML",
            )


async def _process_and_show_announcement(message: Message, state: FSMContext, raw_text: str):
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
        f"🤖 <b>{_active_ai_name()} yaratgan e'lon:</b>\n\n"
        f"{'─' * 30}\n\n"
        f"{announcement}\n\n"
        f"{'─' * 30}\n\n"
        "Tasdiqlaysizmi?"
    )

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
            f"📛 Turnir: <b>{tournament['name']}</b>",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
    else:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "✅ <b>E'lon tasdiqlandi!</b> (Faol turnir topilmadi — DB ga saqlanmadi)",
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
        "🔄 <b>Qaytadan kiritish</b>\n\nTurnir haqida ma'lumotni qaytadan yuboring:",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await callback.answer("🔄 Qaytadan")


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

    await update_tournament_rules(tournament["id"], data.get("raw_text", ""), announcement)

    participants = await get_tournament_participants(tournament["id"])
    sent = 0
    failed = 0
    broadcast_text = (
        f"📢 <b>{tournament['name']} — Rasmiy E'lon</b>\n\n"
        f"{announcement}"
    )
    for p in participants:
        try:
            await bot.send_message(p["user_id"], broadcast_text[:4000], parse_mode="HTML")
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast user {p['user_id']}: {e}")
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
