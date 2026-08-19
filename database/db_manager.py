"""
מנהל מסד הנתונים - SQLite אסינכרוני
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict

import aiosqlite

from config import DATABASE_PATH, ADMIN_IDS
from database.models import User

logger = logging.getLogger(__name__)
DB_PATH = DATABASE_PATH


async def init_db() -> None:
    """יצירת מסד הנתונים והשלמת schema בלי לדרוס העדפות משתמשים קיימות."""
    Path(DB_PATH).expanduser().parent.mkdir(parents=True, exist_ok=True)

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
                font            TEXT NOT NULL DEFAULT 'Assistant',
                position        TEXT NOT NULL DEFAULT 'bottom',
                frequency       INTEGER NOT NULL DEFAULT 10,
                duration_start  INTEGER NOT NULL DEFAULT 5,
                duration_middle INTEGER NOT NULL DEFAULT 5,
                duration_end    INTEGER NOT NULL DEFAULT 5,
                setup_done      INTEGER NOT NULL DEFAULT 0,
                output_format   TEXT NOT NULL DEFAULT 'srt',
                font_size       INTEGER NOT NULL DEFAULT 23,
                border_style    INTEGER NOT NULL DEFAULT 1,
                outline_color   TEXT NOT NULL DEFAULT '#000000',
                outline_width   INTEGER NOT NULL DEFAULT 2,
                shadow_width    INTEGER NOT NULL DEFAULT 0,
                bg_color        TEXT NOT NULL DEFAULT '#000000',
                is_bold         INTEGER NOT NULL DEFAULT 1
            )
        """)

        cols_to_add = {
            "output_format": "TEXT NOT NULL DEFAULT 'srt'",
            "font_size": "INTEGER NOT NULL DEFAULT 23",
            "border_style": "INTEGER NOT NULL DEFAULT 1",
            "outline_color": "TEXT NOT NULL DEFAULT '#000000'",
            "outline_width": "INTEGER NOT NULL DEFAULT 2",
            "shadow_width": "INTEGER NOT NULL DEFAULT 0",
            "bg_color": "TEXT NOT NULL DEFAULT '#000000'",
            "is_bold": "INTEGER NOT NULL DEFAULT 1",
        }
        async with db.execute("PRAGMA table_info(users)") as cursor:
            existing_columns = {row[1] for row in await cursor.fetchall()}
        for col, definition in cols_to_add.items():
            if col not in existing_columns:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")

        await db.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)
        await db.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('processed_files', 0)")
        await db.commit()

    # אין כאן UPDATE גורף לערכי font/font_size/shadow_width:
    # ברירות מחדל חדשות חלות רק על עמודות/משתמשים חדשים ואינן מוחקות בחירה מפורשת של משתמש קיים.
    for admin_id in ADMIN_IDS:
        existing_admin = await get_user(admin_id)
        if existing_admin:
            if not existing_admin.is_admin or not existing_admin.is_approved or existing_admin.is_banned:
                await update_user_settings(
                    admin_id,
                    is_admin=True,
                    is_approved=True,
                    is_banned=False,
                )
        else:
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
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return None if row is None else _row_to_user(row)


async def upsert_user(user: User) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (
                user_id, username, full_name, is_approved, is_banned, is_admin,
                credit_text, color, font, position, frequency,
                duration_start, duration_middle, duration_end, setup_done, output_format,
                font_size, border_style, outline_color, outline_width, shadow_width, bg_color, is_bold
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                setup_done      = excluded.setup_done,
                output_format   = excluded.output_format,
                font_size       = excluded.font_size,
                border_style    = excluded.border_style,
                outline_color   = excluded.outline_color,
                outline_width   = excluded.outline_width,
                shadow_width    = excluded.shadow_width,
                bg_color        = excluded.bg_color,
                is_bold         = excluded.is_bold
        """, (
            user.user_id, user.username, user.full_name,
            int(user.is_approved), int(user.is_banned), int(user.is_admin),
            user.credit_text, user.color, user.font, user.position,
            user.frequency, user.duration_start, user.duration_middle,
            user.duration_end, int(user.setup_done), user.output_format,
            user.font_size, user.border_style, user.outline_color,
            user.outline_width, user.shadow_width, user.bg_color, user.is_bold,
        ))
        await db.commit()


async def update_user_settings(user_id: int, **kwargs) -> None:
    if not kwargs:
        return
    allowed = {
        "credit_text", "color", "font", "position", "frequency",
        "duration_start", "duration_middle", "duration_end",
        "is_approved", "is_banned", "is_admin", "setup_done",
        "username", "full_name", "output_format",
        "font_size", "border_style", "outline_color",
        "outline_width", "shadow_width", "bg_color", "is_bold",
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [user_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE users SET {set_clause} WHERE user_id = ?", values)
        await db.commit()


async def get_all_approved_users() -> List[User]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE is_approved = 1 AND is_banned = 0") as cursor:
            return [_row_to_user(r) for r in await cursor.fetchall()]


async def get_all_users() -> List[User]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users") as cursor:
            return [_row_to_user(r) for r in await cursor.fetchall()]


async def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    user = await get_user(user_id)
    return user is not None and user.is_admin and not user.is_banned


async def is_approved(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    user = await get_user(user_id)
    return user is not None and user.is_approved and not user.is_banned


async def increment_processed_files(count: int = 1) -> None:
    if count <= 0:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE stats SET value = value + ? WHERE key = 'processed_files'",
            (count,),
        )
        await db.commit()


async def get_stats() -> Dict[str, int]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT key, value FROM stats") as cursor:
            return {row[0]: row[1] for row in await cursor.fetchall()}


def _row_to_user(row: aiosqlite.Row) -> User:
    keys = row.keys()
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
        output_format=row["output_format"] if "output_format" in keys else "srt",
        font_size=row["font_size"] if "font_size" in keys else 23,
        border_style=row["border_style"] if "border_style" in keys else 1,
        outline_color=row["outline_color"] if "outline_color" in keys else "#000000",
        outline_width=row["outline_width"] if "outline_width" in keys else 2,
        shadow_width=row["shadow_width"] if "shadow_width" in keys else 0,
        bg_color=row["bg_color"] if "bg_color" in keys else "#000000",
        is_bold=row["is_bold"] if "is_bold" in keys else 1,
    )
