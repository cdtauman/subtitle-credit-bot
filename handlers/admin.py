"""פקודות ניהול לבוט."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from database.db_manager import (
    get_all_approved_users,
    get_all_users,
    get_user,
    is_admin,
    update_user_settings,
)

logger = logging.getLogger(__name__)


async def _check_admin(update: Update) -> bool:
    user_id = update.effective_user.id
    if user_id in ADMIN_IDS or await is_admin(user_id):
        return True
    await update.message.reply_text("❌ פקודה זו מיועדת למנהלים בלבד.")
    return False


async def ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update):
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("📖 שימוש: /ban [user_id]\nלדוגמה: /ban 123456789")
        return

    actor_id = update.effective_user.id
    target_id = int(args[0])
    target = await get_user(target_id)
    if target is None:
        await update.message.reply_text("❌ משתמש לא נמצא במסד הנתונים.")
        return
    if target_id in ADMIN_IDS:
        await update.message.reply_text("❌ לא ניתן לחסום מנהל ראשי.")
        return
    if target.is_admin and actor_id not in ADMIN_IDS:
        await update.message.reply_text("❌ רק מנהל ראשי יכול לחסום מנהל אחר.")
        return

    await update_user_settings(target_id, is_banned=True, is_approved=False)
    await update.message.reply_text(
        f"🚫 המשתמש חסום בהצלחה.\n🆔 מזהה: {target_id}\n👤 שם: {target.full_name}"
    )
    logger.info("Admin %s banned user %s", actor_id, target_id)

    try:
        await context.bot.send_message(chat_id=target_id, text="🚫 הגישה שלך לבוט חסומה על ידי מנהל.")
    except Exception as exc:
        logger.warning("Could not notify banned user %s: %s", target_id, exc)


async def promote_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    actor_id = update.effective_user.id
    if actor_id not in ADMIN_IDS:
        await update.message.reply_text("❌ רק מנהלים ראשיים יכולים לקדם משתמשים.")
        return

    args = context.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("📖 שימוש: /promote [user_id]\nלדוגמה: /promote 123456789")
        return

    target_id = int(args[0])
    target = await get_user(target_id)
    if target is None:
        await update.message.reply_text("❌ משתמש לא נמצא.")
        return

    # קידום הוא פעולה מפורשת שמעניקה גישה; אין להשאיר את המשתמש במצב banned סותר.
    await update_user_settings(target_id, is_admin=True, is_approved=True, is_banned=False)
    await update.message.reply_text(
        f"👑 המשתמש קודם למנהל!\n🆔 מזהה: {target_id}\n👤 שם: {target.full_name}"
    )
    logger.info("Super admin %s promoted user %s to admin", actor_id, target_id)

    try:
        await context.bot.send_message(
            chat_id=target_id,
            text="👑 קיבלת הרשאות מנהל בבוט! עכשיו תוכל לאשר משתמשים חדשים.",
        )
    except Exception as exc:
        logger.warning("Could not notify promoted user %s: %s", target_id, exc)


async def broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update):
        return
    if not context.args:
        await update.message.reply_text("📖 שימוש: /broadcast [הודעה]")
        return

    message_text = " ".join(context.args)
    users = await get_all_approved_users()
    status = await update.message.reply_text(f"📡 שולל הודעה ל-{len(users)} משתמשים...")

    sent = failed = 0
    for user in users:
        try:
            # טקסט מנהל נשלח כטקסט רגיל כדי שסימני Markdown לא יגרמו לכשל בשליחה.
            await context.bot.send_message(
                chat_id=user.user_id,
                text=f"📢 הודעה מהמנהל:\n\n{message_text}",
            )
            sent += 1
        except Exception as exc:
            logger.warning("לא ניתן לשלוח ל-%s: %s", user.user_id, exc)
            failed += 1

    await status.edit_text(f"✅ השידור הסתיים.\n📨 נשלח: {sent}\n❌ נכשל: {failed}")


async def list_users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _check_admin(update):
        return

    users = await get_all_users()
    if not users:
        await update.message.reply_text("📋 אין משתמשים רשומים עדיין.")
        return

    lines = ["👥 רשימת משתמשים:", ""]
    for user in users:
        status_parts = []
        if user.is_admin:
            status_parts.append("👑מנהל")
        if user.is_banned:
            status_parts.append("🚫")
        elif user.is_approved:
            status_parts.append("✅")
        else:
            status_parts.append("⏳")
        username = f"@{user.username}" if user.username else "אין שם משתמש"
        lines.append(f"{' '.join(status_parts)} {user.user_id} - {user.full_name or 'לא ידוע'} ({username})")

    chunks = []
    current = []
    current_len = 0
    for line in lines:
        added = len(line) + 1
        if current and current_len + added > 3900:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += added
    if current:
        chunks.append("\n".join(current))

    for chunk in chunks:
        await update.message.reply_text(chunk)
