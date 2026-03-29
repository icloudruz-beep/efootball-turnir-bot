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
    builder.row(KeyboardButton(text="🤖 AI E'lon yaratish"))
    builder.row(KeyboardButton(text="📋 Turnirlar ro'yxati"))
    builder.row(KeyboardButton(text="▶️ Qabulni ochish"), KeyboardButton(text="🎲 Qurani boshlash"))
    builder.row(KeyboardButton(text="📊 Ishtirokchilar"), KeyboardButton(text="🏁 Turnirni tugatish"))
    builder.row(KeyboardButton(text="Homiylar 📢"), KeyboardButton(text="Shikoyatlar 📥"))
    return builder.as_markup(resize_keyboard=True)


def sponsor_menu_kb() -> InlineKeyboardMarkup:
    """Homiylar boshqaruv menyusi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Homiy qo'shish", callback_data="sponsor_add"))
    builder.row(InlineKeyboardButton(text="➖ Homiyni o'chirish", callback_data="sponsor_remove_list"))
    builder.row(InlineKeyboardButton(text="📋 Homiylar ro'yxati", callback_data="sponsor_list"))
    return builder.as_markup()


def sponsor_delete_kb(sponsors: list) -> InlineKeyboardMarkup:
    """O'chirish uchun homiylar ro'yxati."""
    builder = InlineKeyboardBuilder()
    for s in sponsors:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ {s['channel_name']}",
                callback_data=f"sponsor_del:{s['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="sponsor_back"))
    return builder.as_markup()


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


def ai_confirm_kb() -> InlineKeyboardMarkup:
    """AI tomonidan yaratilgan e'lonni tasdiqlash yoki qayta kiritish uchun tugmalar."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="ai_confirm"),
        InlineKeyboardButton(text="🔄 Qaytadan kiritish", callback_data="ai_retry"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Ishtirokchilarga yuborish", callback_data="ai_broadcast"),
    )
    return builder.as_markup()


def complaint_action_kb(complaint_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Shikoyat uchun admin harakatlar tugmalari."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="💬 Javob yozish",
            callback_data=f"complaint_reply:{complaint_id}:{user_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="🚫 Aybdorni chetlatish (Ban)",
            callback_data=f"complaint_ban:{complaint_id}:{user_id}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✅ Yopish (O'qildi)",
            callback_data=f"complaint_close:{complaint_id}",
        )
    )
    return builder.as_markup()
