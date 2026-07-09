"""
מודלי מסד נתונים
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class User:
    user_id: int
    username: Optional[str]
    full_name: str
    is_approved: bool = False
    is_banned: bool = False
    is_admin: bool = False
    # הגדרות ברירת מחדל
    credit_text: Optional[str] = None
    color: str = "#FFFFFF"
    font: str = "Assistant"
    position: str = "bottom"      # "top" / "bottom"
    frequency: int = 10           # בדקות
    duration_start: int = 5       # שניות
    duration_middle: int = 5      # שניות
    duration_end: int = 5         # שניות
    setup_done: bool = False      # האם השלים הגדרה ראשונית
    output_format: str = "srt"    # "srt" / "ass" / "vtt"
    # עיצוב כתוביות מתקדם (ASS)
    font_size: int = 23
    border_style: int = 1         # 1 = צל + גבול, 3 = קופסה
    outline_color: str = "#000000"
    outline_width: int = 2
    shadow_width: int = 0
    bg_color: str = "#000000"
    is_bold: int = 1              # 1 = מודגש (Bold), 0 = רגיל


@dataclass
class PendingRequest:
    user_id: int
    username: Optional[str]
    full_name: str
    message_id: Optional[int] = None   # מזהה הודעת הבקשה למנהל
