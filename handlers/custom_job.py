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
from database.db_manager import is_approved, get_user
from utils.keyboards import (
    color_keyboard,
    font_keyboard,
    position_keyboard,
    main_menu_keyboard,
    format_keyboard,
    custom_start_keyboard,
    custom_styling_ask_keyboard,
    border_style_keyboard,
    bold_keyboard,
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
    CUSTOM_OUTPUT_FORMAT,
    # הגדרות מותאמות אישית נוספות
    CUSTOM_START_CHOICE,
    CUSTOM_CREDIT_TEXT_ONLY,
    CUSTOM_STYLING_ASK,
    CUSTOM_FONT_SIZE,
    CUSTOM_BORDER_STYLE,
    CUSTOM_OUTLINE_COLOR,
    CUSTOM_OUTLINE_COLOR_CUSTOM,
    CUSTOM_OUTLINE_WIDTH,
    CUSTOM_SHADOW_WIDTH,
    CUSTOM_BG_COLOR,
    CUSTOM_BG_COLOR_CUSTOM,
    CUSTOM_IS_BOLD,
) = range(200, 223)


async def custom_job_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """כניסה לתהליך עבודה מותאמת אישית"""
    user_id = update.effective_user.id

    message = update.message
    if not message and update.callback_query:
        message = update.callback_query.message

    if not await is_approved(user_id):
        if message:
            await message.reply_text("❌ אין לך גישה לבוט.")
        return ConversationHandler.END

    text = (
        "🎬 *קרדיט מותאם אישית - עיבוד חד-פעמי*\n\n"
        "האם ברצונך להשתמש בהגדרות ברירת המחדל שלך (כך שתתבקש להזין רק את טקסט הקרדיט החדש), או להגדיר הכל ידנית עבור קובץ זה?"
    )
    
    if update.message:
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=custom_start_keyboard(),
        )
    elif update.callback_query:
        await update.callback_query.answer()
        await message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=custom_start_keyboard(),
        )
    return CUSTOM_START_CHOICE


async def custom_start_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    
    if choice == "custom_start_default":
        await query.edit_message_text(
            "📝 *טקסט הקרדיט:*\n"
            "הכנס את הטקסט שיופיע כקרדיט בסיבוב זה:",
            parse_mode="Markdown",
        )
        return CUSTOM_CREDIT_TEXT_ONLY
    else:
        # Manual configuration
        await query.edit_message_text(
            "📝 *שלב 1/9 - טקסט הקרדיט:*\n"
            "הכנס את הטקסט שיופיע כקרדיט:",
            parse_mode="Markdown",
        )
        return CUSTOM_CREDIT_TEXT


