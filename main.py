"""
בוט טלגרם להוספת קרדיט לכתוביות
נקודת כניסה ראשית
"""

import logging
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from config import BOT_TOKEN
from database.db_manager import init_db, increment_processed_files, is_admin
from handlers.start import (
    approve_user_callback,
    reject_user_callback,
    setup_conversation_handler,
    help_handler,
)
from handlers.settings import settings_conversation_handler
from handlers.file_receiver import file_receiver_handler
from handlers.custom_job import custom_job_conversation
from handlers.admin_panel import admin_conversation_handler
from handlers.admin import (
    ban_handler,
    promote_handler,
    broadcast_handler,
    list_users_handler,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """אתחול לאחר הפעלת הבוט."""
    await init_db()

    commands = [
        BotCommand("start", "הפעלה מחדש"),
        BotCommand("settings", "⚙️ הגדרות"),
        BotCommand("custom", "🎬 עבודה מותאמת אישית"),
        BotCommand("help", "❓ עזרה"),
        BotCommand("admin", "👑 פאנל ניהול"),
        BotCommand("ban", "🚫 חסימת משתמש (מנהל)"),
        BotCommand("promote", "👑 קידום למנהל (מנהל ראשי)"),
        BotCommand("broadcast", "📢 שידור הודעה (מנהל)"),
        BotCommand("users", "👥 רשימת משתמשים (מנהל)"),
    ]
    await application.bot.set_my_commands(commands)
    logger.info("✅ מסד הנתונים אותחל והפקודות הוגדרו")


async def secure_reject_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """מגן על פעולת הדחייה באותה בדיקת הרשאות של פעולת האישור."""
    query = update.callback_query
    if not await is_admin(update.effective_user.id):
        if query:
            await query.answer("❌ אין לך הרשאת מנהל.", show_alert=True)
        return
    await reject_user_callback(update, context)


async def custom_file_receiver_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """מעבד קובץ ומעדכן סטטיסטיקה רק עבור כתוביות שעובדו בהצלחה."""
    processed_count = await file_receiver_handler(update, context)
    if processed_count > 0:
        await increment_processed_files(processed_count)


def main() -> None:
    """הפעלת הבוט."""
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN לא מוגדר בקובץ .env")

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_handler(setup_conversation_handler())
    application.add_handler(settings_conversation_handler())
    application.add_handler(custom_job_conversation())
    application.add_handler(admin_conversation_handler())

    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("ban", ban_handler))
    application.add_handler(CommandHandler("promote", promote_handler))
    application.add_handler(CommandHandler("broadcast", broadcast_handler))
    application.add_handler(CommandHandler("users", list_users_handler))

    application.add_handler(CallbackQueryHandler(approve_user_callback, pattern=r"^approve_\d+$"))
    application.add_handler(CallbackQueryHandler(secure_reject_user_callback, pattern=r"^reject_\d+$"))

    application.add_handler(
        MessageHandler(
            filters.Document.ALL & ~filters.COMMAND,
            custom_file_receiver_handler,
        )
    )

    logger.info("🤖 הבוט פועל...")
    application.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
