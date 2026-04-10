"""
בוט טלגרם להוספת קרדיט לכתוביות
נקודת כניסה ראשית
"""

import asyncio
import logging
from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from config import BOT_TOKEN
from database.db_manager import init_db, increment_processed_files
from handlers.start import (
    start_handler,
    approve_user_callback,
    reject_user_callback,
    setup_conversation_handler,
    help_handler,
)
from handlers.settings import settings_conversation_handler
from handlers.file_receiver import file_receiver_handler
from handlers.custom_job import custom_job_conversation
from handlers.admin_panel import admin_conversation_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    """אתחול לאחר הפעלת הבוט"""
    await init_db()
    
    # הגדרת פקודות התפריט
    commands = [
        BotCommand("start", "הפעלה מחדש"),
        BotCommand("settings", "⚙️ הגדרות"),
        BotCommand("custom", "🎬 עבודה מותאמת אישית"),
        BotCommand("help", "❓ עזרה"),
        BotCommand("admin", "👑 פאנל ניהול"),
    ]
    await application.bot.set_my_commands(commands)
    
    logger.info("✅ מסד הנתונים אותחל והפקודות הוגדרו")


async def custom_file_receiver_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler מיוחד שרץ אחרי כל עיבוד קובץ כדי לעדכן סטטיסטיקות
    """
    # קריאה ל-Handler המקורי
    await file_receiver_handler(update, context)
    
    # הגדלת מונה הקבצים (בפועל זה יקרה גם אם העיבוד נכשל, אבל זה קירוב טוב)
    if update.message and update.message.document:
        await increment_processed_files()


def main() -> None:
    """הפעלת הבוט"""
    if not BOT_TOKEN:
        raise ValueError("❌ BOT_TOKEN לא מוגדר בקובץ .env")

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # שיחות
    application.add_handler(setup_conversation_handler())
    application.add_handler(settings_conversation_handler())
    application.add_handler(custom_job_conversation())
    application.add_handler(admin_conversation_handler())

    # פקודות פשוטות
    application.add_handler(CommandHandler("help", help_handler))

    # Callback לאישור/דחיית משתמשים
    application.add_handler(CallbackQueryHandler(approve_user_callback, pattern=r"^approve_\d+$"))
    application.add_handler(CallbackQueryHandler(reject_user_callback, pattern=r"^reject_\d+$"))

    # קבלת קבצים - זה צריך להיות ה-Handler האחרון כדי לא לחסום אחרים
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