async def custom_got_credit_text_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ הטקסט לא יכול להיות ריק. נסה שוב:")
        return CUSTOM_CREDIT_TEXT_ONLY
        
    user_id = update.effective_user.id
    db_user = await get_user(user_id)
    
    context.user_data["custom_settings"] = {
        "credit_text": text,
        "color": db_user.color,
        "font": db_user.font,
        "position": db_user.position,
        "output_format": db_user.output_format,
        "frequency": db_user.frequency,
        "duration_start": db_user.duration_start,
        "duration_middle": db_user.duration_middle,
        "duration_end": db_user.duration_end,
        "font_size": db_user.font_size,
        "border_style": db_user.border_style,
        "outline_color": db_user.outline_color,
        "outline_width": db_user.outline_width,
        "shadow_width": db_user.shadow_width,
        "bg_color": db_user.bg_color,
    }
    
    await update.message.reply_text(
        "✅ *ההגדרות המותאמות אישית מוכנות!*\n"
        "_(נעשה שימוש בהגדרות ברירת המחדל שלך עבור שאר הפרמטרים)_\n\n"
        "📂 עכשיו שלח לי קובץ `.srt` או `.zip` לעיבוד עם הגדרות אלו.\n\n"
        "_(ההגדרות ישמשו פעם אחת בלבד)_",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def custom_got_credit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ הטקסט לא יכול להיות ריק. נסה שוב:")
        return CUSTOM_CREDIT_TEXT
    context.user_data["c_credit_text"] = text
    await update.message.reply_text(
        "🎨 *שלב 2/9 - צבע:*\nבחר צבע:",
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
        "🔤 *שלב 3/9 - גופן:*\n"
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
        "🔤 *שלב 3/9 - גופן:*\n"
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
        "📍 *שלב 4/9 - מיקום:*\n"
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
        "📁 *שלב 5/9 - פורמט קובץ פלט:*\n"
        "בחר את סיומת קובץ הפלט עבור ריצה זו:",
        parse_mode="Markdown",
        reply_markup=format_keyboard()
    )
    return CUSTOM_OUTPUT_FORMAT


async def custom_got_output_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt = query.data.replace("format_", "")
    context.user_data["c_output_format"] = fmt
    await query.edit_message_text(f"✅ פורמט פלט: {fmt.upper()}")
    await query.message.reply_text(
        "🎬 *עיצוב כתוביות מתקדם (ASS)*\n\n"
        "האם ברצונך להגדיר עיצוב מותאם אישית עבור כתוביות אלו (כמו גודל גופן, סגנון ועובי גבול, וצבעי צל)?",
        reply_markup=custom_styling_ask_keyboard()
    )
    return CUSTOM_STYLING_ASK


async def custom_styling_ask_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    
    if choice == "custom_styling_yes":
        await query.edit_message_text(
            "📏 *גודל גופן כתוביות:*\n"
            "הזן מספר שלם בין 10 ל-60:"
        )
        return CUSTOM_FONT_SIZE
    else:
        user_id = update.effective_user.id
        db_user = await get_user(user_id)
        context.user_data["c_font_size"] = db_user.font_size
        context.user_data["c_border_style"] = db_user.border_style
        context.user_data["c_outline_color"] = db_user.outline_color
        context.user_data["c_outline_width"] = db_user.outline_width
        context.user_data["c_shadow_width"] = db_user.shadow_width
        context.user_data["c_bg_color"] = db_user.bg_color
        context.user_data["c_is_bold"] = db_user.is_bold
        
        await query.edit_message_text(
            "⏱️ *שלב 6/9 - תדירות:*\n"
            "כל כמה דקות יופיע הקרדיט באמצע הסרט?\n"
            "_(הזן מספר בין 0 ל-60. 0 = ללא קרדיט אמצע)_"
        )
        return CUSTOM_FREQUENCY


async def custom_got_font_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = safe_int(update.message.text, 10, 60)
    if val is None:
        await update.message.reply_text("❌ הזן מספר שלם בין 10 ל-60:")
        return CUSTOM_FONT_SIZE
    context.user_data["c_font_size"] = val
    await update.message.reply_text(
        "🔳 *סגנון גבול כתוביות:*\n"
        "בחר סגנון:",
        reply_markup=border_style_keyboard()
    )
    return CUSTOM_BORDER_STYLE


async def custom_got_border_style(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    val = int(query.data.replace("border_style_", ""))
    context.user_data["c_border_style"] = val
    label = "צל + גבול" if val == 1 else "קופסה כהה"
    await query.edit_message_text(f"✅ סגנון גבול: {label}")
    await query.message.reply_text(
        "🅰️ *הדגשת גופן (Bold):*\n"
        "בחר האם להדגיש את הכתוביות:",
        reply_markup=bold_keyboard()
    )
    return CUSTOM_IS_BOLD


async def custom_got_is_bold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    val = int(query.data.replace("bold_", ""))
    context.user_data["c_is_bold"] = val
    label = "מודגש (Bold)" if val == 1 else "רגיל"
    await query.edit_message_text(f"✅ הדגשה: {label}")
    await query.message.reply_text(
        "🎨 *צבע גבול / קופסה:*\n"
        "בחר צבע:",
        reply_markup=color_keyboard()
    )
    return CUSTOM_OUTLINE_COLOR


async def custom_got_outline_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "color_custom":
        await query.edit_message_text("✏️ הזן קוד צבע HEX עבור הגבול (למשל #000000):")
        return CUSTOM_OUTLINE_COLOR_CUSTOM
    color = query.data.replace("color_", "")
    context.user_data["c_outline_color"] = color
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע גבול: `{color}`",
        parse_mode="Markdown"
    )
    await query.message.reply_text(
        "➖ *עובי גבול:*\n"
        "הזן מספר שלם בין 0 ל-10:"
    )
    return CUSTOM_OUTLINE_WIDTH


async def custom_got_outline_color_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    color = normalize_hex_color(update.message.text)
    if not color:
        await update.message.reply_text("❌ קוד HEX לא תקין. הזן בפורמט #RRGGBB:")
        return CUSTOM_OUTLINE_COLOR_CUSTOM
    context.user_data["c_outline_color"] = color
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע גבול: `{color}`",
        parse_mode="Markdown"
    )
    await query.message.reply_text(
        "➖ *עובי גבול:*\n"
        "הזן מספר שלם בין 0 ל-10:"
    )
    return CUSTOM_OUTLINE_WIDTH


