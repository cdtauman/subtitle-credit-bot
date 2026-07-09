"""
פונקציות עזר כלליות
"""

import os
import re
import logging
from typing import Optional
from PIL import Image, ImageDraw
import io

logger = logging.getLogger(__name__)


def is_valid_hex_color(color: str) -> bool:
    """בדיקת תקינות קוד צבע HEX"""
    return bool(re.match(r'^#([0-9A-Fa-f]{6})$', color.strip()))


def normalize_hex_color(color: str) -> Optional[str]:
    """נרמול קוד צבע - הוספת # אם חסר"""
    color = color.strip()
    if not color.startswith("#"):
        color = "#" + color
    if is_valid_hex_color(color):
        return color.upper()
    return None


def safe_delete(filepath: str) -> None:
    """מחיקה בטוחה של קובץ"""
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.debug(f"🗑️ נמחק: {filepath}")
    except Exception as e:
        logger.warning(f"⚠️ לא ניתן למחוק {filepath}: {e}")


def safe_int(value: str, min_val: int = 1, max_val: int = 9999) -> Optional[int]:
    """המרה בטוחה למספר שלם עם בדיקת טווח"""
    try:
        v = int(value.strip())
        if min_val <= v <= max_val:
            return v
        return None
    except (ValueError, AttributeError):
        return None


def format_user_settings(user) -> str:
    """פורמט הגדרות משתמש להצגה"""
    pos_label = "🔼 למעלה" if user.position == "top" else "🔽 למטה"
    fmt_label = user.output_format.upper() if hasattr(user, 'output_format') else "SRT"
    return (
        f"📋 *ההגדרות הנוכחיות שלך:*\n\n"
        f"📝 טקסט: `{user.credit_text or 'לא הוגדר'}`\n"
        f"🎨 צבע: `{user.color}`\n"
        f"🔤 גופן: `{user.font}`\n"
        f"📍 מיקום: {pos_label}\n"
        f"📁 פורמט פלט: `{fmt_label}`\n"
        f"⏱️ תדירות: כל `{user.frequency}` דקות\n"
        f"⏳ משך התחלה: `{user.duration_start}` שניות\n"
        f"⏳ משך אמצע: `{user.duration_middle}` שניות\n"
        f"⏳ משך סוף: `{user.duration_end}` שניות\n"
    )


def create_color_image(hex_color: str) -> io.BytesIO:
    """יוצר תמונה קטנה של ריבוע בצבע הנתון ומחזיר אותה כ-BytesIO"""
    try:
        # הסרת # אם קיים והמרת ל-RGB
        hex_color = hex_color.lstrip('#')
        rgb_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        img = Image.new('RGB', (100, 100), color = rgb_color)
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr
    except Exception as e:
        logger.error(f"שגיאה ביצירת תמונת צבע עבור {hex_color}: {e}")
        # במקרה של שגיאה, נחזיר תמונה שחורה
        img = Image.new('RGB', (100, 100), color = (0, 0, 0))
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        return img_byte_arr


def format_user_styling_settings(user) -> str:
    """פורמט הגדרות עיצוב כתוביות להצגה"""
    border_label = "צל + גבול 🔳" if user.border_style == 1 else "קופסה כהה ⬛"
    bold_label = "מודגש (Bold) 🅰️" if getattr(user, "is_bold", 1) == 1 else "רגיל 📄"
    return (
        f"🎨 *הגדרות עיצוב הכתוביות שלך (לפורמט ASS):*\n\n"
        f"📏 גודל גופן: `{user.font_size}`\n"
        f"🔳 סגנון גבול: {border_label}\n"
        f"🅰️ הדגשת גופן: {bold_label}\n"
        f"🎨 צבע גבול/קופסה: `{user.outline_color}`\n"
        f"➖ עובי גבול: `{user.outline_width}` פיקסלים\n"
        f"👥 מרחק צל: `{user.shadow_width}` פיקסלים\n"
        f"🎨 צבע צל/רקע: `{user.bg_color}`\n"
    )
