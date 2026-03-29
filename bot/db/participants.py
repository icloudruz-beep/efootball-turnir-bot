import aiosqlite
from typing import Optional
from bot.db.database import get_db


async def add_participant(
    tournament_id: int,
    user_id: int,
    username: str,
    game_id: str,
    team_name: str,
    phone: str,
    payment_status: str = "pending",
) -> int:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT OR REPLACE INTO participants
               (tournament_id, user_id, username, game_id, team_name, phone, payment_status)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tournament_id, user_id, username, game_id, team_name, phone, payment_status),
        )
        await db.commit()
        return cursor.lastrowid


async def get_participant_by_user(tournament_id: int, user_id: int) -> Optional[aiosqlite.Row]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM participants WHERE tournament_id = ? AND user_id = ?",
            (tournament_id, user_id),
        )
        return await cursor.fetchone()


async def get_participant(participant_id: int) -> Optional[aiosqlite.Row]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM participants WHERE id = ?", (participant_id,)
        )
        return await cursor.fetchone()


async def get_tournament_participants(tournament_id: int, approved_only: bool = False) -> list:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if approved_only:
            cursor = await db.execute(
                """SELECT * FROM participants
                   WHERE tournament_id = ?
                   AND payment_status IN ('approved','free')
                   ORDER BY seed, id""",
                (tournament_id,),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM participants WHERE tournament_id = ? ORDER BY id",
                (tournament_id,),
            )
        return await cursor.fetchall()


async def update_payment_status(participant_id: int, status: str, file_id: str = ""):
    async with get_db() as db:
        if file_id:
            await db.execute(
                """UPDATE participants
                   SET payment_status = ?, payment_screenshot_file_id = ?
                   WHERE id = ?""",
                (status, file_id, participant_id),
            )
        else:
            await db.execute(
                "UPDATE participants SET payment_status = ? WHERE id = ?",
                (status, participant_id),
            )
        await db.commit()


async def set_participant_group(participant_id: int, group_name: str, seed: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE participants SET group_name = ?, seed = ? WHERE id = ?",
            (group_name, seed, participant_id),
        )
        await db.commit()


async def count_approved_participants(tournament_id: int) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT COUNT(*) FROM participants
               WHERE tournament_id = ? AND payment_status IN ('approved','free')""",
            (tournament_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0
