"""
שירות טיפול בקבצי ZIP
פתיחה, עיבוד SRT בתוכם, ואריזה מחדש
"""

import os
import zipfile
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


def extract_srt_from_zip(zip_path: str, extract_dir: str) -> List[str]:
    """
    חילוץ קבצי SRT מארכיון ZIP
    מחזיר רשימת נתיבים לקבצי SRT שחולצו
    """
    srt_files = []
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            if name.lower().endswith(".srt") and not name.startswith("__MACOSX"):
                zf.extract(name, extract_dir)
                full_path = os.path.join(extract_dir, name)
                srt_files.append(full_path)
    logger.info(f"📦 חולצו {len(srt_files)} קבצי SRT מ-ZIP")
    return srt_files


def repack_to_zip(processed_files: List[Tuple[str, str]], output_path: str) -> str:
    """
    אריזת קבצים מעובדים ל-ZIP חדש
    processed_files: [(נתיב_קובץ, שם_בתוך_zip), ...]
    מחזיר נתיב ה-ZIP החדש
    """
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path, arc_name in processed_files:
            zf.write(file_path, arc_name)
    logger.info(f"📦 ZIP חדש נוצר: {output_path}")
    return output_path


def is_valid_zip(file_path: str) -> bool:
    """בדיקה שהקובץ הוא ZIP תקין"""
    return zipfile.is_zipfile(file_path)


def zip_contains_srt(zip_path: str) -> bool:
    """בדיקה שה-ZIP מכיל לפחות קובץ SRT אחד"""
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            return any(n.lower().endswith(".srt") for n in zf.namelist())
    except Exception:
        return False
