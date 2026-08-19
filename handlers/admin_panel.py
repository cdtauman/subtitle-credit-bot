"""פאנל ניהול אינטראקטיבי."""

import logging

from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import ADMIN_IDS
from database.db_manager import (
    get_all_approved_users,
    get_all_users,
    get_stats,
    get_user,
    is_admin,
    update_user_settings,
    upsert_user,
)
from database.models import User
from utils.keyboards import admin_panel_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)

ADMIN_MENU, ADMIN_BROADCAST_MSG, ADMIN_ADD_USER_ID = range(300, 303)


async def _ensure_admin(update: Update) -> bool:
    """בודק הרשאה בכל פעולה, גם אם המשתמש כבר נמצא בתוך Conversation state ישן."""
    if await is_admin(update.effective_user.id):
        return True

    query = update.callback_query
    if query:
        await query.answer("❌ הרשאת המנהל שלך אינה פעילה.", show_alert=True)
    elif update.message:
        await update.message.reply_text("❌ אין לך הרשאת מנהל פעילה.")
    return False


async def admin_panel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_admin(update):
        return ConversationHandler.END
    await update.message.reply_text(
        "👑 *פאנל ניהול*\nבחר פעולה:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard(),
    )
    return ADMIN_MENU


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_admin(update):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "admin_stats":
        stats = await get_stats()
        users = await get_all_users()
        approved = [user for user in users if user.is_approved and not user.is_banned]
        text = (
            "📊 *סטטיסטיקות מערכת*\n\n"
            f"👥 סה\"כ משתמשים: `{len(users)}`\n"
            f"✅ משתמשים מאושרים: `{len(approved)}`\n"
            f"🎬 קבצים שעובדו: `{stats.get('processed_files', 0)}`"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_panel_keyboard())
        return ADMIN_MENU

    if action == "admin_users":
        users = await get_all_users()
        lines = ["👥 רשימת משתמשים:", ""]
        for user in users:
            if user.is_banned:
                status = "🚫"
            elif user.is_admin:
                status = "👑"
            elif user.is_approved:
                status = "✅"
            else:
                status = "⏳"
            line = f"{status} {user.user_id} - {user.full_name}"
            if sum(len(part) + 1 for part in lines) + len(line) > 3900:
                lines.append("...(רשימה חלקית)")
                break
            lines.append(line)
        await query.edit_message_text("\n".join(lines), reply_markup=admin_panel_keyboard())
        return ADMIN_MENU

    if action == "admin_broadcast":
        await query.edit_message_text(
            "🗣️ *שידור הודעה*\n\nשלח את ההודעה שברצונך לשדר לכל המשתמשים המאושרים:\n_(שלח /cancel לביטול)_",
            parse_mode="Markdown",
        )
        return ADMIN_BROADCAST_MSG

    if action == "admin_add_user":
        await query.edit_message_text(
            "➕ *הוספת משתמש*\n\nשלח את ה-ID של המשתמש שברצונך להוסיף/לאשר:\n_(שלח /cancel לביטול)_",
            parse_mode="Markdown",
        )
        return ADMIN_ADD_USER_ID

    if action == "admin_back_to_main":
        await query.delete_message()
        await query.message.reply_text("תפריט ראשי", reply_markup=main_menu_keyboard(is_admin=True))
        return ConversationHandler.END

    return ADMIN_MENU


async def admin_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_admin(update):
        return ConversationHandler.END

    text = update.message.text
    users = await get_all_approved_users()
    count = 0
    status_msg = await update.message.reply_text(f"⏳ משדר ל-{len(users)} משתמשים...")
    for user in users:
        try:
            await context.bot.send_message(chat_id=user.user_id, text=text)
            count += 1
        except Exception as exc:
            logger.warning("Broadcast to %s failed: %s", user.user_id, exc)

    await status_msg.edit_text(f"✅ השידור הושלם. נשלח ל-{count} משתמשים.")
    await update.message.reply_text(
        "👑 *פאנל ניהול*\nבחר פעולה:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard(),
    )
    return ADMIN_MENU


async def admin_add_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_admin(update):
        return ConversationHandler.END

    try:
        target_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ מזהה לא תקין. נסה שוב או שלח /cancel.")
        return ADMIN_ADD_USER_ID

    actor_id = update.effective_user.id
    user = await get_user(target_id)
    if user:
        if user.is_admin and actor_id not in ADMIN_IDS and (user.is_banned or not user.is_approved):
            await update.message.reply_text("❌ רק מנהל ראשי יכול לשנות גישה של מנהל אחר.")
            return ADMIN_MENU

        if not user.is_approved or user.is_banned:
            await update_user_settings(target_id, is_approved=True, is_banned=False)
            await update.message.reply_text(f"✅ המשתמש {target_id} אושר בהצלחה.")
            try:
                await context.bot.send_message(target_id, "✅ הגישה שלך אושרה על ידי מנהל!")
            except Exception as exc:
                logger.warning("Could not notify approved user %s: %s", target_id, exc)
        else:
            await update.message.reply_text(f"⚠️ המשתמש {target_id} כבר מאושר.")
    else:
        await upsert_user(
            User(
                user_id=target_id,
                username=None,
                full_name="Added by Admin",
                is_approved=True,
                setup_done=False,
            )
        )
        await update.message.reply_text(f"✅ המשתמש {target_id} נוסף ואושר בהצלחה.")

    await update.message.reply_text(
        "👑 *פאנל ניהול*\nבחר פעולה:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard(),
    )
    return ADMIN_MENU


async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await _ensure_admin(update):
        return ConversationHandler.END
    await update.message.reply_text("❌ הפעולה בוטלה.")
    await update.message.reply_text(
        "👑 *פאנל ניהול*\nבחר פעולה:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard(),
    )
    return ADMIN_MENU


def admin_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("admin", admin_panel_entry)],
        states={
            ADMIN_MENU: [CallbackQueryHandler(admin_menu_callback, pattern=r"^admin_")],
            ADMIN_BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_msg)],
            ADMIN_ADD_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_user_id)],
        },
        fallbacks=[
            CommandHandler("cancel", admin_cancel),
            CommandHandler("admin", admin_panel_entry),
        ],
        name="admin_conversation",
        persistent=False,
    )
