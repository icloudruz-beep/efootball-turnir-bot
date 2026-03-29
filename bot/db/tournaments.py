import aiosqlite
from typing import Optional
from bot.db.database import get_db


async def create_tournament(
    name: str,
    max_participants: int,
    format_: str,
    is_paid: bool,
    price: float = 0.0,
    card_number: str = "",
) -> int:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """INSERT INTO tournaments
               (name, max_participants, format, is_paid, price, card_number, status)
               VALUES (?, ?, ?, ?, ?, ?, 'draft')""",
            (name, max_participants, format_, int(is_paid), price, card_number),
        )
        await db.commit()
        return cursor.lastrowid


async def get_tournament(tournament_id: int) -> Optional[aiosqlite.Row]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tournaments WHERE id = ?", (tournament_id,)
        )
        return await cursor.fetchone()


async def get_active_tournament() -> Optional[aiosqlite.Row]:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tournaments WHERE status IN ('registration','started') ORDER BY id DESC LIMIT 1"
        )
        return await cursor.fetchone()


async def get_all_tournaments() -> list:
    async with get_db() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tournaments ORDER BY id DESC"
        )
        return await cursor.fetchall()


async def update_tournament_status(tournament_id: int, status: str):
    async with get_db() as db:
        await db.execute(
            "UPDATE tournaments SET status = ? WHERE id = ?",
            (status, tournament_id),
        )
        await db.commit()
