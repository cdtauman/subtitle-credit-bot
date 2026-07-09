"""
שירות עיבוד כתוביות SRT
הלוגיקה המרכזית של הבוט
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import timedelta

logger = logging.getLogger(__name__)


@dataclass
class SRTBlock:
    index: int
    start: timedelta
    end: timedelta
    text: str
    raw_position: str = ""  # תגית מיקום מקורית אם קיימת


@dataclass
class CreditSettings:
    credit_text: str
    color: str
    font: str
    position: str           # "top" / "bottom"
    frequency: int          # דקות
    duration_start: int     # שניות
    duration_middle: int    # שניות
    duration_end: int       # שניות
    output_format: str = "srt"  # "srt" / "ass" / "vtt"
    # עיצוב כתוביות מתקדם (ASS)
    font_size: int = 20
    border_style: int = 1
    outline_color: str = "#000000"
    outline_width: int = 2
    shadow_width: int = 2
    bg_color: str = "#000000"
    is_bold: int = 1


def _td_to_srt_time(td: timedelta) -> str:
    """המרת timedelta לפורמט SRT: HH:MM:SS,mmm"""
    total_seconds = int(td.total_seconds())
    millis = int((td.total_seconds() - total_seconds) * 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def _srt_time_to_td(time_str: str) -> timedelta:
    """המרת פורמט SRT לtimedelta"""
    time_str = time_str.strip().replace(",", ".")
    parts = time_str.split(":")
    hours = int(parts[0])
    minutes = int(parts[1])
    sec_parts = parts[2].split(".")
    seconds = int(sec_parts[0])
    millis = int(sec_parts[1]) if len(sec_parts) > 1 else 0
    return timedelta(hours=hours, minutes=minutes, seconds=seconds, milliseconds=millis)


def _build_credit_text(text: str, color: str, font: str, position: str) -> str:
    """בניית שורת קרדיט עם תגיות עיצוב"""
    position_tag = "{\\an8}" if position == "top" else ""
    styled = f'<font color="{color}" face="{font}">{text}</font>'
    return f"{position_tag}{styled}"


def parse_srt(content: str) -> List[SRTBlock]:
    """פרסור קובץ SRT למבנה נתונים"""
    blocks = []
    # ניקוי BOM ו-whitespace
    content = content.lstrip("\ufeff").strip()
    # פיצול לבלוקים
    pattern = re.compile(
        r'(\d+)\s*\n'
        r'(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*\n'
        r'([\s\S]*?)(?=\n\s*\n\d+\s*\n|\Z)',
        re.MULTILINE
    )
    for match in pattern.finditer(content):
        index = int(match.group(1))
        start = _srt_time_to_td(match.group(2))
        end = _srt_time_to_td(match.group(3))
        text = match.group(4).strip()
        blocks.append(SRTBlock(index=index, start=start, end=end, text=text))
    return blocks


def _existing_subtitles_at_bottom(blocks: List[SRTBlock]) -> bool:
    """בדיקה האם הכתוביות המקוריות נמצאות בתחתית (ברירת מחדל)"""
    for block in blocks:
        if "{\\an8}" in block.text or "{\\an7}" in block.text or "{\\an9}" in block.text:
            return False  # כתוביות בחלק העליון
    return True  # כתוביות בחלק התחתון (ברירת מחדל)


def _find_free_window(
    desired_start: timedelta,
    duration: timedelta,
    existing_blocks: List[SRTBlock],
    position: str,
    existing_at_bottom: bool,
    max_shift: timedelta = timedelta(seconds=30),
) -> Optional[Tuple[timedelta, timedelta]]:
    """
    מציאת חלון זמן פנוי לקרדיט.
    מחזיר (start, end) או None אם לא נמצא חלון מתאים.
    
    תלוית-מיקום: אם הקרדיט בחלק אחר מהכתוביות, מאפשרים חפיפה.
    """
    # אם הקרדיט למעלה והכתוביות למטה - אין התנגשות אפשרית
    if position == "top" and existing_at_bottom:
        return (desired_start, desired_start + duration)
    # אם הקרדיט למטה והכתוביות למעלה - אין התנגשות אפשרית
    if position == "bottom" and not existing_at_bottom:
        return (desired_start, desired_start + duration)

    # בדיקת התנגשויות ועדכון חלון
    current_start = desired_start
    attempts = 0
    max_attempts = 60

    while attempts < max_attempts:
        current_end = current_start + duration
        collision = False

        for block in existing_blocks:
            # בדיקת חפיפה
            if current_start < block.end and current_end > block.start:
                # הזזה קדימה לאחר סיום הכתובית הקיימת
                current_start = block.end + timedelta(milliseconds=100)
                collision = True
                break

        if not collision:
            # בדיקה שלא חרגנו יותר מדי מהזמן המקורי
            if current_start - desired_start <= max_shift:
                return (current_start, current_start + duration)
            else:
                return None

        attempts += 1

    return None


def process_srt(content: str, settings: CreditSettings) -> str:
    """
    עיבוד ראשי של קובץ SRT - הוספת קרדיטים
    מחזיר תוכן SRT מעובד
    """
    blocks = parse_srt(content)
    if not blocks:
        raise ValueError("לא נמצאו כתוביות תקינות בקובץ")

    existing_at_bottom = _existing_subtitles_at_bottom(blocks)
    credit_formatted = _build_credit_text(
        settings.credit_text, settings.color, settings.font, settings.position
    )

    # קביעת זמן כולל בסרט
    total_end = blocks[-1].end
    # שתי הכתוביות האחרונות - הקרדיט האחרון חייב להסתיים לפניהן
    last_two_start = blocks[-2].start if len(blocks) >= 2 else blocks[-1].start

    new_credit_blocks: List[SRTBlock] = []

    # ---- 1. קרדיט פתיחה ----
    start_begin = timedelta(seconds=0)
    start_dur = timedelta(seconds=settings.duration_start)
    window = _find_free_window(
        start_begin, start_dur, blocks, settings.position, existing_at_bottom
    )
    if window:
        new_credit_blocks.append(SRTBlock(
            index=0, start=window[0], end=window[1], text=credit_formatted
        ))

    # ---- 2. קרדיטים אמצע ----
    if settings.frequency > 0:
        freq_td = timedelta(minutes=settings.frequency)
        middle_dur = timedelta(seconds=settings.duration_middle)
        current_time = timedelta(minutes=settings.frequency)
        
        # גבול עליון לקרדיט אמצע: לא להציג בפרק הזמן של התדירות לפני הסוף
        middle_credits_limit = total_end - freq_td

        while current_time < middle_credits_limit:
            # לא להציג קרדיט אמצע בזמן שכבר יש קרדיט פתיחה
            if new_credit_blocks and current_time < new_credit_blocks[0].end + timedelta(seconds=30):
                current_time += freq_td
                continue

            window = _find_free_window(
                current_time, middle_dur, blocks, settings.position, existing_at_bottom
            )
            if window:
                new_credit_blocks.append(SRTBlock(
                    index=0, start=window[0], end=window[1], text=credit_formatted
                ))

            current_time += freq_td

    # ---- 3. קרדיט סיום ----
    end_dur = timedelta(seconds=settings.duration_end)
    # הקרדיט האחרון - לפני שתי הכתוביות האחרונות
    end_target = last_two_start - end_dur - timedelta(seconds=2)

    if end_target > timedelta(0):
        window = _find_free_window(
            end_target, end_dur, blocks, settings.position, existing_at_bottom,
            max_shift=timedelta(seconds=60)
        )
        if window and window[1] < last_two_start:
            # בדיקה שאין קרדיט אמצע שצמוד מדי
            is_too_close = False
            for b in new_credit_blocks:
                if b.end > window[0] - timedelta(seconds=30):
                    is_too_close = True
                    break
            if not is_too_close:
                new_credit_blocks.append(SRTBlock(
                    index=0, start=window[0], end=window[1], text=credit_formatted
                ))

    # ---- מיזוג כל הבלוקים וממיין לפי זמן ----
    all_blocks = blocks + new_credit_blocks
    all_blocks.sort(key=lambda b: b.start)

    # מספור מחדש
    for i, block in enumerate(all_blocks, start=1):
        block.index = i

    fmt = settings.output_format.lower()
    if fmt == "ass":
        return _serialize_ass(all_blocks, settings)
    elif fmt == "vtt":
        return _serialize_vtt(all_blocks)
    else:
        return _serialize_srt(all_blocks)


def _serialize_srt(blocks: List[SRTBlock]) -> str:
    """המרת רשימת בלוקים לטקסט SRT"""
    lines = []
    for block in blocks:
        lines.append(str(block.index))
        lines.append(f"{_td_to_srt_time(block.start)} --> {_td_to_srt_time(block.end)}")
        lines.append(block.text)
        lines.append("")
    return "\n".join(lines)


def _td_to_vtt_time(td: timedelta) -> str:
    """המרת timedelta לפורמט WebVTT: HH:MM:SS.mmm"""
    total_seconds = int(td.total_seconds())
    millis = int((td.total_seconds() - total_seconds) * 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _td_to_ass_time(td: timedelta) -> str:
    """המרת timedelta לפורמט ASS: H:MM:SS.cs"""
    total_seconds = int(td.total_seconds())
    centiseconds = int((td.total_seconds() - total_seconds) * 100)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def _hex_to_ass_color(hex_color: str) -> str:
    """המרת קוד צבע HEX RGB ל-BGR של ASS"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H{b}{g}{r}&"
    return "&HFFFFFF&"


