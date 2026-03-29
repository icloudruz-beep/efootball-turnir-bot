"""
Homiylar (Sponsors) tizimi — Force Subscription handlerlari.

Admin oqimi:
  "Homiylar 📢" → inline menyu (qo'shish / o'chirish / ro'yxat)

Foydalanuvchi oqimi:
  Ro'yxatdan o'tish yoki /start → barcha homiy kanallarga obuna tekshiruvi →
  obuna bo'lmagan kanallar inline tugma bilan ko'rsatiladi →
  "✅ Obunani tekshirish" → qayta tekshiruv → o'tsa, davom etiladi.
"""
import logging

from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.states import SponsorAdd, PlayerRegistration
from bot.keyboards.admin_kb import admin_main_kb, cancel_kb, sponsor_menu_kb, sponsor_delete_kb
from bot.config import ADMIN_IDS
from bot.db.sponsors import add_sponsor, remove_sponsor, get_all_sponsors, get_sponsor
from bot.db.tournaments import get_active_tournament
from bot.db.participants import get_participant_by_user, count_approved_participants

logger = logging.getLogger(__name__)
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── Yordamchi: obuna tekshiruvi ─────────────────────────────────────────────

async def get_unsubscribed_channels(bot: Bot, user_id: int) -> list[dict]:
    """
    Foydalanuvchi obuna bo'lmagan homiy kanallar ro'yxatini qaytaradi.
    Bot kanal admini bo'lmasa yoki kanal topilmasa, o'sha kanal ham ro'yxatga qo'shiladi.
    """
    sponsors = await get_all_sponsors()
    if not sponsors:
        return []

    unsubscribed = []
    for sponsor in sponsors:
        try:
            member = await bot.get_chat_member(
                chat_id=sponsor["channel_id"], user_id=user_id
            )
            if member.status in ("left", "kicked", "banned"):
                unsubscribed.append(sponsor)
        except Exception as e:
            err_str = str(e).lower()
            if "bot is not a member" in err_str or "chat not found" in err_str:
                logger.warning(
                    f"Kanal {sponsor['channel_id']} tekshirib bo'lmadi: {e}. "
                    "Bot kanal admini emasmi?"
                )
            else:
                logger.warning(f"Obuna tekshirishda xato (kanal {sponsor['channel_id']}): {e}")
            unsubscribed.append(sponsor)

    return unsubscribed


def build_subscribe_keyboard(unsubscribed: list, action: str = "register") -> InlineKeyboardMarkup:
    """Obuna bo'linmagan kanallar uchun inline tugmalar + tekshirish tugmasi."""
    builder = InlineKeyboardBuilder()
    for ch in unsubscribed:
        builder.row(
            InlineKeyboardButton(
                text=f"➕ {ch['channel_name']}",
                url=ch["channel_link"],
            )
        )
    builder.row(
        InlineKeyboardButton(
            text="✅ Obunani tekshirish",
            callback_data=f"check_sub:{action}",
        )
    )
    return builder.as_markup()


async def check_subscriptions_and_notify(
    message: Message, bot: Bot, user_id: int, action: str = "register"
) -> bool:
    """
    Obuna tekshiradi. Agar yetishmasa, xabar yuboradi va False qaytaradi.
    Agar hammaga obuna bo'lsa, True qaytaradi.
    """
    unsubscribed = await get_unsubscribed_channels(bot, user_id)
    if not unsubscribed:
        return True

    channels_text = "\n".join(
        f"  • <b>{ch['channel_name']}</b>" for ch in unsubscribed
    )
    await message.answer(
        "🔒 <b>Majburiy obuna!</b>\n\n"
        "Turnirda qatnashish uchun quyidagi homiy kanallarga obuna bo'lishingiz shart:\n\n"
        f"{channels_text}\n\n"
        "Obuna bo'lgach, <b>\"✅ Obunani tekshirish\"</b> tugmasini bosing.",
        parse_mode="HTML",
        reply_markup=build_subscribe_keyboard(unsubscribed, action),
    )
    return False


# ─── Callback: "✅ Obunani tekshirish" ────────────────────────────────────────

