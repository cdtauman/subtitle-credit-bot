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
        [InlineKeyboardButton("⏱️ תדירות (דקות)", callback_data="edit_frequency")],
        [InlineKeyboardButton("⏳ משך התחלה (שניות)", callback_data="edit_dur_start")],
        [InlineKeyboardButton("⏳ משך אמצע (שניות)", callback_data="edit_dur_middle")],
        [InlineKeyboardButton("⏳ משך סוף (שניות)", callback_data="edit_dur_end")],
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
