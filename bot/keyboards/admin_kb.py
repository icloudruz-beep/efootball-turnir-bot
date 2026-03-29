from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def admin_main_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="🏆 Turnir yaratish"))
    builder.row(KeyboardButton(text="📋 Turnirlar ro'yxati"))
    builder.row(KeyboardButton(text="▶️ Qabulni ochish"), KeyboardButton(text="🎲 Qurani boshlash"))
    builder.row(KeyboardButton(text="📊 Ishtirokchilar"), KeyboardButton(text="🏁 Turnirni tugatish"))
    return builder.as_markup(resize_keyboard=True)


def payment_approval_kb(participant_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Tasdiqlash",
            callback_data=f"pay_approve:{participant_id}",
        ),
        InlineKeyboardButton(
            text="❌ Rad etish",
            callback_data=f"pay_reject:{participant_id}",
        ),
    )
    return builder.as_markup()


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)


def format_choice_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="Play-off"))
    builder.row(KeyboardButton(text="Guruh + Play-off"))
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)


def payment_type_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="To'lovli"), KeyboardButton(text="Bepul"))
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)


def dispute_kb(match_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Admin tasdiqlash",
            callback_data=f"admin_confirm:{match_id}",
        ),
        InlineKeyboardButton(
            text="🔄 Qayta o'ynatish",
            callback_data=f"admin_replay:{match_id}",
        ),
    )
    return builder.as_markup()