@router.callback_query(F.data.startswith("check_sub:"))
async def check_subscription_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    action = callback.data.split(":")[1]
    user_id = callback.from_user.id

    unsubscribed = await get_unsubscribed_channels(bot, user_id)

    if unsubscribed:
        # Hali ba'zi kanallarga obuna bo'lmagan
        try:
            await callback.message.edit_reply_markup(
                reply_markup=build_subscribe_keyboard(unsubscribed, action)
            )
        except Exception:
            pass
        await callback.answer(
            "❌ Hali ba'zi kanallarga obuna bo'lmadingiz!",
            show_alert=True,
        )
        return

    # ✅ Barcha kanallarga obuna bo'lgan
    await callback.answer("✅ Ajoyib! Barcha kanallarga obunasiz!")

    try:
        await callback.message.delete()
    except Exception:
        pass

    if action == "register":
        # Ro'yxatdan o'tish oqimini to'g'ridan boshlash
        tournament = await get_active_tournament()
        if not tournament:
            await callback.message.answer("⚠️ Hozirda faol turnir yo'q.")
            return
        if tournament["status"] != "registration":
            await callback.message.answer("⚠️ Ro'yxatdan o'tish hali ochilmagan yoki yopilgan.")
            return

        existing = await get_participant_by_user(tournament["id"], user_id)
        if existing:
            st = existing["payment_status"]
            if st in ("approved", "free"):
                await callback.message.answer("✅ Siz allaqachon ro'yxatdan o'tgansiz!")
            elif st == "pending":
                await callback.message.answer("⏳ To'lovingiz tasdiqlanishi kutilmoqda.")
            elif st == "rejected":
                await callback.message.answer("❌ To'lovingiz rad etilgan. Qaytadan yuboring.")
            return

        approved = await count_approved_participants(tournament["id"])
        if approved >= tournament["max_participants"]:
            await callback.message.answer("⚠️ Turnir to'ldi. Ro'yxatdan o'tib bo'lmaydi.")
            return

        await state.set_state(PlayerRegistration.game_id)
        await state.update_data(tournament_id=tournament["id"])
        from bot.keyboards.user_kb import cancel_kb as user_cancel_kb
        await callback.message.answer(
            "📝 <b>Ro'yxatdan o'tish</b>\n\n"
            "Birinchi, <b>eFootball Game ID</b>ingizni kiriting:\n"
            "<i>(Bu raqamni eFootball o'yinida profil bo'limidan topasiz)</i>",
            parse_mode="HTML",
            reply_markup=user_cancel_kb(),
        )
    else:
        # /start yoki boshqa holat — asosiy menyuga qaytarish
        from bot.keyboards.user_kb import user_main_kb
        await callback.message.answer(
            "✅ <b>Barcha shartlar bajarildi!</b>\n\nEndi turnirga qatnashishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=user_main_kb(),
        )


# ─── Admin: Homiylar menyusi ──────────────────────────────────────────────────

