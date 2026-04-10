"""
מטפל פאנל ניהול
"""

import logging
from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    CommandHandler,
)
from database.db_manager import (
    get_stats,
    get_all_users,
    get_all_approved_users,
    is_admin,
    upsert_user,
    get_user,
    update_user_settings
)
from database.models import User
from utils.keyboards import admin_panel_keyboard, main_menu_keyboard

logger = logging.getLogger(__name__)

# מצבים
ADMIN_MENU, ADMIN_BROADCAST_MSG, ADMIN_ADD_USER_ID = range(300, 303)

async def admin_panel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """כניסה לפאנל ניהול"""
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        await update.message.reply_text("❌ אין לך הרשאת מנהל.")
        return ConversationHandler.END
        
    await update.message.reply_text(
        "👑 *פאנל ניהול*\nבחר פעולה:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )
    return ADMIN_MENU

async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data
    
    if action == "admin_stats":
        stats = await get_stats()
        users = await get_all_users()
        approved = [u for u in users if u.is_approved]
        
        text = (
            "📊 *סטטיסטיקות מערכת*\n\n"
            f"👥 סה\"כ משתמשים: `{len(users)}`\n"
            f"✅ משתמשים מאושרים: `{len(approved)}`\n"
            f"🎬 קבצים שעובדו: `{stats.get('processed_files', 0)}`"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_panel_keyboard())
        return ADMIN_MENU
        
    elif action == "admin_users":
        users = await get_all_users()
        text = "👥 *רשימת משתמשים:*\n\n"
        for u in users:
            status = "✅" if u.is_approved else "⏳"
            if u.is_banned: status = "🚫"
            if u.is_admin: status = "👑"
            
            line = f"{status} `{u.user_id}` - {u.full_name}\n"
            if len(text) + len(line) > 4000:
                text += "\n...(רשימה חלקית)"
                break
            text += line
            
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=admin_panel_keyboard())
        return ADMIN_MENU

    elif action == "admin_broadcast":
        await query.edit_message_text(
            "🗣️ *שידור הודעה*\n\n"
            "שלח את ההודעה שברצונך לשדר לכל המשתמשים המאושרים:\n"
            "_(שלח /cancel לביטול)_",
            parse_mode="Markdown"
        )
        return ADMIN_BROADCAST_MSG

    elif action == "admin_add_user":
        await query.edit_message_text(
            "➕ *הוספת משתמש*\n\n"
            "שלח את ה-ID של המשתמש שברצונך להוסיף/לאשר:\n"
            "_(שלח /cancel לביטול)_",
            parse_mode="Markdown"
        )
        return ADMIN_ADD_USER_ID

    elif action == "admin_back_to_main":
        await query.delete_message()
        await query.message.reply_text("תפריט ראשי", reply_markup=main_menu_keyboard(is_admin=True))
        return ConversationHandler.END

    return ADMIN_MENU

async def admin_broadcast_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    users = await get_all_approved_users()
    count = 0
    
    status_msg = await update.message.reply_text(f"⏳ משדר ל-{len(users)} משתמשים...")
    
    for user in users:
        try:
            await context.bot.send_message(chat_id=user.user_id, text=text)
            count += 1
        except Exception:
            pass
            
    await status_msg.edit_text(f"✅ השידור הושלם. נשלח ל-{count} משתמשים.")
    
    await update.message.reply_text(
        "👑 *פאנל ניהול*\nבחר פעולה:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )
    return ADMIN_MENU

async def admin_add_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        target_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ מזהה לא תקין. נסה שוב או שלח /cancel.")
        return ADMIN_ADD_USER_ID
        
    user = await get_user(target_id)
    if user:
        if not user.is_approved:
            await update_user_settings(target_id, is_approved=True)
            await update.message.reply_text(f"✅ המשתמש {target_id} אושר בהצלחה.")
            try:
                await context.bot.send_message(target_id, "✅ הגישה שלך אושרה על ידי מנהל!")
            except: pass
        else:
            await update.message.reply_text(f"⚠️ המשתמש {target_id} כבר מאושר.")
    else:
        # יצירת משתמש חדש
        new_user = User(
            user_id=target_id,
            username=None,
            full_name="Added by Admin",
            is_approved=True,
            setup_done=False
        )
        await upsert_user(new_user)
        await update.message.reply_text(f"✅ המשתמש {target_id} נוסף ואושר בהצלחה.")

    await update.message.reply_text(
        "👑 *פאנל ניהול*\nבחר פעולה:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )
    return ADMIN_MENU

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ הפעולה בוטלה.")
    await update.message.reply_text(
        "👑 *פאנל ניהול*\nבחר פעולה:",
        parse_mode="Markdown",
        reply_markup=admin_panel_keyboard()
    )
    return ADMIN_MENU

def admin_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("admin", admin_panel_entry)
        ],
        states={
            ADMIN_MENU: [
                CallbackQueryHandler(admin_menu_callback, pattern=r"^admin_")
            ],
            ADMIN_BROADCAST_MSG: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_msg)
            ],
            ADMIN_ADD_USER_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_user_id)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", admin_cancel),
            CommandHandler("admin", admin_panel_entry)
        ],
        name="admin_conversation",
        persistent=False,
    )
