"""
מטפל עבודה מותאמת אישית (חד-פעמי)
מאפשר הגדרת הגדרות שונות לעיבוד בודד
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
from database.db_manager import is_approved
from utils.keyboards import (
    color_keyboard,
    font_keyboard,
    position_keyboard,
    main_menu_keyboard,
)
from utils.helpers import normalize_hex_color, safe_int, create_color_image

logger = logging.getLogger(__name__)

# מצבי שיחה
(
    CUSTOM_CREDIT_TEXT,
    CUSTOM_COLOR,
    CUSTOM_COLOR_CUSTOM,
    CUSTOM_FONT,
    CUSTOM_POSITION,
    CUSTOM_FREQUENCY,
    CUSTOM_DUR_START,
    CUSTOM_DUR_MIDDLE,
    CUSTOM_DUR_END,
    CUSTOM_WAITING_FILE,
) = range(200, 210)


async def custom_job_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """כניסה לתהליך עבודה מותאמת אישית"""
    user_id = update.effective_user.id

    if not await is_approved(user_id):
        await update.message.reply_text("❌ אין לך גישה לבוט.")
        return ConversationHandler.END

    await update.message.reply_text(
        "🎬 *קרדיט מותאם אישית - עיבוד חד-פעמי*\n\n"
        "הגדרות אלו יחולו רק על הקובץ הבא שתשלח.\n\n"
        "📝 *שלב 1/8 - טקסט הקרדיט:*\n"
        "הכנס את הטקסט שיופיע כקרדיט:",
        parse_mode="Markdown",
    )
    return CUSTOM_CREDIT_TEXT


async def custom_got_credit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ הטקסט לא יכול להיות ריק. נסה שוב:")
        return CUSTOM_CREDIT_TEXT
    context.user_data["c_credit_text"] = text
    await update.message.reply_text(
        "🎨 *שלב 2/8 - צבע:*\nבחר צבע:",
        parse_mode="Markdown",
        reply_markup=color_keyboard(),
    )
    return CUSTOM_COLOR


async def custom_got_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "color_custom":
        await query.edit_message_text("✏️ הזן קוד HEX:")
        return CUSTOM_COLOR_CUSTOM
    color = query.data.replace("color_", "")
    context.user_data["c_color"] = color
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע: `{color}`",
        parse_mode="Markdown"
    )
    
    await query.message.reply_text(
        "🔤 *שלב 3/8 - גופן:*\n"
        "בחר גופן מהרשימה:",
        parse_mode="Markdown",
        reply_markup=font_keyboard()
    )
    return CUSTOM_FONT


async def custom_got_color_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    color = normalize_hex_color(update.message.text)
    if not color:
        await update.message.reply_text("❌ קוד HEX לא תקין. נסה שוב:")
        return CUSTOM_COLOR_CUSTOM
    context.user_data["c_color"] = color
    
    color_image = create_color_image(color)
    await update.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע: `{color}`",
        parse_mode="Markdown"
    )

    await update.message.reply_text(
        "🔤 *שלב 3/8 - גופן:*\n"
        "בחר גופן מהרשימה:",
        parse_mode="Markdown",
        reply_markup=font_keyboard()
    )
    return CUSTOM_FONT


async def custom_got_font(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    font = query.data.replace("font_", "")
    context.user_data["c_font"] = font
    await query.edit_message_text(f"✅ גופן: {font}")
    await query.message.reply_text(
        "📍 *שלב 4/8 - מיקום:*\n"
        "איפה יוצג הקרדיט?",
        parse_mode="Markdown",
        reply_markup=position_keyboard()
    )
    return CUSTOM_POSITION


async def custom_got_position(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    position = query.data.replace("position_", "")
    context.user_data["c_position"] = position
    label = "🔼 למעלה" if position == "top" else "🔽 למטה"
    await query.edit_message_text(f"✅ מיקום: {label}")
    await query.message.reply_text(
        "⏱️ *שלב 5/8 - תדירות:*\n"
        "כל כמה דקות יופיע הקרדיט באמצע הסרט?\n"
        "_(הזן מספר בין 0 ל-60. 0 = ללא קרדיט אמצע)_",
        parse_mode="Markdown"
    )
    return CUSTOM_FREQUENCY


async def custom_got_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    freq = safe_int(update.message.text, 0, 60)
    if freq is None:
        await update.message.reply_text("❌ הזן מספר בין 0 ל-60:")
        return CUSTOM_FREQUENCY
    context.user_data["c_frequency"] = freq
    await update.message.reply_text("⏳ *שלב 6/8 - משך פתיחה (שניות, 1-30):*", parse_mode="Markdown")
    return CUSTOM_DUR_START


async def custom_got_dur_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dur = safe_int(update.message.text, 1, 30)
    if not dur:
        await update.message.reply_text("❌ הזן מספר בין 1 ל-30:")
        return CUSTOM_DUR_START
    context.user_data["c_dur_start"] = dur

    if context.user_data.get("c_frequency") == 0:
        context.user_data["c_dur_middle"] = 0
        await update.message.reply_text("⏳ *שלב 8/8 - משך סיום (שניות, 1-30):*", parse_mode="Markdown")
        return CUSTOM_DUR_END

    await update.message.reply_text("⏳ *שלב 7/8 - משך אמצע (שניות, 1-30):*", parse_mode="Markdown")
    return CUSTOM_DUR_MIDDLE


async def custom_got_dur_middle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dur = safe_int(update.message.text, 1, 30)
    if not dur:
        await update.message.reply_text("❌ הזן מספר בין 1 ל-30:")
        return CUSTOM_DUR_MIDDLE
    context.user_data["c_dur_middle"] = dur
    await update.message.reply_text("⏳ *שלב 8/8 - משך סיום (שניות, 1-30):*", parse_mode="Markdown")
    return CUSTOM_DUR_END


async def custom_got_dur_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dur = safe_int(update.message.text, 1, 30)
    if not dur:
        await update.message.reply_text("❌ הזן מספר בין 1 ל-30:")
        return CUSTOM_DUR_END
    
    # שמירה כהגדרות מותאמות אישית
    context.user_data["custom_settings"] = {
        "credit_text": context.user_data["c_credit_text"],
        "color": context.user_data["c_color"],
        "font": context.user_data["c_font"],
        "position": context.user_data["c_position"],
        "frequency": context.user_data["c_frequency"],
        "duration_start": context.user_data["c_dur_start"],
        "duration_middle": context.user_data.get("c_dur_middle", 0),
        "duration_end": dur,
    }

    # ניקוי נתונים זמניים
    for key in list(context.user_data.keys()):
        if key.startswith("c_"):
            del context.user_data[key]

    await update.message.reply_text(
        "✅ *ההגדרות המותאמות אישית מוכנות!*\n\n"
        "📂 עכשיו שלח לי קובץ `.srt` או `.zip` לעיבוד עם הגדרות אלו.\n\n"
        "_(ההגדרות ישמשו פעם אחת בלבד)_",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


def custom_job_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("custom", custom_job_handler),
            MessageHandler(filters.Regex("^🎬 קרדיט מותאם אישית$"), custom_job_handler)
        ],
        states={
            CUSTOM_CREDIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_credit_text)],
            CUSTOM_COLOR: [CallbackQueryHandler(custom_got_color, pattern=r"^color_")],
            CUSTOM_COLOR_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_color_custom)],
            CUSTOM_FONT: [CallbackQueryHandler(custom_got_font, pattern=r"^font_")],
            CUSTOM_POSITION: [CallbackQueryHandler(custom_got_position, pattern=r"^position_")],
            CUSTOM_FREQUENCY: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_frequency)],
            CUSTOM_DUR_START: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_dur_start)],
            CUSTOM_DUR_MIDDLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_dur_middle)],
            CUSTOM_DUR_END: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_dur_end)],
        },
        fallbacks=[
            CommandHandler("custom", custom_job_handler),
            MessageHandler(filters.Regex("^🎬 קרדיט מותאם אישית$"), custom_job_handler)
        ],
        name="custom_job_conversation",
        persistent=False,
    )
