"""
Shikoyatlar (Complaints) bilan ishlash uchun DB funksiyalari.
"""
from bot.db.database import get_db


async def add_complaint(
    user_id: int,
    username: str,
    full_name: str,
    text: str,
    screenshot_file_id: str = "",
) -> int:
    """Yangi shikoyat qo'shadi. Qaytaradi: complaint ID."""
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO complaints (user_id, username, full_name, text, screenshot_file_id, status)
            VALUES (?, ?, ?, ?, ?, 'unread')
            """,
            (user_id, username, full_name, text, screenshot_file_id),
        )
        await db.commit()
        return cursor.lastrowid


async def get_unread_complaints() -> list:
    """Barcha o'qilmagan shikoyatlarni qaytaradi."""
    async with get_db() as db:
        db.row_factory = __import__("aiosqlite").Row
        cursor = await db.execute(
            "SELECT * FROM complaints WHERE status = 'unread' ORDER BY created_at ASC"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_complaint(complaint_id: int) -> dict | None:
    """ID bo'yicha bitta shikoyatni qaytaradi."""
    async with get_db() as db:
        db.row_factory = __import__("aiosqlite").Row
        cursor = await db.execute(
            "SELECT * FROM complaints WHERE id = ?", (complaint_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def mark_complaint_read(complaint_id: int) -> None:
    """Shikoyatni 'read' deb belgilaydi."""
    async with get_db() as db:
        await db.execute(
            "UPDATE complaints SET status = 'read' WHERE id = ?", (complaint_id,)
        )
        await db.commit()


async def reply_complaint(complaint_id: int, reply_text: str) -> None:
    """Shikoyatga javob yozadi va 'replied' deb belgilaydi."""
    async with get_db() as db:
        await db.execute(
            "UPDATE complaints SET status = 'replied', admin_reply = ? WHERE id = ?",
            (reply_text, complaint_id),
        )
        await db.commit()


async def ban_complaint_user(complaint_id: int) -> None:
    """Shikoyat statusini 'banned' qiladi."""
    async with get_db() as db:
        await db.execute(
            "UPDATE complaints SET status = 'banned' WHERE id = ?", (complaint_id,)
        )
        await db.commit()


async def ban_user(user_id: int, reason: str = "") -> None:
    """Foydalanuvchini global ban ro'yxatiga qo'shadi."""
    async with get_db() as db:
        await db.execute(
            "INSERT OR REPLACE INTO banned_users (user_id, reason) VALUES (?, ?)",
            (user_id, reason),
        )
        await db.commit()


async def is_user_banned(user_id: int) -> bool:
    """Foydalanuvchi ban ro'yxatida ekanligini tekshiradi."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row is not None


async def get_unread_count() -> int:
    """O'qilmagan shikoyatlar sonini qaytaradi."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM complaints WHERE status = 'unread'"
        )
        row = await cursor.fetchone()
        return row[0] if row else 0


async def update_tournament_rules(tournament_id: int, rules: str, announcement: str) -> None:
    """Turnir qoidalari va e'lonini yangilaydi."""
    async with get_db() as db:
        await db.execute(
            "UPDATE tournaments SET rules = ?, announcement = ? WHERE id = ?",
            (rules, announcement, tournament_id),
        )
        await db.commit()