def _convert_html_to_ass(text: str, settings: CreditSettings) -> str:
    """המרת תגיות HTML בסיסיות לפורמט תגיות ASS"""
    # המרת תגיות פונט
    def replace_font(match):
        color_val = match.group(1)
        font_val = match.group(2)
        inner_text = match.group(3)
        ass_color = _hex_to_ass_color(color_val)
        return f"{{\\fn{font_val}\\c{ass_color}}}{inner_text}"
    
    # תבנית של color ואז face
    pattern = r'<font\s+color="([^"]+)"\s+face="([^"]+)">([\s\S]*?)</font>'
    text = re.sub(pattern, replace_font, text)
    
    # תבנית של face ואז color
    pattern_reverse = r'<font\s+face="([^"]+)"\s+color="([^"]+)">([\s\S]*?)</font>'
    def replace_font_reverse(match):
        font_val = match.group(1)
        color_val = match.group(2)
        inner_text = match.group(3)
        ass_color = _hex_to_ass_color(color_val)
        return f"{{\\fn{font_val}\\c{ass_color}}}{inner_text}"
    text = re.sub(pattern_reverse, replace_font_reverse, text)
    
    # המרת תגיות עיצוב בסיסיות נוספות
    text = text.replace("<i>", "{\\i1}").replace("</i>", "{\\i0}")
    text = text.replace("<b>", "{\\b1}").replace("</b>", "{\\b0}")
    text = text.replace("<u>", "{\\u1}").replace("</u>", "{\\u0}")
    
    # המרת ירידות שורה ל-ASS
    text = text.replace("\n", "\\N")
    return text


