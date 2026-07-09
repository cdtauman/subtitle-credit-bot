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
    format_keyboard,
    subtitle_styling_keyboard,
    border_style_keyboard,
    bold_keyboard,
)
from utils.helpers import (
    normalize_hex_color,
    safe_int,
    format_user_settings,
    create_color_image,
    format_user_styling_settings,
    parse_style_string,
)
from services.preview_generator import generate_subtitle_preview

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
    EDIT_OUTPUT_FORMAT,
    # הגדרות עיצוב כתוביות (ASS)
    SUBMENU_STYLING,
    EDIT_FONT_SIZE,
    EDIT_BORDER_STYLE,
    EDIT_OUTLINE_COLOR,
    EDIT_OUTLINE_COLOR_CUSTOM,
    EDIT_OUTLINE_WIDTH,
    EDIT_SHADOW_WIDTH,
    EDIT_BG_COLOR,
    EDIT_BG_COLOR_CUSTOM,
    EDIT_IS_BOLD,
    EDIT_IMPORT,
) = range(100, 122)


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

    if action == "submenu_styling":
        return await submenu_styling_handler(update, context)

    prompts = {
        "edit_credit_text": ("📝 הזן טקסט קרדיט חדש:", EDIT_CREDIT_TEXT),
        "edit_color": ("🎨 בחר צבע חדש:", EDIT_COLOR),
        "edit_font": ("🔤 בחר גופן חדש:", EDIT_FONT),
        "edit_position": ("📍 בחר מיקום חדש:", EDIT_POSITION),
        "edit_frequency": ("⏱️ הזן תדירות חדשה (דקות, 0-60). 0 = ללא קרדיט אמצע:", EDIT_FREQUENCY),
        "edit_dur_start": ("⏳ הזן משך קרדיט פתיחה (שניות, 1-30):", EDIT_DUR_START),
        "edit_dur_middle": ("⏳ הזן משך קרדיט אמצע (שניות, 1-30):", EDIT_DUR_MIDDLE),
        "edit_dur_end": ("⏳ הזן משך קרדיט סיום (שניות, 1-30):", EDIT_DUR_END),
        "edit_output_format": ("📁 בחר פורמט קובץ פלט חדש:", EDIT_OUTPUT_FORMAT),
        "style_import": (
            "📥 *ייבוא הגדרות עיצוב (Import Settings)*\n\n"
            "שלח לי את שורת הסגנון של ה-ASS או את פקודת ה-FFmpeg המכילה את סגנון ה-`force_style`:\n"
            "*(למשל: FontName=Assistant,Fontsize=23,Bold=1,Shadow=0.1)*",
            EDIT_IMPORT
        ),
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
    elif action == "edit_output_format":
        await query.edit_message_text(prompt, reply_markup=format_keyboard())
        return EDIT_OUTPUT_FORMAT
    else:
        # style_import prompt needs markdown parsing
        if action == "style_import":
            await query.edit_message_text(prompt, parse_mode="Markdown")
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


async def edit_output_format_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    fmt = query.data.replace("format_", "")
    await update_user_settings(update.effective_user.id, output_format=fmt)
    return await settings_handler(update, context)


async def submenu_styling_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """כניסה לתפריט משנה עיצוב כתוביות"""
    user_id = update.effective_user.id
    query = update.callback_query
    message = update.message
    if not message and query:
        message = query.message
        
    db_user = await get_user(user_id)
    text = format_user_styling_settings(db_user)
    
    if query:
        try:
            await query.edit_message_text(
                text + "\n\n*בחר מה לערוך בעיצוב:*",
                parse_mode="Markdown",
                reply_markup=subtitle_styling_keyboard(),
            )
        except Exception:
            await message.reply_text(
                text + "\n\n*בחר מה לערוך בעיצוב:*",
                parse_mode="Markdown",
                reply_markup=subtitle_styling_keyboard(),
            )
    else:
        await message.reply_text(
            text + "\n\n*בחר מה לערוך בעיצוב:*",
            parse_mode="Markdown",
            reply_markup=subtitle_styling_keyboard(),
        )
    return SUBMENU_STYLING


async def submenu_styling_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    
    if action == "style_back_to_settings":
        return await settings_handler(update, context)
        
    if action == "style_preview":
        user_id = update.effective_user.id
        db_user = await get_user(user_id)
        status_msg = await query.message.reply_text("⏳ מייצר תצוגה מקדימה...")
        
        preview_text = db_user.credit_text or "הבוט מעצב כתוביות בעברית!"
        try:
            preview_image = generate_subtitle_preview(
                text=preview_text,
                font_name=db_user.font,
                font_size=db_user.font_size,
                color_hex=db_user.color,
                border_style=db_user.border_style,
                outline_color_hex=db_user.outline_color,
                outline_width=db_user.outline_width,
                shadow_width=db_user.shadow_width,
                bg_color_hex=db_user.bg_color,
                is_bold=db_user.is_bold,
                position=db_user.position
            )
            await query.message.reply_photo(
                photo=preview_image,
                caption="🔍 *תצוגה מקדימה של הכתוביות שלך:*",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Failed to generate styling preview: {e}", exc_info=True)
            await query.message.reply_text("❌ אירעה שגיאה בייצור התצוגה המקדימה.")
        finally:
            await status_msg.delete()
        return await submenu_styling_handler(update, context)

    prompts = {
        "style_font_size": ("📏 הזן גודל גופן חדש (מספר שלם בין 10 ל-60):", EDIT_FONT_SIZE),
        "style_border_style": ("🔳 בחר סגנון גבול:", EDIT_BORDER_STYLE),
        "style_is_bold": ("🅰️ בחר הדגשת גופן (Bold):", EDIT_IS_BOLD),
        "style_outline_color": ("🎨 בחר צבע גבול / קופסה חדש:", EDIT_OUTLINE_COLOR),
        "style_outline_width": ("➖ הזן עובי גבול (מספר שלם בין 0 ל-10):", EDIT_OUTLINE_WIDTH),
        "style_shadow_width": ("👥 הזן מרחק צל (מספר שלם בין 0 ל-10):", EDIT_SHADOW_WIDTH),
        "style_bg_color": ("🎨 בחר צבע צל / רקע חדש:", EDIT_BG_COLOR),
    }
    
    if action not in prompts:
        return SUBMENU_STYLING
        
    prompt, state = prompts[action]
    
    if action == "style_border_style":
        await query.edit_message_text(prompt, reply_markup=border_style_keyboard())
        return EDIT_BORDER_STYLE
    elif action == "style_is_bold":
        await query.edit_message_text(prompt, reply_markup=bold_keyboard())
        return EDIT_IS_BOLD
    elif action in ("style_outline_color", "style_bg_color"):
        await query.edit_message_text(prompt, reply_markup=color_keyboard())
        return state
    else:
        await query.edit_message_text(prompt)
        return state


async def edit_font_size(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = safe_int(update.message.text, min_val=10, max_val=60)
    if val is None:
        await update.message.reply_text("❌ הזן מספר שלם תקין בין 10 ל-60:")
        return EDIT_FONT_SIZE
    await update_user_settings(update.effective_user.id, font_size=val)
    await update.message.reply_text(f"✅ גודל גופן עודכן ל-{val}")
    return await submenu_styling_handler(update, context)


async def edit_border_style_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    val = int(query.data.replace("border_style_", ""))
    await update_user_settings(update.effective_user.id, border_style=val)
    label = "צל + גבול" if val == 1 else "קופסה כהה"
    await query.message.reply_text(f"✅ סגנון גבול עודכן ל: {label}")
    return await submenu_styling_handler(update, context)


async def edit_is_bold_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    val = int(query.data.replace("bold_", ""))
    await update_user_settings(update.effective_user.id, is_bold=val)
    label = "מודגש (Bold)" if val == 1 else "רגיל"
    await query.message.reply_text(f"✅ סגנון הדגשת גופן עודכן ל: {label}")
    return await submenu_styling_handler(update, context)


async def edit_import_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ הטקסט לא תקין. נסה שוב:")
        return EDIT_IMPORT
        
    parsed = parse_style_string(text)
    if not parsed:
        await update.message.reply_text(
            "❌ לא זוהו הגדרות תקינות בטקסט ששלחת.\n"
            "ודא ששלחת טקסט המכיל הגדרות בפורמט `Key=Value` (למשל: `FontName=Assistant,Fontsize=23...`) ונסה שוב:"
        )
        return EDIT_IMPORT
        
    user_id = update.effective_user.id
    await update_user_settings(user_id, **parsed)
    
    labels = {
        "font": "🔤 גופן",
        "font_size": "📏 גודל גופן",
        "is_bold": "🅰️ הדגשה",
        "outline_width": "➖ עובי גבול",
        "shadow_width": "👥 מרחק צל",
        "border_style": "🔳 סגנון גבול",
        "color": "🎨 צבע ראשי",
        "outline_color": "🎨 צבע גבול/קופסה",
        "bg_color": "🎨 צבע רקע/צל"
    }
    
    lines = []
    for k, v in parsed.items():
        label = labels.get(k, k)
        if k == "is_bold":
            val_str = "מודגש (Bold)" if v == 1 else "רגיל"
        elif k == "border_style":
            val_str = "צל + גבול" if v == 1 else "קופסה כהה"
        else:
            val_str = str(v)
        lines.append(f"- *{label}:* `{val_str}`")
        
    await update.message.reply_text(
        f"✅ *ההגדרות יובאו ועודכנו בהצלחה!*\n\n" + "\n".join(lines),
        parse_mode="Markdown"
    )
    return await settings_handler(update, context)


async def edit_outline_color_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "color_custom":
        await query.edit_message_text("✏️ הזן קוד צבע HEX עבור הגבול (למשל #000000):")
        return EDIT_OUTLINE_COLOR_CUSTOM
    color = query.data.replace("color_", "")
    await update_user_settings(update.effective_user.id, outline_color=color)
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע גבול עודכן ל: `{color}`",
        parse_mode="Markdown"
    )
    return await submenu_styling_handler(update, context)


async def edit_outline_color_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    color = normalize_hex_color(update.message.text)
    if not color:
        await update.message.reply_text("❌ קוד HEX לא תקין. הזן בפורמט #RRGGBB:")
        return EDIT_OUTLINE_COLOR_CUSTOM
    await update_user_settings(update.effective_user.id, outline_color=color)
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע גבול עודכן ל: `{color}`",
        parse_mode="Markdown"
    )
    return await submenu_styling_handler(update, context)


async def edit_outline_width(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = safe_int(update.message.text, min_val=0, max_val=10)
    if val is None:
        await update.message.reply_text("❌ הזן מספר שלם תקין בין 0 ל-10:")
        return EDIT_OUTLINE_WIDTH
    await update_user_settings(update.effective_user.id, outline_width=val)
    await update.message.reply_text(f"✅ עובי גבול עודכן ל-{val} פיקסלים")
    return await submenu_styling_handler(update, context)


async def edit_shadow_width(update: Update, context: ContextTypes.DEFAULT_TYPE):
    val = safe_int(update.message.text, min_val=0, max_val=10)
    if val is None:
        await update.message.reply_text("❌ הזן מספר שלם תקין בין 0 ל-10:")
        return EDIT_SHADOW_WIDTH
    await update_user_settings(update.effective_user.id, shadow_width=val)
    await update.message.reply_text(f"✅ מרחק צל עודכן ל-{val} פיקסלים")
    return await submenu_styling_handler(update, context)


async def edit_bg_color_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "color_custom":
        await query.edit_message_text("✏️ הזן קוד צבע HEX עבור הרקע/הצל (למשל #000000):")
        return EDIT_BG_COLOR_CUSTOM
    color = query.data.replace("color_", "")
    await update_user_settings(update.effective_user.id, bg_color=color)
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע רקע עודכן ל: `{color}`",
        parse_mode="Markdown"
    )
    return await submenu_styling_handler(update, context)


async def edit_bg_color_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    color = normalize_hex_color(update.message.text)
    if not color:
        await update.message.reply_text("❌ קוד HEX לא תקין. הזן בפורמט #RRGGBB:")
        return EDIT_BG_COLOR_CUSTOM
    await update_user_settings(update.effective_user.id, bg_color=color)
    
    color_image = create_color_image(color)
    await query.message.reply_photo(
        photo=color_image,
        caption=f"✅ צבע רקע עודכן ל: `{color}`",
        parse_mode="Markdown"
    )
    return await submenu_styling_handler(update, context)


def settings_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("settings", settings_handler),
            MessageHandler(filters.Regex("^⚙️ הגדרות$"), settings_handler)
        ],
        states={
            SETTINGS_MENU: [
                CallbackQueryHandler(settings_menu_callback, pattern=r"^(edit_|settings_done|submenu_styling|style_)")
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
            EDIT_OUTPUT_FORMAT: [
                CallbackQueryHandler(edit_output_format_callback, pattern=r"^format_")
            ],
            SUBMENU_STYLING: [
                CallbackQueryHandler(submenu_styling_callback, pattern=r"^(style_)")
            ],
            EDIT_FONT_SIZE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_font_size)
            ],
            EDIT_BORDER_STYLE: [
                CallbackQueryHandler(edit_border_style_callback, pattern=r"^border_style_")
            ],
            EDIT_OUTLINE_COLOR: [
                CallbackQueryHandler(edit_outline_color_callback, pattern=r"^color_")
            ],
            EDIT_OUTLINE_COLOR_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_outline_color_custom)
            ],
            EDIT_OUTLINE_WIDTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_outline_width)
            ],
            EDIT_SHADOW_WIDTH: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_shadow_width)
            ],
            EDIT_BG_COLOR: [
                CallbackQueryHandler(edit_bg_color_callback, pattern=r"^color_")
            ],
            EDIT_BG_COLOR_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_bg_color_custom)
            ],
            EDIT_IS_BOLD: [
                CallbackQueryHandler(edit_is_bold_callback, pattern=r"^bold_")
            ],
            EDIT_IMPORT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_import_callback)
            ],
        },
        fallbacks=[
            CommandHandler("settings", settings_handler),
            MessageHandler(filters.Regex("^⚙️ הגדרות$"), settings_handler)
        ],
        name="settings_conversation",
        persistent=False,
    )
