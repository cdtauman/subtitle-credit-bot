"""
מטפל הגדרות משתמש
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
from database.db_manager import get_user, update_user_settings, is_approved
from utils.keyboards import (
    settings_menu_keyboard,
    color_keyboard,
    font_keyboard,
    position_keyboard,
    main_menu_keyboard,
)
from utils.helpers import normalize_hex_color, safe_int, format_user_settings, create_color_image

logger = logging.getLogger(__name__)

# מצבי שיחת הגדרות
(
    SETTINGS_MENU,
    EDIT_CREDIT_TEXT,
    EDIT_COLOR,
    EDIT_COLOR_CUSTOM,
    EDIT_FONT,
    EDIT_POSITION,
    EDIT_FREQUENCY,
    EDIT_DUR_START,
    EDIT_DUR_MIDDLE,
    EDIT_DUR_END,
) = range(100, 110)


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """כניסה לתפריט הגדרות"""
    user_id = update.effective_user.id

    # טיפול במקרה של callback query
    message = update.message
    if not message and update.callback_query:
        message = update.callback_query.message

    if not await is_approved(user_id):
        if message:
            await message.reply_text("❌ אין לך גישה לבוט.")
        return ConversationHandler.END

    db_user = await get_user(user_id)
    if not db_user or not db_user.setup_done:
        if message:
            await message.reply_text(
                "⚠️ תחילה יש להשלים את ההגדרה הראשונית. שלח /start"
            )
        return ConversationHandler.END

    text = format_user_settings(db_user)
    
    # אם זו הודעה רגילה
    if update.message:
        await update.message.reply_text(
            text + "\n\n*בחר מה לערוך:*",
            parse_mode="Markdown",
            reply_markup=settings_menu_keyboard(),
        )
    # אם זה callback query (חזרה לתפריט)
    elif update.callback_query:
        # מנסים לערוך את ההודעה הקיימת
        try:
            await update.callback_query.edit_message_text(
                text + "\n\n*בחר מה לערוך:*",
                parse_mode="Markdown",
                reply_markup=settings_menu_keyboard(),
            )
        except Exception:
            # אם אי אפשר לערוך (למשל הודעה ישנה מדי), שולחים חדשה
            await message.reply_text(
                text + "\n\n*בחר מה לערוך:*",
                parse_mode="Markdown",
                reply_markup=settings_menu_keyboard(),
            )
            
    return SETTINGS_MENU


async def settings_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data

    if action == "settings_done":
        await query.edit_message_text("✅ ההגדרות נשמרו.")
        await query.message.reply_text("חזרנו לתפריט הראשי.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    prompts = {
        "edit_credit_text": ("📝 הזן טקסט קרדיט חדש:", EDIT_CREDIT_TEXT),
        "edit_color": ("🎨 בחר צבע חדש:", EDIT_COLOR),
        "edit_font": ("🔤 בחר גופן חדש:", EDIT_FONT),
        "edit_position": ("📍 בחר מיקום חדש:", EDIT_POSITION),
        "edit_frequency": ("⏱️ הזן תדירות חדשה (דקות, 0-60). 0 = ללא קרדיט אמצע:", EDIT_FREQUENCY),
        "edit_dur_start": ("⏳ הזן משך קרדיט פתיחה (שניות, 1-30):", EDIT_DUR_START),
        "edit_dur_middle": ("⏳ הזן משך קרדיט אמצע (שניות, 1-30):", EDIT_DUR_MIDDLE),
        "edit_dur_end": ("⏳ הזן משך קרדיט סיום (שניות, 1-30):", EDIT_DUR_END),
    }

    if action not in prompts:
        return SETTINGS_MENU

    prompt, state = prompts[action]

    if action == "edit_color":
        await query.edit_message_text(prompt, reply_markup=color_keyboard())
        return EDIT_COLOR
    elif action == "edit_font":
        await query.edit_message_text(prompt, reply_markup=font_keyboard())
        return EDIT_FONT
    elif action == "edit_position":
        await query.edit_message_text(prompt, reply_markup=position_keyboard())
        return EDIT_POSITION
    else:
        await query.edit_message_text(prompt)
        return state


async def edit_credit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ הטקסט לא יכול להיות ריק. נסה שוב:")
        return EDIT_CREDIT_TEXT
    await update_user_settings(update.effective_user.id, credit_text=text)
    await update.message.reply_text(
        f"✅ טקסט קרדיט עודכן: `{text}`",
        parse_mode="Markdown",
    )
    return await settings_handler(update, context)


async def edit_color_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "color_custom":
        await query.edit_message_text("✏️ הזן קוד HEX (לדוגמה: #FF5733):")
        return EDIT_COLOR_CUSTOM
    color = query.data.replace("color_", "")
    await update_user_settings(update.effective_user.id, color=color)
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע עודכן: `{color}`",
        parse_mode="Markdown"
    )
    
    return await settings_handler(update, context)


async def edit_color_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    color = normalize_hex_color(update.message.text)
    if not color:
        await update.message.reply_text("❌ קוד HEX לא תקין. הזן בפורמט #RRGGBB:")
        return EDIT_COLOR_CUSTOM
    await update_user_settings(update.effective_user.id, color=color)
    
    color_image = create_color_image(color)
    await update.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע עודכן: `{color}`",
        parse_mode="Markdown"
    )

    return await settings_handler(update, context)


async def edit_font_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    font = query.data.replace("font_", "")
    await update_user_settings(update.effective_user.id, font=font)
    return await settings_handler(update, context)


async def edit_position_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    position = query.data.replace("position_", "")
    await update_user_settings(update.effective_user.id, position=position)
    return await settings_handler(update, context)


async def _edit_number_field(update, context, field_name, min_v, max_v, label):
    val = safe_int(update.message.text, min_val=min_v, max_val=max_v)
    if val is None:
        await update.message.reply_text(f"❌ הזן מספר תקין בין {min_v} ל-{max_v}:")
        return None
    await update_user_settings(update.effective_user.id, **{field_name: val})
    await update.message.reply_text(
        f"✅ {label} עודכן: {val}",
    )
    return await settings_handler(update, context)


async def edit_frequency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await _edit_number_field(update, context, "frequency", 0, 60, "תדירות")
    return result if result is not None else EDIT_FREQUENCY


async def edit_dur_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await _edit_number_field(update, context, "duration_start", 1, 30, "משך פתיחה")
    return result if result is not None else EDIT_DUR_START


async def edit_dur_middle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await _edit_number_field(update, context, "duration_middle", 1, 30, "משך אמצע")
    return result if result is not None else EDIT_DUR_MIDDLE


async def edit_dur_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await _edit_number_field(update, context, "duration_end", 1, 30, "משך סיום")
    return result if result is not None else EDIT_DUR_END


def settings_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("settings", settings_handler),
            MessageHandler(filters.Regex("^⚙️ הגדרות$"), settings_handler)
        ],
        states={
            SETTINGS_MENU: [
                CallbackQueryHandler(settings_menu_callback, pattern=r"^(edit_|settings_done)")
            ],
            EDIT_CREDIT_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_credit_text)
            ],
            EDIT_COLOR: [
                CallbackQueryHandler(edit_color_callback, pattern=r"^color_")
            ],
            EDIT_COLOR_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_color_custom)
            ],
            EDIT_FONT: [
                CallbackQueryHandler(edit_font_callback, pattern=r"^font_")
            ],
            EDIT_POSITION: [
                CallbackQueryHandler(edit_position_callback, pattern=r"^position_")
            ],
            EDIT_FREQUENCY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_frequency)
            ],
            EDIT_DUR_START: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_dur_start)
            ],
            EDIT_DUR_MIDDLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_dur_middle)
            ],
            EDIT_DUR_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_dur_end)
            ],
        },
        fallbacks=[
            CommandHandler("settings", settings_handler),
            MessageHandler(filters.Regex("^⚙️ הגדרות$"), settings_handler)
        ],
        name="settings_conversation",
        persistent=False,
    )