def _serialize_vtt(blocks: List[SRTBlock]) -> str:
    """המרת רשימת בלוקים לטקסט WebVTT"""
    lines = ["WEBVTT", ""]
    for block in blocks:
        start_str = _td_to_vtt_time(block.start)
        end_str = _td_to_vtt_time(block.end)
        
        # טיפול במיקום top ב-WebVTT באמצעות cue settings
        cue_settings = ""
        text = block.text
        if "{\\an8}" in text:
            cue_settings = " line:0"
            text = text.replace("{\\an8}", "")
            
        lines.append(str(block.index))
        lines.append(f"{start_str} --> {end_str}{cue_settings}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _hex_to_ass_style_color(hex_color: str, alpha: str = "00") -> str:
    """המרת קוד צבע HEX RGB לפורמט &H AABBGGRR של סגנונות ASS"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        return f"&H{alpha}{b}{g}{r}"
    return f"&H{alpha}FFFFFF"


def _serialize_ass(blocks: List[SRTBlock], settings: CreditSettings) -> str:
    """המרת רשימת בלוקים לפורמט Advanced SubStation Alpha"""
    outline_color_ass = _hex_to_ass_style_color(settings.outline_color)
    back_color_ass = _hex_to_ass_style_color(settings.bg_color)
    
    # בניית שורת סגנון מותאמת אישית - צבע הכתוביות הראשי (Primary) הוא תמיד לבן (&H00FFFFFF)
    # צבע הקרדיט המיוחד מוחל נקודתית באמצעות תגיות צבע בפסקה של הקרדיט עצמו.
    style_line = (
        f"Style: Default,{settings.font},{settings.font_size},"
        f"&H00FFFFFF,&H000000FF,{outline_color_ass},{back_color_ass},"
        f"{settings.is_bold},0,0,0,100,100,0,0,{settings.border_style},{settings.outline_width},{settings.shadow_width},"
        f"2,10,10,10,1\n"
    )
    
    header = (
        "[Script Info]\n"
        "Title: Processed Subtitles\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        "PlayResX: 640\n"
        "PlayResY: 360\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + style_line +
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    
    lines = [header]
    for block in blocks:
        start_str = _td_to_ass_time(block.start)
        end_str = _td_to_ass_time(block.end)
        text = _convert_html_to_ass(block.text, settings)
        lines.append(f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n")
        
    return "".join(lines)
