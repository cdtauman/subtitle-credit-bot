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


def parse_style_string(text: str) -> dict:
    """
    מנתח שורת הגדרות סגנון (או פקודת FFmpeg) ומחזיר מילון של פרמטרים שזוהו.
    למשל: FontName=Assistant,Fontsize=23,Bold=1,Shadow=0.1
    """
    import re
    result = {}
    
    # תבנית של מפתח=ערך (תומך גם ברווחים ומירכאות)
    pattern = re.compile(r'(\w+)\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^,\'"\s]+))')
    
    def parse_inner(text_to_parse):
        matches = pattern.findall(text_to_parse)
        for match in matches:
            raw_key = match[0].lower()
            val = match[1] or match[2] or match[3]
            if not val:
                continue
            val = val.strip()
            
            # אם הערך הוא בעצמו תת-מערך של מפתח=ערך (כמו force_style='...'), ננתח אותו רקורסיבית
            if "=" in val and raw_key in ("force_style", "style", "command", "vf"):
                parse_inner(val)
                continue
                
            # מיפוי פונט
            if raw_key in ("fontname", "font"):
                result["font"] = val
                
            # גודל גופן
            elif raw_key in ("fontsize", "size"):
                try:
                    clean_val = re.sub(r'[^\d]', '', val)
                    if clean_val:
                        result["font_size"] = int(clean_val)
                except ValueError:
                    pass
                    
            # הדגשה (Bold)
            elif raw_key == "bold":
                try:
                    if val.lower() in ("true", "1", "yes"):
                        result["is_bold"] = 1
                    elif val.lower() in ("false", "0", "no"):
                        result["is_bold"] = 0
                except ValueError:
                    pass
                    
            # גבול (Outline)
            elif raw_key in ("outline", "outlinewidth", "border"):
                try:
                    clean_val = re.sub(r'[^\d]', '', val)
                    if clean_val:
                        result["outline_width"] = int(clean_val)
                except ValueError:
                    pass
                    
            # צל (Shadow)
            elif raw_key in ("shadow", "shadowwidth", "shadowx", "shadowy"):
                try:
                    f_val = float(val)
                    result["shadow_width"] = int(round(f_val))
                except ValueError:
                    pass
                    
            # סגנון גבול (BorderStyle)
            elif raw_key in ("borderstyle", "style"):
                try:
                    clean_val = re.sub(r'[^\d]', '', val)
                    if clean_val:
                        result["border_style"] = int(clean_val)
                except ValueError:
                    pass
                    
            # צבעים
            elif raw_key in ("primarycolour", "colour", "color"):
                if val.startswith("&H"):
                    hex_clean = val.replace("&H", "").replace("&", "")
                    if len(hex_clean) >= 6:
                        bb = hex_clean[-6:-4]
                        gg = hex_clean[-4:-2]
                        rr = hex_clean[-2:]
                        result["color"] = f"#{rr}{gg}{bb}"
                elif val.startswith("#"):
                    result["color"] = val
                    
            elif raw_key == "outlinecolour":
                if val.startswith("&H"):
                    hex_clean = val.replace("&H", "").replace("&", "")
                    if len(hex_clean) >= 6:
                        bb = hex_clean[-6:-4]
                        gg = hex_clean[-4:-2]
                        rr = hex_clean[-2:]
                        result["outline_color"] = f"#{rr}{gg}{bb}"
                elif val.startswith("#"):
                    result["outline_color"] = val
                    
            elif raw_key in ("backcolour", "bgcolor"):
                if val.startswith("&H"):
                    hex_clean = val.replace("&H", "").replace("&", "")
                    if len(hex_clean) >= 6:
                        bb = hex_clean[-6:-4]
                        gg = hex_clean[-4:-2]
                        rr = hex_clean[-2:]
                        result["bg_color"] = f"#{rr}{gg}{bb}"
                elif val.startswith("#"):
                    result["bg_color"] = val

    parse_inner(text)
    return result

