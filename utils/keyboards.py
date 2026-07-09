"""
מקלדות ותפריטים לבוט
"""

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from config import AVAILABLE_FONTS, QUICK_COLORS


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """תפריט ראשי קבוע"""
    keyboard = [
        ["🎬 קרדיט מותאם אישית", "⚙️ הגדרות"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def color_keyboard() -> InlineKeyboardMarkup:
    """מקלדת בחירת צבע"""
    buttons = []
    row = []
    for label, hex_val in QUICK_COLORS.items():
        row.append(InlineKeyboardButton(label, callback_data=f"color_{hex_val}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("✏️ הזן קוד HEX מותאם", callback_data="color_custom")])
    return InlineKeyboardMarkup(buttons)


def font_keyboard() -> InlineKeyboardMarkup:
    """מקלדת בחירת גופן"""
    buttons = [
        [InlineKeyboardButton(font, callback_data=f"font_{font}")]
        for font in AVAILABLE_FONTS
    ]
    return InlineKeyboardMarkup(buttons)


def position_keyboard() -> InlineKeyboardMarkup:
    """מקלדת בחירת מיקום"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔼 למעלה", callback_data="position_top"),
            InlineKeyboardButton("🔽 למטה", callback_data="position_bottom"),
        ]
    ])


def admin_approval_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """מקלדת אישור/דחייה למנהל"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ אשר", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton("❌ דחה", callback_data=f"reject_{user_id}"),
        ]
    ])


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    """תפריט עריכת הגדרות"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 טקסט קרדיט", callback_data="edit_credit_text")],
        [InlineKeyboardButton("🎨 צבע", callback_data="edit_color")],
        [InlineKeyboardButton("🔤 גופן", callback_data="edit_font")],
        [InlineKeyboardButton("📍 מיקום", callback_data="edit_position")],
        [InlineKeyboardButton("📁 פורמט קובץ פלט", callback_data="edit_output_format")],
        [InlineKeyboardButton("⏱️ תדירות (דקות)", callback_data="edit_frequency")],
        [InlineKeyboardButton("⏳ משך התחלה (שניות)", callback_data="edit_dur_start")],
        [InlineKeyboardButton("⏳ משך אמצע (שניות)", callback_data="edit_dur_middle")],
        [InlineKeyboardButton("⏳ משך סוף (שניות)", callback_data="edit_dur_end")],
        [InlineKeyboardButton("🎬 עיצוב כתוביות (פלט ASS)", callback_data="submenu_styling")],
        [InlineKeyboardButton("✅ סיום", callback_data="settings_done")],
    ])


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    """תפריט פאנל ניהול"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 סטטיסטיקות", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 רשימת משתמשים", callback_data="admin_users")],
        [InlineKeyboardButton("🗣️ שידור הודעה", callback_data="admin_broadcast")],
        [InlineKeyboardButton("➕ הוספת משתמש", callback_data="admin_add_user")],
        [InlineKeyboardButton("🔙 חזרה לתפריט הראשי", callback_data="admin_back_to_main")],
    ])


def format_keyboard() -> InlineKeyboardMarkup:
    """מקלדת בחירת פורמט קובץ פלט"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("SRT (.srt)", callback_data="format_srt"),
            InlineKeyboardButton("ASS (.ass)", callback_data="format_ass"),
            InlineKeyboardButton("VTT (.vtt)", callback_data="format_vtt"),
        ]
    ])


def subtitle_styling_keyboard() -> InlineKeyboardMarkup:
    """מקלדת לתפריט משנה עיצוב כתוביות"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📏 גודל גופן", callback_data="style_font_size")],
        [InlineKeyboardButton("🔳 סגנון גבול", callback_data="style_border_style")],
        [InlineKeyboardButton("🅰️ הדגשת גופן (Bold)", callback_data="style_is_bold")],
        [InlineKeyboardButton("🎨 צבע גבול / קופסה", callback_data="style_outline_color")],
        [InlineKeyboardButton("➖ עובי גבול", callback_data="style_outline_width")],
        [InlineKeyboardButton("👥 מרחק צל", callback_data="style_shadow_width")],
        [InlineKeyboardButton("🎨 צבע צל / רקע", callback_data="style_bg_color")],
        [InlineKeyboardButton("🔍 תצוגה מקדימה (Preview)", callback_data="style_preview")],
        [InlineKeyboardButton("🔙 חזרה להגדרות ראשיות", callback_data="style_back_to_settings")],
    ])


def bold_keyboard() -> InlineKeyboardMarkup:
    """מקלדת בחירת הדגשה"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("מודגש (Bold) 🅰️", callback_data="bold_1"),
            InlineKeyboardButton("רגיל (Regular) 📄", callback_data="bold_0"),
        ]
    ])


def border_style_keyboard() -> InlineKeyboardMarkup:
    """מקלדת בחירת סגנון גבול"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("צל + גבול 🔳", callback_data="border_style_1"),
            InlineKeyboardButton("קופסה כהה ⬛", callback_data="border_style_3"),
        ]
    ])


def custom_start_keyboard() -> InlineKeyboardMarkup:
    """מקלדת לתחילת עבודה חד-פעמית - שימוש בברירות מחדל או ידני"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚙️ להשתמש בברירת מחדל", callback_data="custom_start_default"),
            InlineKeyboardButton("✏️ להגדיר ידנית", callback_data="custom_start_manual"),
        ]
    ])


def custom_styling_ask_keyboard() -> InlineKeyboardMarkup:
    """מקלדת לשאלה האם להגדיר עיצוב מתקדם"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎨 כן, לעצב", callback_data="custom_styling_yes"),
            InlineKeyboardButton("⏭️ לא, לדלג", callback_data="custom_styling_skip"),
        ]
    ])
