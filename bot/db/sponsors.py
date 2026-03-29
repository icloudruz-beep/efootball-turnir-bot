"""
Homiy kanallar (Sponsors) bilan ishlash uchun DB funksiyalari.
"""
from bot.db.database import get_db


async def add_sponsor(channel_id: int, channel_name: str, channel_link: str) -> int:
    """Yangi homiy kanal qo'shadi. Qaytaradi: sponsor ID."""
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT OR REPLACE INTO sponsors (channel_id, channel_name, channel_link)
               VALUES (?, ?, ?)""",
            (channel_id, channel_name, channel_link),
        )
        await db.commit()
        return cursor.lastrowid


async def remove_sponsor(sponsor_id: int) -> bool:
    """ID bo'yicha homiy kanalni o'chiradi."""
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM sponsors WHERE id = ?", (sponsor_id,)
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_all_sponsors() -> list:
    """Barcha homiy kanallar ro'yxatini qaytaradi."""
    async with get_db() as db:
        db.row_factory = __import__("aiosqlite").Row
        cursor = await db.execute(
            "SELECT * FROM sponsors ORDER BY id"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_sponsor(sponsor_id: int) -> dict | None:
    """ID bo'yicha bitta homiyni qaytaradi."""
    async with get_db() as db:
        db.row_factory = __import__("aiosqlite").Row
        cursor = await db.execute(
            "SELECT * FROM sponsors WHERE id = ?", (sponsor_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
