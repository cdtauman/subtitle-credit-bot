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
