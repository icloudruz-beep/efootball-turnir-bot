"""
Foydalanuvchi handlerlari — ro'yxatdan o'tish, natija yuborish.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, PhotoSize
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from bot.states import PlayerRegistration, ResultSubmission
from bot.keyboards.user_kb import user_main_kb, cancel_kb, result_confirm_kb, match_select_kb
from bot.keyboards.admin_kb import dispute_kb, payment_approval_kb
from bot.db.tournaments import get_active_tournament
from bot.db.participants import (
    add_participant,
    get_participant_by_user,
    update_payment_status,
    get_participant,
    count_approved_participants,
)
from bot.db.matches import (
    get_pending_matches_for_participant,
    submit_match_result,
    get_match,
    confirm_match_result,
    dispute_match,
    get_tournament_matches,
)
from bot.utils.draw_utils import determine_winner
from bot.utils.bracket_generator import generate_playoff_bracket, generate_group_stage_image
from bot.config import ADMIN_IDS

router = Router()


def get_main_kb(has_reg: bool):
    return user_main_kb(has_registration=has_reg)


@router.message(Command("start"))
async def user_start(message: Message, state: FSMContext):
    from bot.config import ADMIN_IDS
    if message.from_user.id in ADMIN_IDS:
        return

    tournament = await get_active_tournament()
    if not tournament:
        await message.answer(
            "👋 <b>eFootball Turnir Botiga xush kelibsiz!</b>\n\n"
            "Hozircha faol turnir mavjud emas. Keyinroq tekshiring.",
            parse_mode="HTML",
        )
        return

    participant = await get_participant_by_user(tournament["id"], message.from_user.id)
    has_reg = participant is not None and participant["payment_status"] in ("approved", "free")

    payment_info = f"To'lovli ({tournament['price']:,.0f} so'm)" if tournament["is_paid"] else "Bepul"
    reg_status = "Siz ro'yxatdan o'tgansiz! ✅" if has_reg else "Ro'yxatdan o'tish uchun tugmani bosing."
    await message.answer(
        f"👋 <b>eFootball Turnir Botiga xush kelibsiz!</b>\n\n"
        f"📛 Turnir: <b>{tournament['name']}</b>\n"
        f"👥 Max ishtirokchilar: <b>{tournament['max_participants']}</b>\n"
        f"💳 To'lov: <b>{payment_info}</b>\n\n"
        f"{reg_status}",
        parse_mode="HTML",
        reply_markup=get_main_kb(has_reg),
    )


@router.message(F.text == "ℹ️ Turnir haqida")
async def tournament_info(message: Message):
    tournament = await get_active_tournament()
    if not tournament:
        await message.answer("⚠️ Faol turnir topilmadi.")
        return
    status_map = {
        "draft": "📝 Hali boshlanmagan",
        "registration": "🟢 Ro'yxatdan o'tish ochiq",
        "started": "⚽ Davom etmoqda",
        "finished": "🏁 Tugagan",
    }
    fmt_map = {"playoff": "Play-off", "group_playoff": "Guruh + Play-off"}
    approved = await count_approved_participants(tournament["id"])
    pay_txt = f"To'lovli — {tournament['price']:,.0f} so'm" if tournament["is_paid"] else "Bepul"
    text = (
        f"🏆 <b>{tournament['name']}</b>\n\n"
        f"📊 Holat: {status_map.get(tournament['status'], '?')}\n"
        f"🗂 Format: {fmt_map.get(tournament['format'], '?')}\n"
        f"👥 Ishtirokchilar: {approved}/{tournament['max_participants']}\n"
        f"💳 To'lov: {pay_txt}\n"
    )
    if tournament["is_paid"] and tournament["card_number"]:
        text += f"🏦 Karta: <code>{tournament['card_number']}</code>\n"
    await message.answer(text, parse_mode="HTML")


@router.message(F.text == "📝 Ro'yxatdan o'tish")
async def start_registration(message: Message, state: FSMContext):
    tournament = await get_active_tournament()
    if not tournament:
        await message.answer("⚠️ Hozirda faol turnir yo'q.")
        return
    if tournament["status"] != "registration":
        await message.answer("⚠️ Ro'yxatdan o'tish hali ochilmagan yoki yopilgan.")
        return
    existing = await get_participant_by_user(tournament["id"], message.from_user.id)
    if existing:
        st = existing["payment_status"]
        if st in ("approved", "free"):
            await message.answer("✅ Siz allaqachon ro'yxatdan o'tgansiz!")
        elif st == "pending":
            await message.answer("⏳ To'lovingiz tasdiqlanishi kutilmoqda.")
        elif st == "rejected":
            await message.answer("❌ To'lovingiz rad etilgan. Qaytadan yuboring.")
        return
    approved = await count_approved_participants(tournament["id"])
    if approved >= tournament["max_participants"]:
        await message.answer("⚠️ Turnir to'ldi. Ro'yxatdan o'tib bo'lmaydi.")
        return

    await state.set_state(PlayerRegistration.game_id)
    await state.update_data(tournament_id=tournament["id"])
    await message.answer(
        "📝 <b>Ro'yxatdan o'tish</b>\n\n"
        "Birinchi, <b>eFootball Game ID</b>ingizni kiriting:\n"
        "<i>(Bu raqamni eFootball o'yinida profil bo'limidan topasiz)</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb(),
    )


@router.message(PlayerRegistration.game_id, F.text == "❌ Bekor qilish")
@router.message(PlayerRegistration.team_name, F.text == "❌ Bekor qilish")
@router.message(PlayerRegistration.phone, F.text == "❌ Bekor qilish")
@router.message(PlayerRegistration.payment_screenshot, F.text == "❌ Bekor qilish")
async def cancel_registration(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Ro'yxatdan o'tish bekor qilindi.", reply_markup=user_main_kb())


@router.message(PlayerRegistration.game_id)
async def game_id_received(message: Message, state: FSMContext):
    await state.update_data(game_id=message.text.strip())
    await state.set_state(PlayerRegistration.team_name)
    await message.answer(
        "⚽ Jamoangiz nomini kiriting:\n<i>(Masalan: Real Madrid, Manchester City)</i>",
        parse_mode="HTML",
    )


@router.message(PlayerRegistration.team_name)
async def team_name_received(message: Message, state: FSMContext):
    await state.update_data(team_name=message.text.strip())
    await state.set_state(PlayerRegistration.phone)
    await message.answer(
        "📞 Telefon raqamingizni kiriting:\n<i>(Masalan: +998901234567)</i>",
        parse_mode="HTML",
    )


@router.message(PlayerRegistration.phone)
async def phone_received(message: Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    data = await state.get_data()
    tournament = await get_active_tournament()

    if tournament and tournament["is_paid"]:
        await state.set_state(PlayerRegistration.payment_screenshot)
        await message.answer(
            f"💳 <b>To'lov</b>\n\n"
            f"Turnir narxi: <b>{tournament['price']:,.0f} so'm</b>\n"
            f"Karta raqami: <code>{tournament['card_number']}</code>\n\n"
            f"Shu kartaga to'lov qilib, <b>to'lov skrinshoti</b>ni yuboring:",
            parse_mode="HTML",
        )
    else:
        pid = await add_participant(
            tournament_id=data["tournament_id"],
            user_id=message.from_user.id,
            username=message.from_user.username or "",
            game_id=data["game_id"],
            team_name=data["team_name"],
            phone=data["phone"],
            payment_status="free",
        )
        await state.clear()
        await message.answer(
            f"✅ <b>Ro'yxatdan o'tdingiz!</b>\n\n"
            f"🎮 Game ID: <code>{data['game_id']}</code>\n"
            f"⚽ Jamoa: <b>{data['team_name']}</b>\n"
            f"📞 Tel: {data['phone']}\n\n"
            f"Turnir boshlanishini kuting!",
            parse_mode="HTML",
            reply_markup=user_main_kb(has_registration=True),
        )


@router.message(PlayerRegistration.payment_screenshot, F.photo)
async def payment_screenshot_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    photo: PhotoSize = message.photo[-1]

    pid = await add_participant(
        tournament_id=data["tournament_id"],
        user_id=message.from_user.id,
        username=message.from_user.username or "",
        game_id=data["game_id"],
        team_name=data["team_name"],
        phone=data["phone"],
        payment_status="pending",
    )
    await update_payment_status(pid, "pending", photo.file_id)
    await state.clear()

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(
                chat_id=admin_id,
                photo=photo.file_id,
                caption=(
                    f"💳 <b>Yangi to'lov skrinshoti</b>\n\n"
                    f"👤 Foydalanuvchi: @{message.from_user.username or 'noma_lum'} (ID: {message.from_user.id})\n"
                    f"🎮 Game ID: <code>{data['game_id']}</code>\n"
                    f"⚽ Jamoa: <b>{data['team_name']}</b>\n"
                    f"📞 Tel: {data['phone']}\n"
                    f"🆔 Participant ID: {pid}"
                ),
                parse_mode="HTML",
                reply_markup=payment_approval_kb(pid),
            )
        except Exception:
            pass

    await message.answer(
        "✅ <b>To'lov skrinshoti yuborildi!</b>\n\n"
        "Admin tasdiqlashini kuting. Tez orada javob beriladi.",
        parse_mode="HTML",
        reply_markup=user_main_kb(has_registration=False),
    )


@router.message(PlayerRegistration.payment_screenshot)
async def payment_screenshot_wrong(message: Message):
    await message.answer("⚠️ Iltimos, <b>rasm</b> (skrinshot) yuboring.", parse_mode="HTML")


@router.message(F.text == "📊 Mening o'yinlarim")
async def my_matches(message: Message):
    tournament = await get_active_tournament()
    if not tournament:
        await message.answer("⚠️ Faol turnir yo'q.")
        return
    participant = await get_participant_by_user(tournament["id"], message.from_user.id)
    if not participant:
        await message.answer("⚠️ Siz bu turnirda ro'yxatdan o'tmagansiz.")
        return

    matches = await get_pending_matches_for_participant(tournament["id"], participant["id"])
    if not matches:
        await message.answer("⏳ Hozircha sizga tayinlangan o'yin yo'q.")
        return

    text = "🎮 <b>Sizning o'yinlaringiz:</b>\n\n"
    for m in matches:
        opp_id = m["participant2_id"] if m["participant1_id"] == participant["id"] else m["participant1_id"]
        opp = await get_participant(opp_id) if opp_id else None
        opp_name = opp["team_name"] if opp else "BYE"
        text += (
            f"⚔️ O'yin #{m['id']}\n"
            f"Raqib: <b>{opp_name}</b>\n"
            f"Bosqich: {m['stage'].upper()} - Tur {m['round']}\n\n"
        )
    await message.answer(text, parse_mode="HTML", reply_markup=user_main_kb(has_registration=True))


@router.message(F.text == "📤 Natija yuborish")
async def start_result_submission(message: Message, state: FSMContext):
    tournament = await get_active_tournament()
    if not tournament:
        await message.answer("⚠️ Faol turnir yo'q.")
        return
    if tournament["status"] != "started":
        await message.answer("⚠️ Turnir hali boshlanmagan.")
        return
    participant = await get_participant_by_user(tournament["id"], message.from_user.id)
    if not participant:
        await message.answer("⚠️ Siz bu turnirda ishtirok etmaysiz.")
        return

    matches = await get_pending_matches_for_participant(tournament["id"], participant["id"])
    if not matches:
        await message.answer("⏳ Sizga tayinlangan o'yin yo'q.")
        return

    await state.set_state(ResultSubmission.select_match)
    await state.update_data(
        tournament_id=tournament["id"],
        participant_id=participant["id"],
    )
    if len(matches) == 1:
        m = matches[0]
        await state.update_data(match_id=m["id"])
        await state.set_state(ResultSubmission.score)
        await message.answer(
            f"📤 <b>Natija yuborish</b>\n\n"
            f"O'yin #{m['id']} natijasini kiriting.\n"
            f"Format: <code>3-1</code> (siz-raqib)\n"
            f"<i>Sizning natijangiz avval, raqibnikini keyin yozing.</i>",
            parse_mode="HTML",
            reply_markup=cancel_kb(),
        )
    else:
        await message.answer(
            "🎮 Qaysi o'yin natijasini yubormoqchisiz?",
            reply_markup=match_select_kb([dict(m) for m in matches]),
        )


@router.callback_query(F.data.startswith("select_match:"), ResultSubmission.select_match)
async def select_match_callback(callback: CallbackQuery, state: FSMContext):
    match_id = int(callback.data.split(":")[1])
    await state.update_data(match_id=match_id)
    await state.set_state(ResultSubmission.score)
    await callback.message.edit_text(
        f"📤 <b>O'yin #{match_id} natijasi</b>\n\n"
        f"Hisobni kiriting.\n"
        f"Format: <code>3-1</code> (siz-raqib)",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ResultSubmission.score, F.text == "❌ Bekor qilish")
@router.message(ResultSubmission.screenshot, F.text == "❌ Bekor qilish")
async def cancel_result(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Natija yuborish bekor qilindi.", reply_markup=user_main_kb(has_registration=True))


@router.message(ResultSubmission.score)
async def score_received(message: Message, state: FSMContext):
    txt = message.text.strip()
    try:
        parts = txt.replace(" ", "").split("-")
        if len(parts) != 2:
            raise ValueError
        s1, s2 = int(parts[0]), int(parts[1])
        if s1 < 0 or s2 < 0 or s1 > 30 or s2 > 30:
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(
            "⚠️ Noto'g'ri format! Misol: <code>3-1</code>",
            parse_mode="HTML",
        )
        return
    await state.update_data(score1=s1, score2=s2)
    await state.set_state(ResultSubmission.screenshot)
    await message.answer(
        f"📸 Endi o'yin natijasini ko'rsatuvchi <b>skrinshot</b> yuboring:",
        parse_mode="HTML",
    )


@router.message(ResultSubmission.screenshot, F.photo)
async def result_screenshot_received(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    photo: PhotoSize = message.photo[-1]
    match_id = data["match_id"]
    score1 = data["score1"]
    score2 = data["score2"]
    participant_id = data["participant_id"]
    tournament_id = data["tournament_id"]

    await submit_match_result(
        match_id=match_id,
        submitted_by=participant_id,
        score1=score1,
        score2=score2,
        screenshot_file_id=photo.file_id,
    )
    await state.clear()

    match = await get_match(match_id)
    other_participant_id = (
        match["participant2_id"] if match["participant1_id"] == participant_id else match["participant1_id"]
    )
    other = await get_participant(other_participant_id) if other_participant_id else None

    await message.answer(
        f"✅ <b>Natija yuborildi!</b>\n\n"
        f"📊 Hisob: <b>{score1} - {score2}</b>\n\n"
        f"Raqibingiz tasdiqlashi kutilmoqda.",
        parse_mode="HTML",
        reply_markup=user_main_kb(has_registration=True),
    )

    if other:
        try:
            sender = await get_participant(participant_id)
            sender_name = sender["team_name"] if sender else "Raqib"
            await bot.send_photo(
                chat_id=other["user_id"],
                photo=photo.file_id,
                caption=(
                    f"⚠️ <b>Natija tasdiqlanishi kerak</b>\n\n"
                    f"<b>{sender_name}</b> o'yin natijasini yubordi:\n"
                    f"📊 Hisob: <b>{score1} - {score2}</b>\n\n"
                    f"Bu to'g'rimi?"
                ),
                parse_mode="HTML",
                reply_markup=result_confirm_kb(match_id),
            )
        except Exception:
            pass


@router.message(ResultSubmission.screenshot)
async def result_screenshot_wrong(message: Message):
    await message.answer("⚠️ Iltimos, skrinshot (rasm) yuboring.", parse_mode="HTML")


@router.callback_query(F.data.startswith("result_ok:"))
async def result_confirmed(callback: CallbackQuery, bot: Bot):
    match_id = int(callback.data.split(":")[1])
    match = await get_match(match_id)
    if not match or match["status"] != "waiting_confirm":
        await callback.answer("Bu o'yin allaqachon tasdiqlangan yoki topilmadi.")
        return

    winner = await determine_winner(match)
    if winner:
        await confirm_match_result(match_id, winner)

        winner_participant = await get_participant(winner)
        loser_id = (
            match["participant2_id"] if match["participant1_id"] == winner else match["participant1_id"]
        )
        loser_participant = await get_participant(loser_id) if loser_id else None

        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n✅ <b>Tasdiqlandi!</b>",
            parse_mode="HTML",
        )
        await callback.answer("✅ Natija tasdiqlandi!")

        try:
            await bot.send_message(
                match["result_submitted_by"] and (await get_participant(match["result_submitted_by"]) or {}).get("user_id", 0) or winner_participant["user_id"] if winner_participant else 0,
                f"✅ <b>Natijangiz tasdiqlandi!</b>\n📊 Hisob: {match['score1']} - {match['score2']}",
                parse_mode="HTML",
            )
        except Exception:
            pass

        tournament = await get_active_tournament()
        if tournament and tournament["format"] == "playoff":
            try:
                from bot.db.participants import get_tournament_participants
                participants = await get_tournament_participants(tournament["id"], approved_only=True)
                matches = await get_tournament_matches(tournament["id"])
                img_bytes = generate_playoff_bracket(
                    participants=[dict(p) for p in participants],
                    tournament_name=tournament["name"],
                    matches=[dict(m) for m in matches],
                )
                from aiogram.types import BufferedInputFile
                photo = BufferedInputFile(img_bytes, filename="bracket.png")
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_photo(
                            admin_id,
                            photo=photo,
                            caption=f"🔄 <b>Yangilangan setka</b> — {tournament['name']}",
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
            except Exception:
                pass
    else:
        await callback.answer("Natija aniqlanmadi (durang).")


@router.callback_query(F.data.startswith("result_wrong:"))
async def result_disputed(callback: CallbackQuery, bot: Bot):
    match_id = int(callback.data.split(":")[1])
    await dispute_match(match_id)
    await callback.message.edit_caption(
        caption=callback.message.caption + "\n\n❌ <b>Natija rad etildi!</b> Admin hal qiladi.",
        parse_mode="HTML",
    )
    await callback.answer("❌ Natija rad etildi!")

    match = await get_match(match_id)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"⚠️ <b>Nizo!</b> O'yin #{match_id} bo'yicha kelishmovchilik.\n"
                f"Hisob: {match['score1']} - {match['score2']}\n"
                f"Qaror qabul qiling:",
                parse_mode="HTML",
                reply_markup=dispute_kb(match_id),
            )
        except Exception:
            pass
