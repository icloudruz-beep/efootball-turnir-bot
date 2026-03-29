"""
Umumiy handlerlar — noma'lum komandalar va xabarlar.
"""
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from bot.config import ADMIN_IDS

router = Router()


@router.message(Command("help"))
async def help_command(message: Message):
    if message.from_user.id in ADMIN_IDS:
        text = (
            "👑 <b>Admin buyruqlari:</b>\n\n"
            "/admin — Admin panelga kirish\n\n"
            "<b>Tugmalar:</b>\n"
            "🏆 Turnir yaratish — Yangi turnir ochish\n"
            "▶️ Qabulni ochish — Ro'yxatdan o'tishni faollashtirish\n"
            "🎲 Qurani boshlash — Tasodifiy qura\n"
            "📊 Ishtirokchilar — Ro'yxat ko'rish\n"
            "🏁 Turnirni tugatish — Turnirni yakunlash\n"
        )
    else:
        text = (
            "🎮 <b>eFootball Turnir Bot yordam</b>\n\n"
            "/start — Botni ishga tushirish\n\n"
            "<b>Tugmalar:</b>\n"
            "📝 Ro'yxatdan o'tish — Turnirga qo'shilish\n"
            "📊 Mening o'yinlarim — O'yinlaringizni ko'rish\n"
            "📤 Natija yuborish — O'yin natijasini yuborish\n"
            "ℹ️ Turnir haqida — Turnir ma'lumotlari\n"
        )
    await message.answer(text, parse_mode="HTML")


@router.message()
async def unknown_message(message: Message):
    await message.answer(
        "🤔 Tushunmadim. /help buyrug'ini ishlating.",
        parse_mode="HTML",
    )
