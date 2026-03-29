from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def user_main_kb(has_registration: bool = False) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    if not has_registration:
        builder.row(KeyboardButton(text="📝 Ro'yxatdan o'tish"))
    else:
        builder.row(KeyboardButton(text="📊 Mening o'yinlarim"))
        builder.row(KeyboardButton(text="📤 Natija yuborish"))
    builder.row(KeyboardButton(text="ℹ️ Turnir haqida"))
    builder.row(KeyboardButton(text="Shikoyat qilish ⚠️"))
    return builder.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)


def result_confirm_kb(match_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ To'g'ri",
            callback_data=f"result_ok:{match_id}",
        ),
        InlineKeyboardButton(
            text="❌ Xato",
            callback_data=f"result_wrong:{match_id}",
        ),
    )
    return builder.as_markup()


def match_select_kb(matches: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for match in matches:
        builder.row(
            InlineKeyboardButton(
                text=f"O'yin #{match['id']}",
                callback_data=f"select_match:{match['id']}",
            )
        )
    return builder.as_markup()


def complaint_skip_kb() -> ReplyKeyboardMarkup:
    """Shikoyatda skrinshot o'tkazib yuborish tugmasi."""
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="⏭ Skrinshot o'tkazib yuborish"))
    builder.row(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)
