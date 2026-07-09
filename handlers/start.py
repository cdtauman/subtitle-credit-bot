"""
מטפל פקודת /start והגדרה ראשונית
"""

import logging
from telegram import Update, Message
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from config import ADMIN_IDS
from database.db_manager import get_user, upsert_user, update_user_settings, is_approved
from database.models import User
from utils.keyboards import (
    main_menu_keyboard,
    color_keyboard,
    font_keyboard,
    position_keyboard,
    admin_approval_keyboard,
    format_keyboard,
)
from utils.helpers import normalize_hex_color, safe_int

logger = logging.getLogger(__name__)

# מצבי שיחה להגדרה ראשונית
(
    WAITING_CREDIT_TEXT,
    WAITING_COLOR,
    WAITING_COLOR_CUSTOM,
    WAITING_FONT,
    WAITING_POSITION,
    WAITING_FREQUENCY,
    WAITING_DURATION_START,
    WAITING_DURATION_MIDDLE,
    WAITING_DURATION_END,
    WAITING_OUTPUT_FORMAT,
) = range(10)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בפקודת /start"""
    user = update.effective_user
    db_user = await get_user(user.id)

    if db_user is None:
        # משתמש חדש - שמירה ובקשת אישור
        new_user = User(
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            is_approved=False,
        )
        await upsert_user(new_user)

        await update.message.reply_text(
            "👋 שלום! הבקשה שלך לגישה לבוט התקבלה ונשלחה למנהל לאישור.\n"
            "תקבל הודעה ברגע שהבקשה תאושר. 🕐"
        )

        # שליחת התראה למנהלים
        for admin_id in ADMIN_IDS:
            try:
                keyboard = admin_approval_keyboard(user.id)
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🔔 *בקשת גישה חדשה!*\n\n"
                        f"👤 שם: {user.full_name}\n"
                        f"🆔 מזהה: `{user.id}`\n"
                        f"📛 שם משתמש: @{user.username or 'אין'}"
                    ),
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception as e:
                logger.warning(f"לא ניתן לשלוח התראה למנהל {admin_id}: {e}")
        return ConversationHandler.END

    if db_user.is_banned:
        await update.message.reply_text("🚫 הגישה שלך לבוט חסומה. פנה למנהל.")
        return ConversationHandler.END

    if not db_user.is_approved:
        await update.message.reply_text(
            "⏳ הבקשה שלך עדיין ממתינה לאישור מנהל. אנא המתן."
        )
        return ConversationHandler.END

    if not db_user.setup_done:
        # המשתמש מאושר אך טרם ביצע הגדרה ראשונית
        return await _start_setup(update, context)

    # בדיקה אם המשתמש הוא מנהל כדי להציג תפריט מתאים
    is_admin_user = db_user.is_admin or user.id in ADMIN_IDS

    await update.message.reply_text(
        f"👋 ברוך הבא, {user.first_name}!\n\n"
        "📂 שלח לי קובץ `.srt` או `.zip` עם קבצי כתוביות ואעבד אותם עבורך.\n\n"
        "השתמש בתפריט למטה לשינוי הגדרות או לעבודה מותאמת אישית.",
        reply_markup=main_menu_keyboard(is_admin=is_admin_user),
    )
    return ConversationHandler.END


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פקודת עזרה"""
    text = (
        "📚 *מדריך למשתמש*\n\n"
        "בוט זה מאפשר לך להוסיף קרדיטים אוטומטיים לקבצי כתוביות.\n\n"
        "*איך זה עובד?*\n"
        "1. שלח קובץ `.srt` או קובץ `.zip` המכיל כתוביות.\n"
        "2. הבוט יעבד את הקובץ ויוסיף את הקרדיט שלך לפי ההגדרות שקבעת.\n"
        "3. תקבל חזרה את הקובץ המעובד.\n\n"
        "*הגדרות:*\n"
        "ניתן לשנות את הגדרות הקרדיט (טקסט, צבע, גופן, מיקום, תדירות) בכל עת דרך התפריט `/settings`.\n\n"
        "*עבודה מותאמת אישית:*\n"
        "אם ברצונך להשתמש בהגדרות שונות עבור קובץ ספציפי (מבלי לשנות את ההגדרות הקבועות), השתמש בפקודה `/custom`.\n\n"
        "*תמיכה:*\n"
        "אם נתקלת בבעיה, פנה למנהל המערכת."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def _start_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """התחלת תהליך ההגדרה הראשונית"""
    await update.message.reply_text(
        "🎉 *ברוך הבא! בוא נגדיר את הגדרות ברירת המחדל שלך.*\n\n"
        "הגדרות אלו ישמשו לכל עיבוד אוטומטי של קבצים.\n\n"
        "📝 *שלב 1/9 - טקסט הקרדיט:*\n"
        "הכנס את הטקסט שיופיע כקרדיט בכתוביות:\n"
        "_(לדוגמה: תרגום: צוות אריאל)_",
        parse_mode="Markdown",
    )
    return WAITING_CREDIT_TEXT


async def setup_got_credit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    credit_text = update.message.text.strip()
    if not credit_text:
        await update.message.reply_text("❌ הטקסט לא יכול להיות ריק. נסה שוב:")
        return WAITING_CREDIT_TEXT

    context.user_data["setup_credit_text"] = credit_text
    await update.message.reply_text(
        "✅ נשמר!\n\n"
        "🎨 *שלב 2/9 - צבע הקרדיט:*\n"
        "בחר צבע מהרשימה או הזן קוד HEX מותאם:",
        parse_mode="Markdown",
        reply_markup=color_keyboard(),
    )
    return WAITING_COLOR


async def setup_got_color_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "color_custom":
        await query.edit_message_text(
            "✏️ הזן קוד צבע HEX (לדוגמה: #FF5733):"
        )
        return WAITING_COLOR_CUSTOM

    color = query.data.replace("color_", "")
    context.user_data["setup_color"] = color
    await query.edit_message_text(f"✅ צבע נבחר: `{color}`", parse_mode="Markdown")
    await query.message.reply_text(
        "🔤 *שלב 3/9 - גופן:*\n"
        "בחר גופן מהרשימה:",
        parse_mode="Markdown",
        reply_markup=font_keyboard(),
    )
    return WAITING_FONT


async def setup_got_color_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    color = normalize_hex_color(update.message.text)
    if not color:
        await update.message.reply_text(
            "❌ קוד HEX לא תקין. הזן בפורמט #RRGGBB (לדוגמה: #FF5733):"
        )
        return WAITING_COLOR_CUSTOM

    context.user_data["setup_color"] = color
    await update.message.reply_text(
        f"✅ צבע נבחר: `{color}`\n\n"
        "🔤 *שלב 3/9 - גופן:*\n"
        "בחר גופן מהרשימה:",
        parse_mode="Markdown",
        reply_markup=font_keyboard(),
    )
    return WAITING_FONT


async def setup_got_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    font = query.data.replace("font_", "")
    context.user_data["setup_font"] = font
    await query.edit_message_text(f"✅ גופן נבחר: {font}")
    await query.message.reply_text(
        "📍 *שלב 4/9 - מיקום:*\n"
        "איפה יוצג הקרדיט?",
        parse_mode="Markdown",
        reply_markup=position_keyboard(),
    )
    return WAITING_POSITION


async def setup_got_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    position = query.data.replace("position_", "")
    context.user_data["setup_position"] = position
    pos_label = "🔼 למעלה" if position == "top" else "🔽 למטה"
    await query.edit_message_text(f"✅ מיקום נבחר: {pos_label}")
    await query.message.reply_text(
        "📁 *שלב 5/9 - פורמט קובץ פלט:*\n"
        "בחר את סיומת קובץ הפלט המועדפת עליך:",
        parse_mode="Markdown",
        reply_markup=format_keyboard(),
    )
    return WAITING_OUTPUT_FORMAT


async def setup_got_output_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt = query.data.replace("format_", "")
    context.user_data["setup_output_format"] = fmt
    await query.edit_message_text(f"✅ פורמט נבחר: {fmt.upper()}")
    await query.message.reply_text(
        "⏱️ *שלב 6/9 - תדירות:*\n"
        "כל כמה דקות יופיע הקרדיט באמצע הסרט?\n"
        "_(הזן מספר בין 0 ל-60. 0 = ללא קרדיט אמצע)_",
        parse_mode="Markdown",
    )
    return WAITING_FREQUENCY


async def setup_got_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    freq = safe_int(update.message.text, min_val=0, max_val=60)
    if freq is None:
        await update.message.reply_text("❌ הזן מספר תקין בין 0 ל-60:")
        return WAITING_FREQUENCY

    context.user_data["setup_frequency"] = freq
    await update.message.reply_text(
        "⏳ *שלב 7/9 - משך קרדיט פתיחה:*\n"
        "כמה שניות יוצג הקרדיט בתחילת הסרט?\n"
        "_(הזן מספר שניות בין 1 ל-30)_",
        parse_mode="Markdown",
    )
    return WAITING_DURATION_START


async def setup_got_duration_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dur = safe_int(update.message.text, min_val=1, max_val=30)
    if dur is None:
        await update.message.reply_text("❌ הזן מספר תקין בין 1 ל-30:")
        return WAITING_DURATION_START

    context.user_data["setup_duration_start"] = dur

    # אם התדירות היא 0, מדלגים על משך אמצע
    if context.user_data.get("setup_frequency") == 0:
        context.user_data["setup_duration_middle"] = 0
        await update.message.reply_text(
            "⏳ *שלב 9/9 - משך קרדיט סיום:*\n"
            "כמה שניות יוצג הקרדיט בסוף הסרט?\n"
            "_(הזן מספר שניות בין 1 ל-30)_",
            parse_mode="Markdown",
        )
        return WAITING_DURATION_END

    await update.message.reply_text(
        "⏳ *שלב 8/9 - משך קרדיט אמצע:*\n"
        "כמה שניות יוצג כל קרדיט באמצע הסרט?\n"
        "_(הזן מספר שניות בין 1 ל-30)_",
        parse_mode="Markdown",
    )
    return WAITING_DURATION_MIDDLE


async def setup_got_duration_middle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dur = safe_int(update.message.text, min_val=1, max_val=30)
    if dur is None:
        await update.message.reply_text("❌ הזן מספר תקין בין 1 ל-30:")
        return WAITING_DURATION_MIDDLE

    context.user_data["setup_duration_middle"] = dur
    await update.message.reply_text(
        "⏳ *שלב 9/9 - משך קרדיט סיום:*\n"
        "כמה שניות יוצג הקרדיט בסוף הסרט?\n"
        "_(הזן מספר שניות בין 1 ל-30)_",
        parse_mode="Markdown",
    )
    return WAITING_DURATION_END


async def setup_got_duration_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dur = safe_int(update.message.text, min_val=1, max_val=30)
    if dur is None:
        await update.message.reply_text("❌ הזן מספר תקין בין 1 ל-30:")
        return WAITING_DURATION_END

    user_id = update.effective_user.id
    data = context.user_data

    # בדיקה אם המשתמש הוא מנהל
    from database.db_manager import is_admin
    is_admin_user = await is_admin(user_id)

    await update_user_settings(
        user_id,
        credit_text=data["setup_credit_text"],
        color=data["setup_color"],
        font=data["setup_font"],
        position=data["setup_position"],
        output_format=data.get("setup_output_format", "srt"),
        frequency=data["setup_frequency"],
        duration_start=data["setup_duration_start"],
        duration_middle=data.get("setup_duration_middle", 0),
        duration_end=dur,
        setup_done=True,
    )

    # ניקוי נתונים זמניים
    for key in list(data.keys()):
        if key.startswith("setup_"):
            del data[key]

    await update.message.reply_text(
        "🎉 *ההגדרות נשמרו בהצלחה!*\n\n"
        "עכשיו שלח לי קובץ `.srt` או `.zip` ואעבד אותו עבורך.\n\n"
        "תוכל לשנות הגדרות בכל עת דרך כפתור ⚙️ הגדרות.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(is_admin=is_admin_user),
    )
    return ConversationHandler.END


async def approve_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """אישור משתמש על ידי מנהל"""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id not in ADMIN_IDS:
        # בדיקה מורחבת
        from database.db_manager import is_admin
        if not await is_admin(update.effective_user.id):
            await query.answer("❌ אין לך הרשאת מנהל.", show_alert=True)
            return

    target_user_id = int(query.data.replace("approve_", ""))
    await update_user_settings(target_user_id, is_approved=True)

    await query.edit_message_text(
        query.message.text + f"\n\n✅ *אושר על ידי {update.effective_user.full_name}*",
        parse_mode="Markdown",
    )

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=(
                "✅ *הגישה שלך אושרה!*\n\n"
                "כעת תוכל להשתמש בבוט.\n"
                "שלח /start להתחיל."
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"לא ניתן לשלוח הודעה למשתמש {target_user_id}: {e}")


async def reject_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """דחיית משתמש על ידי מנהל"""
    query = update.callback_query
    await query.answer()

    target_user_id = int(query.data.replace("reject_", ""))

    await query.edit_message_text(
        query.message.text + f"\n\n❌ *נדחה על ידי {update.effective_user.full_name}*",
        parse_mode="Markdown",
    )

    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text="❌ בקשת הגישה שלך נדחתה. פנה למנהל לפרטים נוספים.",
        )
    except Exception:
        pass


def setup_conversation_handler() -> ConversationHandler:
    """יצירת ConversationHandler להגדרה ראשונית"""
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_handler)],
        states={
            WAITING_CREDIT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_got_credit_text)
            ],
            WAITING_COLOR: [
                CallbackQueryHandler(setup_got_color_callback, pattern=r"^color_")
            ],
            WAITING_COLOR_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_got_color_custom)
            ],
            WAITING_FONT: [
                CallbackQueryHandler(setup_got_font, pattern=r"^font_")
            ],
            WAITING_POSITION: [
                CallbackQueryHandler(setup_got_position, pattern=r"^position_")
            ],
            WAITING_OUTPUT_FORMAT: [
                CallbackQueryHandler(setup_got_output_format, pattern=r"^format_")
            ],
            WAITING_FREQUENCY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_got_frequency)
            ],
            WAITING_DURATION_START: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_got_duration_start)
            ],
            WAITING_DURATION_MIDDLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_got_duration_middle)
            ],
            WAITING_DURATION_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, setup_got_duration_end)
            ],
        },
        fallbacks=[CommandHandler("start", start_handler)],
        name="setup_conversation",
        persistent=False,
    )
