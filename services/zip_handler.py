"""
שירות טיפול בקבצי ZIP
פתיחה, עיבוד SRT בתוכם, ואריזה מחדש
"""

import logging
import os
import shutil
import zipfile
from pathlib import PurePosixPath
from typing import List, Tuple

logger = logging.getLogger(__name__)

MAX_SRT_FILES = 500
MAX_MEMBER_BYTES = 5 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200


def _normalized_member_name(name: str) -> str:
    """נרמול שם ZIP לנתיב POSIX ובדיקה שאינו יוצא מתיקיית החילוץ."""
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts:
        raise ValueError("ה-ZIP מכיל נתיב קובץ לא בטוח")
    if any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("ה-ZIP מכיל נתיב קובץ לא בטוח")
    # מגן גם מפני שמות Windows כמו C:/file.srt
    if ":" in path.parts[0]:
        raise ValueError("ה-ZIP מכיל נתיב קובץ לא בטוח")
    return "/".join(path.parts)


def _validated_srt_members(zf: zipfile.ZipFile) -> List[Tuple[zipfile.ZipInfo, str]]:
    members: List[Tuple[zipfile.ZipInfo, str]] = []
    total_size = 0

    for info in zf.infolist():
        if info.is_dir():
            continue
        normalized = _normalized_member_name(info.filename)
        if normalized.startswith("__MACOSX/") or not normalized.lower().endswith(".srt"):
            continue

        if info.file_size > MAX_MEMBER_BYTES:
            raise ValueError("ה-ZIP מכיל קובץ כתוביות גדול מדי")
        total_size += info.file_size
        if total_size > MAX_TOTAL_UNCOMPRESSED_BYTES:
            raise ValueError("ה-ZIP גדול מדי לאחר חילוץ")

        if info.file_size > 0:
            compressed = max(info.compress_size, 1)
            if info.file_size / compressed > MAX_COMPRESSION_RATIO:
                raise ValueError("ה-ZIP מכיל יחס דחיסה חריג")

        members.append((info, normalized))
        if len(members) > MAX_SRT_FILES:
            raise ValueError("ה-ZIP מכיל יותר מדי קבצי SRT")

    return members


def extract_srt_from_zip(zip_path: str, extract_dir: str) -> List[str]:
    """חילוץ בטוח של קבצי SRT מארכיון ZIP."""
    os.makedirs(extract_dir, exist_ok=True)
    root = os.path.realpath(extract_dir)
    srt_files: List[str] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info, normalized in _validated_srt_members(zf):
            output_path = os.path.realpath(os.path.join(extract_dir, *PurePosixPath(normalized).parts))
            if os.path.commonpath([root, output_path]) != root:
                raise ValueError("ה-ZIP מכיל נתיב קובץ לא בטוח")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with zf.open(info, "r") as src, open(output_path, "wb") as dst:
                shutil.copyfileobj(src, dst, length=1024 * 1024)
            srt_files.append(output_path)

    logger.info("📦 חולצו %s קבצי SRT מ-ZIP", len(srt_files))
    return srt_files


def repack_to_zip(processed_files: List[Tuple[str, str]], output_path: str) -> str:
    if not processed_files:
        raise ValueError("לא נוצרו קבצים תקינים לאריזה")
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path, arc_name in processed_files:
            safe_arc_name = _normalized_member_name(arc_name)
            zf.write(file_path, safe_arc_name)
    logger.info("📦 ZIP חדש נוצר: %s", output_path)
    return output_path


def is_valid_zip(file_path: str) -> bool:
    return zipfile.is_zipfile(file_path)


def zip_contains_srt(zip_path: str) -> bool:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            return bool(_validated_srt_members(zf))
    except (OSError, zipfile.BadZipFile, ValueError):
        return False