@router.message(F.text == "Homiylar 📢")
async def show_sponsor_menu(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    sponsors = await get_all_sponsors()
    count_text = f"Hozir <b>{len(sponsors)}</b> ta homiy kanal mavjud." if sponsors else "Hozircha homiy kanal yo'q."

    await message.answer(
        f"📢 <b>Homiylar boshqaruvi</b>\n\n"
        f"{count_text}\n\n"
        "Nima qilmoqchisiz?",
        parse_mode="HTML",
        reply_markup=sponsor_menu_kb(),
    )


@router.callback_query(F.data == "sponsor_back")
async def sponsor_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    sponsors = await get_all_sponsors()
    count_text = f"Hozir <b>{len(sponsors)}</b> ta homiy kanal mavjud." if sponsors else "Hozircha homiy kanal yo'q."
    try:
        await callback.message.edit_text(
            f"📢 <b>Homiylar boshqaruvi</b>\n\n{count_text}\n\nNima qilmoqchisiz?",
            parse_mode="HTML",
            reply_markup=sponsor_menu_kb(),
        )
    except Exception:
        pass
    await callback.answer()


# ─── Admin: Homiy qo'shish (FSM) ──────────────────────────────────────────────

@router.callback_query(F.data == "sponsor_add")
async def sponsor_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await state.set_state(SponsorAdd.channel_id)
    await callback.message.answer(
        "➕ <b>Yangi homiy kanal qo'shish</b>\n\n"
        "<b>1-qadam:</b> Kanal ID sini kiriting.\n\n"
        "📌 <b>Kanal ID ni qanday topish:</b>\n"
        "• Kanalga @userinfobot yoki @getidsbot qo'shing\n"
        "• Yoki Forward qilib shu botga yuboring\n"
        "• Format: <code>-1001234567890</code> (minus bilan boshlanadi)\n\n"
        "⚠️ <b>Eslatma:</b> Botni o'sha kanalga <b>administrator</b> qilib qo'shing!",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )
    await callback.answer()


@router.message(SponsorAdd.channel_id, F.text == "❌ Bekor qilish")
@router.message(SponsorAdd.channel_name, F.text == "❌ Bekor qilish")
@router.message(SponsorAdd.channel_link, F.text == "❌ Bekor qilish")
async def cancel_sponsor_add(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ Bekor qilindi.", reply_markup=admin_main_kb())


@router.message(SponsorAdd.channel_id, F.text)
async def sponsor_channel_id_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    raw = message.text.strip().replace(" ", "")
    try:
        channel_id = int(raw)
    except ValueError:
        await message.answer(
            "⚠️ Noto'g'ri format! Kanal ID raqam bo'lishi kerak.\n"
            "Misol: <code>-1001234567890</code>",
            parse_mode="HTML",
        )
        return

    await state.update_data(channel_id=channel_id)
    await state.set_state(SponsorAdd.channel_name)
    await message.answer(
        "<b>2-qadam:</b> Kanal nomini kiriting.\n"
        "<i>Masalan: eFootball Uzbekistan</i>",
        parse_mode="HTML",
    )


@router.message(SponsorAdd.channel_name, F.text)
async def sponsor_channel_name_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Kanal nomi juda qisqa.")
        return
    await state.update_data(channel_name=name)
    await state.set_state(SponsorAdd.channel_link)
    await message.answer(
        "<b>3-qadam:</b> Kanal ssilkasini kiriting.\n"
        "<i>Masalan: https://t.me/mening_kanalim</i>",
        parse_mode="HTML",
    )


@router.message(SponsorAdd.channel_link, F.text)
async def sponsor_channel_link_received(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    link = message.text.strip()
    if not (link.startswith("https://t.me/") or link.startswith("http://t.me/")):
        await message.answer(
            "⚠️ Kanal ssilkasi <code>https://t.me/</code> bilan boshlanishi kerak.",
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    channel_id = data["channel_id"]
    channel_name = data["channel_name"]
    await state.clear()

    # Bot kanalga admin ekanligini tekshirish
    bot_is_admin = False
    try:
        bot_info = await bot.get_me()
        bot_member = await bot.get_chat_member(channel_id, bot_info.id)
        if bot_member.status in ("administrator", "creator"):
            bot_is_admin = True
    except Exception as e:
        logger.warning(f"Bot admin tekshirishda xato: {e}")

    try:
        sponsor_id = await add_sponsor(channel_id, channel_name, link)
    except Exception as e:
        await message.answer(f"❌ Saqlashda xatolik: {e}", reply_markup=admin_main_kb())
        return

    admin_warning = ""
    if not bot_is_admin:
        admin_warning = (
            "\n\n⚠️ <b>Muhim:</b> Bot hali kanalga admin qilinmagan!\n"
            "Obuna tekshiruvi to'g'ri ishlamaydi. Botni kanalga admin qiling!"
        )

    await message.answer(
        f"✅ <b>Homiy kanal qo'shildi!</b>\n\n"
        f"📛 Nom: <b>{channel_name}</b>\n"
        f"🆔 ID: <code>{channel_id}</code>\n"
        f"🔗 Link: {link}"
        f"{admin_warning}",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


# ─── Admin: Homiy o'chirish ────────────────────────────────────────────────────

@router.callback_query(F.data == "sponsor_remove_list")
async def sponsor_remove_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    sponsors = await get_all_sponsors()
    if not sponsors:
        await callback.answer("📋 Homiy kanal yo'q.", show_alert=True)
        return
    try:
        await callback.message.edit_text(
            "➖ <b>O'chirmoqchi bo'lgan homiy kanalni tanlang:</b>",
            parse_mode="HTML",
            reply_markup=sponsor_delete_kb(sponsors),
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("sponsor_del:"))
async def sponsor_delete(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    sponsor_id = int(callback.data.split(":")[1])
    sponsor = await get_sponsor(sponsor_id)
    name = sponsor["channel_name"] if sponsor else "Noma'lum"

    deleted = await remove_sponsor(sponsor_id)
    if deleted:
        await callback.answer(f"✅ '{name}' o'chirildi!")
    else:
        await callback.answer("❌ Topilmadi yoki allaqachon o'chirilgan.")

    # Yangilangan ro'yxatni ko'rsatish
    sponsors = await get_all_sponsors()
    if sponsors:
        try:
            await callback.message.edit_text(
                "➖ <b>O'chirmoqchi bo'lgan homiy kanalni tanlang:</b>",
                parse_mode="HTML",
                reply_markup=sponsor_delete_kb(sponsors),
            )
        except Exception:
            pass
    else:
        try:
            await callback.message.edit_text(
                "📢 <b>Homiylar boshqaruvi</b>\n\nHozircha homiy kanal yo'q.\n\nNima qilmoqchisiz?",
                parse_mode="HTML",
                reply_markup=sponsor_menu_kb(),
            )
        except Exception:
            pass


# ─── Admin: Homiylar ro'yxati ─────────────────────────────────────────────────

@router.callback_query(F.data == "sponsor_list")
async def sponsor_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    sponsors = await get_all_sponsors()
    if not sponsors:
        await callback.answer("📋 Homiy kanal yo'q.", show_alert=True)
        return

    text = "📋 <b>Homiy kanallar ro'yxati:</b>\n\n"
    for i, s in enumerate(sponsors, 1):
        text += (
            f"{i}. <b>{s['channel_name']}</b>\n"
            f"   🆔 <code>{s['channel_id']}</code>\n"
            f"   🔗 {s['channel_link']}\n\n"
        )

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=sponsor_menu_kb(),
        )
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=sponsor_menu_kb())
    await callback.answer()