async def custom_got_outline_width(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = safe_int(update.message.text, 0, 10)
    if val is None:
        await update.message.reply_text("❌ הזן מספר שלם בין 0 ל-10:")
        return CUSTOM_OUTLINE_WIDTH
    context.user_data["c_outline_width"] = val
    await update.message.reply_text(
        "👥 *מרחק צל:*\n"
        "הזן מספר שלם בין 0 ל-10:"
    )
    return CUSTOM_SHADOW_WIDTH


async def custom_got_shadow_width(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = safe_int(update.message.text, 0, 10)
    if val is None:
        await update.message.reply_text("❌ הזן מספר שלם בין 0 ל-10:")
        return CUSTOM_SHADOW_WIDTH
    context.user_data["c_shadow_width"] = val
    await update.message.reply_text(
        "🎨 *צבע צל / רקע:*\n"
        "בחר צבע:",
        reply_markup=color_keyboard()
    )
    return CUSTOM_BG_COLOR


async def custom_got_bg_color(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "color_custom":
        await query.edit_message_text("✏️ הזן קוד צבע HEX עבור הרקע/הצל (למשל #000000):")
        return CUSTOM_BG_COLOR_CUSTOM
    color = query.data.replace("color_", "")
    context.user_data["c_bg_color"] = color
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע רקע/צל: `{color}`",
        parse_mode="Markdown"
    )
    await query.message.reply_text(
        "⏱️ *שלב 6/9 - תדירות:*\n"
        "כל כמה דקות יופיע הקרדיט באמצע הסרט?\n"
        "_(הזן מספר בין 0 ל-60. 0 = ללא קרדיט אמצע)_"
    )
    return CUSTOM_FREQUENCY


async def custom_got_bg_color_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    color = normalize_hex_color(update.message.text)
    if not color:
        await update.message.reply_text("❌ קוד HEX לא תקין. הזן בפורמט #RRGGBB:")
        return CUSTOM_BG_COLOR_CUSTOM
    context.user_data["c_bg_color"] = color
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע רקע/צל: `{color}`",
        parse_mode="Markdown"
    )
    await query.message.reply_text(
        "⏱️ *שלב 6/9 - תדירות:*\n"
        "כל כמה דקות יופיע הקרדיט באמצע הסרט?\n"
        "_(הזן מספר בין 0 ל-60. 0 = ללא קרדיט אמצע)_"
    )
    return CUSTOM_FREQUENCY


async def custom_got_output_format(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt = query.data.replace("format_", "")
    context.user_data["c_output_format"] = fmt
    await query.edit_message_text(f"✅ פורמט פלט: {fmt.upper()}")
    await query.message.reply_text(
        "⏱️ *שלב 6/9 - תדירות:*\n"
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
    await update.message.reply_text("⏳ *שלב 7/9 - משך פתיחה (שניות, 1-30):*", parse_mode="Markdown")
    return CUSTOM_DUR_START


async def custom_got_dur_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dur = safe_int(update.message.text, 1, 30)
    if not dur:
        await update.message.reply_text("❌ הזן מספר בין 1 ל-30:")
        return CUSTOM_DUR_START
    context.user_data["c_dur_start"] = dur

    if context.user_data.get("c_frequency") == 0:
        context.user_data["c_dur_middle"] = 0
        await update.message.reply_text("⏳ *שלב 9/9 - משך סיום (שניות, 1-30):*", parse_mode="Markdown")
        return CUSTOM_DUR_END

    await update.message.reply_text("⏳ *שלב 8/9 - משך אמצע (שניות, 1-30):*", parse_mode="Markdown")
    return CUSTOM_DUR_MIDDLE


async def custom_got_dur_middle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dur = safe_int(update.message.text, 1, 30)
    if not dur:
        await update.message.reply_text("❌ הזן מספר בין 1 ל-30:")
        return CUSTOM_DUR_MIDDLE
    context.user_data["c_dur_middle"] = dur
    await update.message.reply_text("⏳ *שלב 9/9 - משך סיום (שניות, 1-30):*", parse_mode="Markdown")
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
        "output_format": context.user_data.get("c_output_format", "srt"),
        "frequency": context.user_data["c_frequency"],
        "duration_start": context.user_data["c_dur_start"],
        "duration_middle": context.user_data.get("c_dur_middle", 0),
        "duration_end": dur,
        # הגדרות עיצוב מותאמות
        "font_size": context.user_data.get("c_font_size", 20),
        "border_style": context.user_data.get("c_border_style", 1),
        "outline_color": context.user_data.get("c_outline_color", "#000000"),
        "outline_width": context.user_data.get("c_outline_width", 2),
        "shadow_width": context.user_data.get("c_shadow_width", 2),
        "bg_color": context.user_data.get("c_bg_color", "#000000"),
        "is_bold": context.user_data.get("c_is_bold", 1),
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
            CUSTOM_START_CHOICE: [
                CallbackQueryHandler(custom_start_choice_callback, pattern=r"^custom_start_")
            ],
            CUSTOM_CREDIT_TEXT_ONLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_credit_text_only)
            ],
            CUSTOM_CREDIT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_credit_text)
            ],
            CUSTOM_COLOR: [CallbackQueryHandler(custom_got_color, pattern=r"^color_")],
            CUSTOM_COLOR_CUSTOM: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_color_custom)],
            CUSTOM_FONT: [CallbackQueryHandler(custom_got_font, pattern=r"^font_")],
            CUSTOM_POSITION: [CallbackQueryHandler(custom_got_position, pattern=r"^position_")],
            CUSTOM_OUTPUT_FORMAT: [CallbackQueryHandler(custom_got_output_format, pattern=r"^format_")],
            CUSTOM_STYLING_ASK: [
                CallbackQueryHandler(custom_styling_ask_callback, pattern=r"^custom_styling_")
            ],
            CUSTOM_FONT_SIZE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_font_size)
            ],
            CUSTOM_BORDER_STYLE: [
                CallbackQueryHandler(custom_got_border_style, pattern=r"^border_style_")
            ],
            CUSTOM_OUTLINE_COLOR: [
                CallbackQueryHandler(custom_got_outline_color, pattern=r"^color_")
            ],
            CUSTOM_OUTLINE_COLOR_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_outline_color_custom)
            ],
            CUSTOM_OUTLINE_WIDTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_outline_width)
            ],
            CUSTOM_SHADOW_WIDTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_shadow_width)
            ],
            CUSTOM_BG_COLOR: [
                CallbackQueryHandler(custom_got_bg_color, pattern=r"^color_")
            ],
            CUSTOM_BG_COLOR_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_got_bg_color_custom)
            ],
            CUSTOM_IS_BOLD: [
                CallbackQueryHandler(custom_got_is_bold, pattern=r"^bold_")
            ],
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
