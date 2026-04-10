"""
מנהל מסד הנתונים - SQLite אסינכרוני
"""

import aiosqlite
import logging
from typing import Optional, List, Dict
from config import DATABASE_PATH, ADMIN_IDS
from database.models import User

logger = logging.getLogger(__name__)

DB_PATH = DATABASE_PATH


async def init_db() -> None:
    """יצירת טבלאות מסד הנתונים אם לא קיימות"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id         INTEGER PRIMARY KEY,
                username        TEXT,
                full_name       TEXT NOT NULL,
                is_approved     INTEGER NOT NULL DEFAULT 0,
                is_banned       INTEGER NOT NULL DEFAULT 0,
                is_admin        INTEGER NOT NULL DEFAULT 0,
                credit_text     TEXT,
                color           TEXT NOT NULL DEFAULT '#FFFFFF',
                font            TEXT NOT NULL DEFAULT 'Arial',
                position        TEXT NOT NULL DEFAULT 'bottom',
                frequency       INTEGER NOT NULL DEFAULT 10,
                duration_start  INTEGER NOT NULL DEFAULT 5,
                duration_middle INTEGER NOT NULL DEFAULT 5,
                duration_end    INTEGER NOT NULL DEFAULT 5,
                setup_done      INTEGER NOT NULL DEFAULT 0
            )
        """)
        
        # טבלת סטטיסטיקות
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)
        # אתחול מונה קבצים אם לא קיים
        await db.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('processed_files', 0)")
        
        await db.commit()

    # הוספת מנהלים ראשיים מה-.env אם לא קיימים
    # תיקון: לא לדרוס הגדרות קיימות של מנהלים בעת הפעלה מחדש
    for admin_id in ADMIN_IDS:
        existing_admin = await get_user(admin_id)
        if existing_admin:
            # אם המנהל קיים, רק לוודא שיש לו הרשאות
            if not existing_admin.is_admin or not existing_admin.is_approved:
                await update_user_settings(admin_id, is_admin=True, is_approved=True)
        else:
            # אם המנהל לא קיים, ליצור אותו עם ברירות מחדל
            await upsert_user(User(
                user_id=admin_id,
                username=None,
                full_name="Super Admin",
                is_approved=True,
                is_admin=True,
                setup_done=True,
            ))

    logger.info("✅ מסד הנתונים מוכן")


async def get_user(user_id: int) -> Optional[User]:
    """קבלת משתמש לפי מזהה"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return _row_to_user(row)


async def upsert_user(user: User) -> None:
    """הוספה או עדכון משתמש"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (
                user_id, username, full_name, is_approved, is_banned, is_admin,
                credit_text, color, font, position, frequency,
                duration_start, duration_middle, duration_end, setup_done
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET
                username        = excluded.username,
                full_name       = excluded.full_name,
                is_approved     = excluded.is_approved,
                is_banned       = excluded.is_banned,
                is_admin        = excluded.is_admin,
                credit_text     = excluded.credit_text,
                color           = excluded.color,
                font            = excluded.font,
                position        = excluded.position,
                frequency       = excluded.frequency,
                duration_start  = excluded.duration_start,
                duration_middle = excluded.duration_middle,
                duration_end    = excluded.duration_end,
                setup_done      = excluded.setup_done
        """, (
            user.user_id, user.username, user.full_name,
            int(user.is_approved), int(user.is_banned), int(user.is_admin),
            user.credit_text, user.color, user.font, user.position,
            user.frequency, user.duration_start, user.duration_middle,
            user.duration_end, int(user.setup_done),
        ))
        await db.commit()


async def update_user_settings(user_id: int, **kwargs) -> None:
    """עדכון שדות ספציפיים למשתמש"""
    if not kwargs:
        return
    allowed = {
        "credit_text", "color", "font", "position", "frequency",
        "duration_start", "duration_middle", "duration_end",
        "is_approved", "is_banned", "is_admin", "setup_done",
        "username", "full_name",
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE users SET {set_clause} WHERE user_id = ?", values
        )
        await db.commit()


async def get_all_approved_users() -> List[User]:
    """קבלת כל המשתמשים המאושרים"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE is_approved = 1 AND is_banned = 0"
        ) as cursor:
            rows = await cursor.fetchall()
            return [_row_to_user(r) for r in rows]


async def get_all_users() -> List[User]:
    """קבלת כל המשתמשים"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            rows = await cursor.fetchall()
            return [_row_to_user(r) for r in rows]


async def is_admin(user_id: int) -> bool:
    """בדיקה האם המשתמש הוא מנהל"""
    if user_id in ADMIN_IDS:
        return True
    user = await get_user(user_id)
    return user is not None and user.is_admin


async def is_approved(user_id: int) -> bool:
    """בדיקה האם המשתמש מאושר"""
    if user_id in ADMIN_IDS:
        return True
    user = await get_user(user_id)
    return user is not None and user.is_approved and not user.is_banned


async def increment_processed_files() -> None:
    """הגדלת מונה הקבצים המעובדים"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE stats SET value = value + 1 WHERE key = 'processed_files'")
        await db.commit()


async def get_stats() -> Dict[str, int]:
    """קבלת סטטיסטיקות"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM stats") as cursor:
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}


def _row_to_user(row: aiosqlite.Row) -> User:
    return User(
        user_id=row["user_id"],
        username=row["username"],
        full_name=row["full_name"],
        is_approved=bool(row["is_approved"]),
        is_banned=bool(row["is_banned"]),
        is_admin=bool(row["is_admin"]),
        credit_text=row["credit_text"],
        color=row["color"],
        font=row["font"],
        position=row["position"],
        frequency=row["frequency"],
        duration_start=row["duration_start"],
        duration_middle=row["duration_middle"],
        duration_end=row["duration_end"],
        setup_done=bool(row["setup_done"]),
    )
