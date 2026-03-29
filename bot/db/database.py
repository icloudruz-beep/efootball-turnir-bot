import aiosqlite
import os
from bot.config import DB_PATH


def get_db():
    """aiosqlite context manager qaytaradi. async with get_db() as db: ko'rinishida ishlatiladi."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return aiosqlite.connect(DB_PATH)


async def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        await db.execute("PRAGMA journal_mode=WAL")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                max_participants INTEGER NOT NULL,
                format TEXT NOT NULL CHECK(format IN ('playoff', 'group_playoff')),
                is_paid INTEGER NOT NULL DEFAULT 0,
                price REAL DEFAULT 0,
                card_number TEXT DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft'
                    CHECK(status IN ('draft','registration','started','finished')),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
                user_id INTEGER NOT NULL,
                username TEXT DEFAULT '',
                game_id TEXT NOT NULL,
                team_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                payment_status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(payment_status IN ('pending','approved','rejected','free')),
                payment_screenshot_file_id TEXT DEFAULT '',
                group_name TEXT DEFAULT '',
                seed INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tournament_id, user_id)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL REFERENCES tournaments(id),
                stage TEXT NOT NULL,
                round INTEGER NOT NULL DEFAULT 0,
                group_name TEXT DEFAULT '',
                participant1_id INTEGER REFERENCES participants(id),
                participant2_id INTEGER REFERENCES participants(id),
                score1 INTEGER DEFAULT NULL,
                score2 INTEGER DEFAULT NULL,
                winner_id INTEGER DEFAULT NULL REFERENCES participants(id),
                result_screenshot_file_id TEXT DEFAULT '',
                result_submitted_by INTEGER DEFAULT NULL,
                result_confirmed INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending','waiting_confirm','confirmed','disputed')),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
