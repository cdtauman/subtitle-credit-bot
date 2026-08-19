"""
פונקציות עזר כלליות
"""

import io
import logging
import os
import re
from typing import Optional

from PIL import Image

logger = logging.getLogger(__name__)


def is_valid_hex_color(color: str) -> bool:
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{6}", color.strip()))


def normalize_hex_color(color: str) -> Optional[str]:
    color = color.strip()
    if not color.startswith("#"):
        color = "#" + color
    return color.upper() if is_valid_hex_color(color) else None


def safe_delete(filepath: str) -> None:
    try:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
            logger.debug("🗑️ נמחק: %s", filepath)
    except Exception as exc:
        logger.warning("⚠️ לא ניתן למחוק %s: %s", filepath, exc)


def safe_int(value: str, min_val: int = 1, max_val: int = 9999) -> Optional[int]:
    try:
        parsed = int(value.strip())
    except (ValueError, AttributeError):
        return None
    return parsed if min_val <= parsed <= max_val else None


def format_user_settings(user) -> str:
    pos_label = "🔼 למעלה" if user.position == "top" else "🔽 למטה"
    fmt_label = getattr(user, "output_format", "srt").upper()
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
    try:
        normalized = normalize_hex_color(hex_color)
        if not normalized:
            raise ValueError("invalid color")
        rgb_color = tuple(int(normalized[i:i + 2], 16) for i in (1, 3, 5))
    except Exception as exc:
        logger.error("שגיאה ביצירת שמונת צבע עבור %s: %s", hex_color, exc)
        rgb_color = (0, 0, 0)

    img = Image.new("RGB", (100, 100), color=rgb_color)
    output = io.BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


def format_user_styling_settings(user) -> str:
    border_label = "צל + גבול 🔳" if user.border_style == 1 else "קופסה אטומה ⬛"
    bold_label = "מודגש (Bold) 🅰️" if getattr(user, "is_bold", 1) == 1 else "רגיל 📄"
    return (
        f"🎨 *הגדרות עיצוב הכתוביות שלך (לפורמט ASS):*\n\n"
        f"📏 גודל גופן: `{user.font_size}`\n"
        f"🔳 סגנון גבול: {border_label}\n"
        f"🅰️ הדגשת גופן: {bold_label}\n"
        f"🎨 צבע גבול: `{user.outline_color}` _(במצב צל + גבול)_\n"
        f"➖ עובי גבול / ריווח קופסה: `{user.outline_width}` פיקסלים\n"
        f"👥 מרחק צל: `{user.shadow_width}` פיקסלים\n"
        f"🎨 צבע צל / קופסה: `{user.bg_color}`\n"
    )


def _ass_color_to_hex(value: str) -> Optional[str]:
    value = value.strip().upper().replace("&", "")
    if value.startswith("H"):
        value = value[1:]
    if not re.fullmatch(r"[0-9A-F]{6,8}", value):
        return normalize_hex_color(value) if value.startswith("#") else None
    bbggrr = value[-6:]
    bb, gg, rr = bbggrr[:2], bbggrr[2:4], bbggrr[4:6]
    return f"#{rr}{gg}{bb}"


def _parse_number(value: str, min_value: int, max_value: int) -> Optional[int]:
    try:
        parsed = int(round(float(value.strip())))
    except (TypeError, ValueError):
        return None
    return parsed if min_value <= parsed <= max_value else None


def _apply_key_value(result: dict, raw_key: str, raw_value: str) -> None:
    key = raw_key.strip().lower()
    value = raw_value.strip()

    if key in ("fontname", "font"):
        if value:
            result["font"] = value
        return

    if key in ("fontsize", "size"):
        parsed = _parse_number(value, 10, 60)
        if parsed is not None:
            result["font_size"] = parsed
        return

    if key == "bold":
        lowered = value.lower()
        if lowered in ("true", "yes", "1", "-1"):
            result["is_bold"] = 1
        elif lowered in ("false", "no", "0"):
            result["is_bold"] = 0
        return

    if key in ("outline", "outlinewidth", "border"):
        parsed = _parse_number(value, 0, 10)
        if parsed is not None:
            result["outline_width"] = parsed
        return

    if key in ("shadow", "shadowwidth", "shadowx", "shadowy"):
        parsed = _parse_number(value, 0, 10)
        if parsed is not None:
            result["shadow_width"] = parsed
        return

    if key == "borderstyle":
        try:
            parsed = int(float(value))
        except ValueError:
            return
        if parsed in (1, 3):
            result["border_style"] = parsed
        return

    color_targets = {
        "primarycolour": "color",
        "primarycolor": "color",
        "colour": "color",
        "color": "color",
        "outlinecolour": "outline_color",
        "outlinecolor": "outline_color",
        "backcolour": "bg_color",
        "backcolor": "bg_color",
        "bgcolor": "bg_color",
    }
    target = color_targets.get(key)
    if target:
        parsed_color = _ass_color_to_hex(value) if value.upper().startswith("&H") else normalize_hex_color(value)
        if parsed_color:
            result[target] = parsed_color


def _parse_ass_style_line(text: str, result: dict) -> bool:
    """Parse a full ASS `Style:` line according to the standard V4+ field order."""
    match = re.search(r"(?:^|\n)\s*Style\s*:\s*(.+)", text, flags=re.IGNORECASE)
    if not match:
        return False
    fields = [part.strip() for part in match.group(1).split(",")]
    if len(fields) < 23:
        return False

    # Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour,
    # BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing,
    # Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    try:
        border_style = int(float(fields[15])) if fields[15] else None
    except ValueError:
        border_style = None

    bold_value = fields[7].strip().lower()
    mapping = {
        "font": fields[1] or None,
        "font_size": _parse_number(fields[2], 10, 60),
        "color": _ass_color_to_hex(fields[3]),
        "outline_color": _ass_color_to_hex(fields[5]),
        "bg_color": _ass_color_to_hex(fields[6]),
        "is_bold": 0 if bold_value in ("0", "false", "no") else 1,
        "border_style": border_style,
        "outline_width": _parse_number(fields[16], 0, 10),
        "shadow_width": _parse_number(fields[17], 0, 10),
    }
    for key, value in mapping.items():
        if value is None:
            continue
        if key == "border_style" and value not in (1, 3):
            continue
        result[key] = value
    return True


def parse_style_string(text: str) -> dict:
    """
    מנתח שורת ASS מלאה, force_style או רשימת Key=Value ומחזיר רק ערכים תקינים.
    """
    result: dict = {}
    text = (text or "").strip()
    if not text:
        return result

    _parse_ass_style_line(text, result)

    # תומך גם ב-force_style='FontName=...,Fontsize=...' ובערכים עשרוניים/שליליים.
    pair_pattern = re.compile(
        r"(\w+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^,\s]+))",
        flags=re.IGNORECASE,
    )

    def parse_pairs(value: str) -> None:
        for match in pair_pattern.finditer(value):
            key = match.group(1)
            parsed_value = match.group(2) or match.group(3) or match.group(4) or ""
            if key.lower() in ("force_style", "style", "command", "vf") and "=" in parsed_value:
                parse_pairs(parsed_value)
            else:
                _apply_key_value(result, key, parsed_value)

    parse_pairs(text)
    return result
