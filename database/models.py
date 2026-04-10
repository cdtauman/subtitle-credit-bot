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
    font: str = "Arial"
    position: str = "bottom"      # "top" / "bottom"
    frequency: int = 10           # בדקות
    duration_start: int = 5       # שניות
    duration_middle: int = 5      # שניות
    duration_end: int = 5         # שניות
    setup_done: bool = False      # האם השלים הגדרה ראשונית


@dataclass
class PendingRequest:
    user_id: int
    username: Optional[str]
    full_name: str
    message_id: Optional[int] = None   # מזהה הודעת הבקשה למנהל
