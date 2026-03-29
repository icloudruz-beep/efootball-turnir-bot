"""
Admin handlerlari — turnir yaratish, qabul ochish, qurani boshlash.
"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from bot.states import TournamentCreation
from bot.keyboards.admin_kb import (
    admin_main_kb,
    cancel_kb,
    format_choice_kb,
    payment_type_kb,
    payment_approval_kb,
    dispute_kb,
)
from bot.db.tournaments import (
    create_tournament,
    get_active_tournament,
    update_tournament_status,
    get_all_tournaments,
    get_tournament,
)
from bot.db.participants import (
    get_tournament_participants,
    update_payment_status,
    count_approved_participants,
    get_participant,
)
from bot.db.matches import get_tournament_matches, confirm_match_result, get_match
from bot.utils.draw_utils import run_playoff_draw, run_group_draw, determine_winner
from bot.utils.bracket_generator import (
    generate_playoff_bracket,
    generate_group_stage_image,
)
from bot.config import ADMIN_IDS

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
@router.message(F.text == "/start", F.from_user.id.func(is_admin))
async def admin_start(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "👑 <b>Admin panelga xush kelibsiz!</b>\n\nQuyidagi tugmalardan birini tanlang:",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.message(F.text == "🏆 Turnir yaratish")
async def start_create_tournament(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await state.set_state(TournamentCreation.name)
    await message.answer(
        "🏆 <b>Yangi turnir yaratish</b>\n\n"
        "Turnir nomini kiriting:\n"
        "<i>(Masalan: eFootball Premier League 2025)</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(TournamentCreation.name, F.text == "❌ Bekor qilish")
@router.message(TournamentCreation.max_participants, F.text == "❌ Bekor qilish")
@router.message(TournamentCreation.format, F.text == "❌ Bekor qilish")
@router.message(TournamentCreation.payment_type, F.text == "❌ Bekor qilish")
@router.message(TournamentCreation.price, F.text == "❌ Bekor qilish")
@router.message(TournamentCreation.card_number, F.text == "❌ Bekor qilish")
async def cancel_creation(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ Turnir yaratish bekor qilindi.", reply_markup=admin_main_kb())


@router.message(TournamentCreation.name)
async def tournament_name_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(TournamentCreation.max_participants)
    await message.answer(
        "👥 <b>Ishtirokchilar soni</b>\n\n"
        "Nechta ishtirokchi bo'ladi?\n"
        "<i>(Masalan: 8, 16, 32, 64)</i>",
        parse_mode="HTML",
    )


@router.message(TournamentCreation.max_participants)
async def tournament_participants_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        n = int(message.text.strip())
        if n < 2 or n > 128:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Iltimos, 2 dan 128 gacha bo'lgan son kiriting.")
        return
    await state.update_data(max_participants=n)
    await state.set_state(TournamentCreation.format)
    await message.answer(
        "🗂 <b>Turnir formati</b>\n\nQanday format bo'ladi?",
        parse_mode="HTML",
        reply_markup=format_choice_kb(),
    )


@router.message(TournamentCreation.format)
async def tournament_format_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if text == "Play-off":
        fmt = "playoff"
    elif text == "Guruh + Play-off":
        fmt = "group_playoff"
    else:
        await message.answer("⚠️ Iltimos, tugmalardan birini tanlang.")
        return
    await state.update_data(format=fmt)
    await state.set_state(TournamentCreation.payment_type)
    await message.answer(
        "💳 <b>To'lov turi</b>\n\nTurnir to'lovlimi yoki bepulmi?",
        parse_mode="HTML",
        reply_markup=payment_type_kb(),
    )


@router.message(TournamentCreation.payment_type)
async def tournament_payment_type_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if text == "Bepul":
        await state.update_data(is_paid=False, price=0.0, card_number="")
        data = await state.get_data()
        await state.clear()
        tid = await create_tournament(
            name=data["name"],
            max_participants=data["max_participants"],
            format_=data["format"],
            is_paid=False,
        )
        await message.answer(
            f"✅ <b>Turnir yaratildi!</b>\n\n"
            f"📛 Nom: <b>{data['name']}</b>\n"
            f"👥 Ishtirokchilar: <b>{data['max_participants']}</b>\n"
            f"🗂 Format: <b>{'Play-off' if data['format'] == 'playoff' else 'Guruh + Play-off'}</b>\n"
            f"💳 To'lov: <b>Bepul</b>\n\n"
            f"Endi <b>▶️ Qabulni ochish</b> tugmasini bosing.",
            parse_mode="HTML",
            reply_markup=admin_main_kb(),
        )
    elif text == "To'lovli":
        await state.update_data(is_paid=True)
        await state.set_state(TournamentCreation.price)
        await message.answer(
            "💰 <b>Turnir narxi</b>\n\nNarxni kiriting (so'mda):\n<i>(Masalan: 50000)</i>",
            parse_mode="HTML",
        )
    else:
        await message.answer("⚠️ Iltimos, tugmalardan birini tanlang.")


@router.message(TournamentCreation.price)
async def tournament_price_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text.strip().replace(" ", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Iltimos, to'g'ri narx kiriting.")
        return
    await state.update_data(price=price)
    await state.set_state(TournamentCreation.card_number)
    await message.answer(
        "💳 <b>Karta raqami</b>\n\nTo'lov uchun karta raqamini kiriting:",
        parse_mode="HTML",
    )


@router.message(TournamentCreation.card_number)
async def tournament_card_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    card = message.text.strip()
    data = await state.get_data()
    await state.clear()
    tid = await create_tournament(
        name=data["name"],
        max_participants=data["max_participants"],
        format_=data["format"],
        is_paid=True,
        price=data["price"],
        card_number=card,
    )
    await message.answer(
        f"✅ <b>Turnir yaratildi!</b>\n\n"
        f"📛 Nom: <b>{data['name']}</b>\n"
        f"👥 Ishtirokchilar: <b>{data['max_participants']}</b>\n"
        f"🗂 Format: <b>{'Play-off' if data['format'] == 'playoff' else 'Guruh + Play-off'}</b>\n"
        f"💳 Narx: <b>{data['price']:,.0f} so'm</b>\n"
        f"🏦 Karta: <code>{card}</code>\n\n"
        f"Endi <b>▶️ Qabulni ochish</b> tugmasini bosing.",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.message(F.text == "▶️ Qabulni ochish")
async def open_registration(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    tournament = await get_active_tournament()
    if not tournament:
        tournaments = await get_all_tournaments()
        if not tournaments:
            await message.answer("⚠️ Avval turnir yarating!")
            return
        tournament = tournaments[0]
    if tournament["status"] == "registration":
        await message.answer("⚠️ Ro'yxatdan o'tish allaqachon ochiq!")
        return
    await update_tournament_status(tournament["id"], "registration")
    await message.answer(
        f"✅ <b>Ro'yxatdan o'tish ochildi!</b>\n\n"
        f"📛 Turnir: <b>{tournament['name']}</b>\n"
        f"👥 Max ishtirokchilar: <b>{tournament['max_participants']}</b>\n\n"
        f"Foydalanuvchilar endi ro'yxatdan o'tishlari mumkin.",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.message(F.text == "📋 Turnirlar ro'yxati")
async def list_tournaments(message: Message):
    if not is_admin(message.from_user.id):
        return
    tournaments = await get_all_tournaments()
    if not tournaments:
        await message.answer("📋 Hech qanday turnir topilmadi.")
        return
    text = "📋 <b>Turnirlar ro'yxati:</b>\n\n"
    status_map = {
        "draft": "📝 Loyiha",
        "registration": "🟢 Qabul ochiq",
        "started": "⚽ Davom etmoqda",
        "finished": "🏁 Tugagan",
    }
    for t in tournaments:
        st = status_map.get(t["status"], t["status"])
        text += (
            f"• <b>{t['name']}</b> (ID: {t['id']})\n"
            f"  {st} | 👥 {t['max_participants']} kishi\n\n"
        )
    await message.answer(text, parse_mode="HTML", reply_markup=admin_main_kb())


@router.message(F.text == "📊 Ishtirokchilar")
async def show_participants(message: Message):
    if not is_admin(message.from_user.id):
        return
    tournament = await get_active_tournament()
    if not tournament:
        await message.answer("⚠️ Faol turnir topilmadi.")
        return
    participants = await get_tournament_participants(tournament["id"])
    if not participants:
        await message.answer("👥 Hali ishtirokchi yo'q.")
        return
    status_map = {
        "pending": "⏳",
        "approved": "✅",
        "rejected": "❌",
        "free": "🆓",
    }
    text = f"📊 <b>{tournament['name']} — Ishtirokchilar</b>\n\n"
    for i, p in enumerate(participants, 1):
        st = status_map.get(p["status"] if "status" in p.keys() else p["payment_status"], "?")
        text += (
            f"{i}. {st} <b>{p['team_name']}</b>\n"
            f"   🎮 ID: {p['game_id']} | 📞 {p['phone']}\n"
        )
    approved_count = await count_approved_participants(tournament["id"])
    text += f"\n✅ Tasdiqlangan: <b>{approved_count}</b> / {tournament['max_participants']}"
    await message.answer(text, parse_mode="HTML", reply_markup=admin_main_kb())


@router.message(F.text == "🎲 Qurani boshlash")
async def start_draw(message: Message, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    tournament = await get_active_tournament()
    if not tournament:
        await message.answer("⚠️ Faol turnir topilmadi.")
        return
    approved = await count_approved_participants(tournament["id"])
    if approved < 2:
        await message.answer(f"⚠️ Qura uchun kamida 2 ta tasdiqlangan ishtirokchi kerak. Hozir: {approved}")
        return

    await update_tournament_status(tournament["id"], "started")
    await message.answer("🎲 Qura boshlanmoqda... Iltimos kuting.")

    try:
        participants = await get_tournament_participants(tournament["id"], approved_only=True)
        participants = list(participants)
        fmt = tournament["format"]

        if fmt == "playoff":
            parts, match_ids = await run_playoff_draw(tournament["id"])
            matches = await get_tournament_matches(tournament["id"])
            img_bytes = generate_playoff_bracket(
                participants=[dict(p) for p in parts],
                tournament_name=tournament["name"],
                matches=[dict(m) for m in matches],
            )
            from aiogram.types import BufferedInputFile
            photo = BufferedInputFile(img_bytes, filename="bracket.png")
            await message.answer_photo(
                photo=photo,
                caption=(
                    f"🎲 <b>{tournament['name']}</b>\n\n"
                    f"Play-off setka tayyor! Jami {len(parts)} ishtirokchi.\n"
                    f"O'yinchilar natijalarini yuborishlarini kuting."
                ),
                parse_mode="HTML",
            )
        else:
            group_size = 4
            groups = await run_group_draw(tournament["id"], group_size=group_size)
            group_dict = {k: [dict(p) for p in v] for k, v in groups.items()}
            img_bytes = generate_group_stage_image(group_dict, tournament["name"])
            from aiogram.types import BufferedInputFile
            photo = BufferedInputFile(img_bytes, filename="groups.png")
            await message.answer_photo(
                photo=photo,
                caption=(
                    f"🎲 <b>{tournament['name']}</b>\n\n"
                    f"Guruhlar tayyor! {len(groups)} ta guruh.\n"
                    f"O'yinchilar natijalarini yuborishlarini kuting."
                ),
                parse_mode="HTML",
            )
    except Exception as e:
        await message.answer(f"⚠️ Qura jarayonida xatolik: {e}", reply_markup=admin_main_kb())


@router.message(F.text == "🏁 Turnirni tugatish")
async def finish_tournament(message: Message):
    if not is_admin(message.from_user.id):
        return
    tournament = await get_active_tournament()
    if not tournament:
        await message.answer("⚠️ Faol turnir topilmadi.")
        return
    await update_tournament_status(tournament["id"], "finished")
    await message.answer(
        f"🏁 <b>{tournament['name']}</b> turniri yakunlandi!",
        parse_mode="HTML",
        reply_markup=admin_main_kb(),
    )


@router.callback_query(F.data.startswith("pay_approve:"))
async def approve_payment(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    await update_payment_status(participant_id, "approved")
    participant = await get_participant(participant_id)
    if participant:
        try:
            await bot.send_message(
                participant["user_id"],
                "✅ <b>To'lovingiz tasdiqlandi!</b>\n\nSiz turnirga qabul qilindingiz. Omad!",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n✅ <b>TASDIQLANDI</b>",
        parse_mode="HTML",
    )
    await callback.answer("✅ Tasdiqlandi!")


@router.callback_query(F.data.startswith("pay_reject:"))
async def reject_payment(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    participant_id = int(callback.data.split(":")[1])
    await update_payment_status(participant_id, "rejected")
    participant = await get_participant(participant_id)
    if participant:
        try:
            await bot.send_message(
                participant["user_id"],
                "❌ <b>To'lovingiz rad etildi.</b>\n\nIltimos, to'g'ri to'lov skrinshoti yuboring.",
                parse_mode="HTML",
            )
        except Exception:
            pass
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n❌ <b>RAD ETILDI</b>",
        parse_mode="HTML",
    )
    await callback.answer("❌ Rad etildi!")


@router.callback_query(F.data.startswith("admin_confirm:"))
async def admin_confirm_match(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    match_id = int(callback.data.split(":")[1])
    match = await get_match(match_id)
    if not match:
        await callback.answer("Match topilmadi!")
        return
    winner = await determine_winner(match)
    if winner:
        await confirm_match_result(match_id, winner)
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>Admin tomonidan tasdiqlandi.</b>",
            parse_mode="HTML",
        )
        await callback.answer("Natija tasdiqlandi!")
    else:
        await callback.answer("Natija aniqlanmadi!")


@router.callback_query(F.data.startswith("admin_replay:"))
async def admin_replay_match(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    match_id = int(callback.data.split(":")[1])
    from bot.db.matches import dispute_match
    await dispute_match(match_id)
    await callback.message.edit_text(
        callback.message.text + "\n\n🔄 <b>O'yin qayta o'ynatilishi kerak.</b>",
        parse_mode="HTML",
    )
    await callback.answer("Qayta o'ynatish buyurildi!")
