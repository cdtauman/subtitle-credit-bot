"""
הגדרות תצורה - טעינת משתני סביבה
"""

import os
from dotenv import load_dotenv

load_dotenv()

# טוקן הבוט מטלגרם
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# מזהי מנהלים ראשיים (מופרדים בפסיק ב-.env)
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _admin_ids_raw.split(",") if x.strip().isdigit()
]

# נתיב מסד הנתונים
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "database/bot.db")

# תיקיית קבצים זמניים
TEMP_DIR: str = os.getenv("TEMP_DIR", "temp_files")
os.makedirs(TEMP_DIR, exist_ok=True)

# ברירות מחדל
DEFAULT_COLOR = "#FFFFFF"
DEFAULT_FONT = "Arial"
DEFAULT_POSITION = "top"
DEFAULT_FREQUENCY = 30  # דקות
DEFAULT_DURATION_START = 12  # שניות
DEFAULT_DURATION_MIDDLE = 7  # שניות
DEFAULT_DURATION_END = 20  # שניות

# רשימת גופנים זמינים
AVAILABLE_FONTS = [
    "Arial",
    "Times New Roman",
    "Courier New",
    "Verdana",
    "Tahoma",
    "Georgia",
    "Trebuchet MS",
]

# רשימת צבעים מהירים
QUICK_COLORS = {
    "לבן ⚪": "#FFFFFF",
    "שחור ⚫": "#000000",
    "אדום 🔴": "#FF0000",
    "ירוק 🟢": "#00FF00",
    "כחול 🔵": "#0000FF",
    "צהוב 🟡": "#FFFF00",
    "כתום 🟠": "#FFA500",
    "סגול 🟣": "#800080",
    "ורוד": "#FFC0CB",
    "טורקיז 🔵": "#40E0D0",
    "זהב 🟡": "#FFD700",
    "כסף ⚪": "#C0C0C0",
    "חום 🟤": "#A52A2A",
    "אפור ⚪": "#808080",
    "כחול בהיר 🔵": "#ADD8E6",
    "ירוק בהיר 🟢": "#90EE90",
    "אדום כהה 🔴": "#8B0000",
    "כחול כהה 🔵": "#00008B",
    "ירוק זית 🟢": "#808000",
    "ציאן 🔵": "#00FFFF",
    "מג'נטה 🟣": "#FF00FF",
    "ליים 🟢": "#00FF00",
    "טיל 🔵": "#008080",
    "אינדיגו 🟣": "#4B0082",
    "בז' ⚪": "#F5F5DC",
    "שוקולד 🟤": "#D2691E",
    "קורל 🟠": "#FF7F50",
    "קרם ⚪": "#FFFDD0",
    "לבנדר 🟣": "#E6E6FA",
    "מנטה 🟢": "#F5FFFA",
    "אפרסק 🟠": "#FFE5B4",
    "שזיף 🟣": "#DDA0DD",
    "סלמון 🟠": "#FA8072",
    "שמיים 🔵": "#87CEEB",
    "שלג ⚪": "#FFFAFA",
    "אביב 🟢": "#00FF7F",
    "שחור פחם ⚫": "#36454F",
    "כחול חצות 🔵": "#191970",
    "ירוק יער 🟢": "#228B22",
    "אדום עגבנייה 🔴": "#FF6347",
    "זהב חיוור 🟡": "#EEE8AA",
    "טורקיז כהה 🔵": "#00CED1",
    "סגול כהה 🟣": "#9932CC",
    "ורוד עמוק": "#FF1493",
    "כחול רויאל 🔵": "#4169E1",
    "ירוק ים 🟢": "#2E8B57",
    "חום ארד 🟤": "#CD7F32",
    "אפור פחם ⚫": "#36454F",
}
