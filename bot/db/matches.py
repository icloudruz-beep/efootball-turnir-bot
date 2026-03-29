import aiosqlite
from typing import Optional
from bot.db.database import get_db


async def create_match(
    tournament_id: int,
    stage: str,
    round_: int,
    participant1_id: int,
    participant2_id: Optional[int],
    group_name: str = "",
) -> int:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO matches
               (tournament_id, stage, round, group_name, participant1_id, participant2_id, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (tournament_id, stage, round_, group_name, participant1_id, participant2_id),
        )
        await db.commit()
        return cursor.lastrowid


async def get_match(match_id: int) -> Optional[aiosqlite.Row]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
        return await cursor.fetchone()


async def get_tournament_matches(tournament_id: int, stage: str = None) -> list:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        if stage:
            cursor = await db.execute(
                "SELECT * FROM matches WHERE tournament_id = ? AND stage = ? ORDER BY round, id",
                (tournament_id, stage),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM matches WHERE tournament_id = ? ORDER BY round, id",
                (tournament_id,),
            )
        return await cursor.fetchall()


async def get_participant_matches(tournament_id: int, participant_id: int) -> list:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM matches WHERE tournament_id = ?
               AND (participant1_id = ? OR participant2_id = ?)
               ORDER BY round, id""",
            (tournament_id, participant_id, participant_id),
        )
        return await cursor.fetchall()


async def submit_match_result(
    match_id: int,
    submitted_by: int,
    score1: int,
    score2: int,
    screenshot_file_id: str,
):
    async with get_db() as db:
        await db.execute(
            """UPDATE matches SET
               score1 = ?, score2 = ?,
               result_screenshot_file_id = ?,
               result_submitted_by = ?,
               status = 'waiting_confirm'
               WHERE id = ?""",
            (score1, score2, screenshot_file_id, submitted_by, match_id),
        )
        await db.commit()


async def confirm_match_result(match_id: int, winner_id: int):
    async with get_db() as db:
        await db.execute(
            """UPDATE matches SET
               status = 'confirmed', result_confirmed = 1, winner_id = ?
               WHERE id = ?""",
            (winner_id, match_id),
        )
        await db.commit()


async def dispute_match(match_id: int):
    async with get_db() as db:
        await db.execute(
            "UPDATE matches SET status = 'disputed' WHERE id = ?",
            (match_id,),
        )
        await db.commit()


async def get_pending_matches_for_participant(tournament_id: int, participant_id: int) -> list:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM matches WHERE tournament_id = ?
               AND status = 'pending'
               AND (participant1_id = ? OR participant2_id = ?)""",
            (tournament_id, participant_id, participant_id),
        )
        return await cursor.fetchall()
