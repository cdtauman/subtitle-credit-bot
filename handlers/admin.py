"""
מטפל פקודות ניהול
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from config import ADMIN_IDS
from database.db_manager import (
    get_user,
    update_user_settings,
    get_all_approved_users,
    get_all_users,
    is_admin,
)

logger = logging.getLogger(__name__)


async def _check_admin(update: Update) -> bool:
    """בדיקת הרשאות מנהל"""
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS:
        return True
    if await is_admin(user_id):
        return True
    await update.message.reply_text("❌ פקודה זו מיועדת למנהלים בלבד.")
    return False


async def ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /ban [user_id] - חסימת משתמש
    """
    if not await _check_admin(update):
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "📖 שימוש: `/ban [user_id]`\n"
            "לדוגמה: `/ban 123456789`",
            parse_mode="Markdown",
        )
        return

    target_id = int(args[0])
    target = await get_user(target_id)
    if target is None:
        await update.message.reply_text("❌ משתמש לא נמצא במסד הנתונים.")
        return

    if target_id in ADMIN_IDS:
        await update.message.reply_text("❌ לא ניתן לחסום מנהל ראשי.")
        return

    await update_user_settings(target_id, is_banned=True, is_approved=False)
    await update.message.reply_text(
        f"🚫 *המשתמש חסום בהצלחה.*\n"
        f"🆔 מזהה: `{target_id}`\n"
        f"👤 שם: {target.full_name}",
        parse_mode="Markdown",
    )
    logger.info(f"Admin {update.effective_user.id} banned user {target_id}")

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="🚫 הגישה שלך לבוט חסומה על ידי מנהל."
        )
    except Exception:
        pass


async def promote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /promote [user_id] - קידום משתמש למנהל
    רק מנהלים ראשיים יכולים לקדם
    """
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("❌ רק מנהלים ראשיים יכולים לקדם משתמשים.")
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text(
            "📖 שימוש: `/promote [user_id]`\n"
            "לדוגמה: `/promote 123456789`",
            parse_mode="Markdown",
        )
        return

    target_id = int(args[0])
    target = await get_user(target_id)
    if target is None:
        await update.message.reply_text("❌ משתמש לא נמצא.")
        return

    await update_user_settings(target_id, is_admin=True, is_approved=True)
    await update.message.reply_text(
        f"👑 *המשתמש קודם למנהל!*\n"
        f"🆔 מזהה: `{target_id}`\n"
        f"👤 שם: {target.full_name}",
        parse_mode="Markdown",
    )
    logger.info(f"Super admin {update.effective_user.id} promoted user {target_id} to admin")

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="👑 קיבלת הרשאות מנהל בבוט! עכשיו תוכל לאשר משתמשים חדשים."
        )
    except Exception:
        pass


async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /broadcast [הודעה] - שידור הודעה לכל המשתמשים המאושרים
    """
    if not await _check_admin(update):
        return

    if not context.args:
        await update.message.reply_text(
            "📖 שימוש: `/broadcast [הודעה]`\n"
            "לדוגמה: `/broadcast הבוט עודכן לגרסה 2.0!`",
            parse_mode="Markdown",
        )
        return

    message_text = " ".join(context.args)
    users = await get_all_approved_users()

    status = await update.message.reply_text(f"📡 שולח הודעה ל-{len(users)} משתמשים...")

    sent = 0
    failed = 0
    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user.user_id,
                text=f"📢 *הודעה מהמנהל:*\n\n{message_text}",
                parse_mode="Markdown",
            )
            sent += 1
        except Exception as e:
            logger.warning(f"לא ניתן לשלוח ל-{user.user_id}: {e}")
            failed += 1

    await status.edit_text(
        f"✅ *השידור הסתיים.*\n"
        f"📨 נשלח: {sent}\n"
        f"❌ נכשל: {failed}",
        parse_mode="Markdown",
    )


async def list_users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /users - רשימת כל המשתמשים
    """
    if not await _check_admin(update):
        return

    users = await get_all_users()
    if not users:
        await update.message.reply_text("📋 אין משתמשים רשומים עדיין.")
        return

    lines = ["👥 *רשימת משתמשים:*\n"]
    for u in users:
        status_parts = []
        if u.is_admin:
            status_parts.append("👑מנהל")
        if u.is_approved:
            status_parts.append("✅")
        elif u.is_banned:
            status_parts.append("🚫")
        else:
            status_parts.append("⏳")

        status = " ".join(status_parts) if status_parts else "❓"
        name = u.full_name or "לא ידוע"
        username = f"@{u.username}" if u.username else "אין שם משתמש"
        lines.append(f"{status} `{u.user_id}` - {name} ({username})")

    # פיצול הודעה אם ארוכה מדי
    full_text = "\n".join(lines)
    if len(full_text) <= 4000:
        await update.message.reply_text(full_text, parse_mode="Markdown")
    else:
        chunks = []
        current = [lines[0]]
        for line in lines[1:]:
            if sum(len(l) for l in current) + len(line) > 3500:
                chunks.append("\n".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            chunks.append("\n".join(current))
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown")
