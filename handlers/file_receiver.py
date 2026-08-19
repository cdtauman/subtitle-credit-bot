"""
מטפל קבלת קבצים - SRT ו-ZIP
"""

import logging
import os
import shutil
import uuid

from telegram import Update
from telegram.ext import ContextTypes

from config import TEMP_DIR
from database.db_manager import get_user, is_approved
from services.srt_processor import process_srt, CreditSettings
from services.zip_handler import (
    extract_srt_from_zip,
    repack_to_zip,
    is_valid_zip,
    zip_contains_srt,
)
from utils.helpers import safe_delete
from utils.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)


def _safe_filename(file_name: str) -> str:
    """הסרת רכיבי נתיב משם קובץ שמגיע מטלגרם."""
    name = (file_name or "file").replace("\\", "/").split("/")[-1].strip()
    name = name.replace("\x00", "")
    return name or "file"


async def file_receiver_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """קבלת קבצים ועיבודם. מחזיר מספר קבצי כתוביות שעובדו בהצלחה."""
    user_id = update.effective_user.id

    if not await is_approved(user_id):
        await update.message.reply_text("❌ אין לך גישה לבוט. שלח /start לבקשת גישה.")
        return 0

    db_user = await get_user(user_id)
    if not db_user or not db_user.setup_done:
        await update.message.reply_text("⚠️ יש להשלים הגדרה ראשונית תחילה. שלח /start")
        return 0

    if not db_user.credit_text:
        await update.message.reply_text("⚠️ טקסט הקרדיט לא הוגדר. עבור ל⚙️ הגדרות והגדר אותו.")
        return 0

    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ לא זוהה קובץ. שלח קובץ .srt או .zip")
        return 0

    file_name = _safe_filename(doc.file_name or "file")
    lower_name = file_name.lower()
    is_zip = lower_name.endswith(".zip")
    is_srt = lower_name.endswith(".srt")
    if not is_zip and not is_srt:
        await update.message.reply_text(
            "❌ פורמט קובץ לא נתמך.\nאני מקבל רק קבצי `.srt` או `.zip` המכילים כתוביות."
        )
        return 0

    custom = context.user_data.get("custom_settings")
    settings = _build_settings(custom or db_user)
    status_msg = await update.message.reply_text("⏳ מוריד קובץ...")

    job_id = str(uuid.uuid4())[:8]
    temp_path = os.path.join(TEMP_DIR, f"{user_id}_{job_id}_{file_name}")
    processed_count = 0

    try:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(temp_path)
        await status_msg.edit_text("⚙️ מעבד כתוביות...")

        if is_srt:
            output_path = None
            try:
                output_path = await _process_single_srt(temp_path, settings, job_id, user_id)
                base_name, _ = os.path.splitext(file_name)
                out_name = f"processed_{base_name}.{settings.output_format}"
                with open(output_path, "rb") as output_file:
                    await update.message.reply_document(
                        document=output_file,
                        filename=out_name,
                        caption="✅ עיבוד הכתוביות הסתיים בהצלחה! 🎬",
                        reply_markup=main_menu_keyboard(),
                    )
                processed_count = 1
            finally:
                safe_delete(output_path)

        else:
            if not is_valid_zip(temp_path):
                raise ValueError("קובץ ZIP פגום")
            if not zip_contains_srt(temp_path):
                raise ValueError("ה-ZIP לא מכיל קבצי SRT תקינים")

            output_zip_path = None
            try:
                output_zip_path, succeeded, failed = await _process_zip(
                    temp_path, settings, job_id, user_id
                )
                out_name = f"processed_{file_name}"
                if failed:
                    caption = f"✅ עובדו {succeeded} קבצים. ⚠️ {failed} קבצים נכשלו ולא נכללו ב-ZIP."
                else:
                    caption = f"✅ עיבוד {succeeded} קבצי הכתוביות הסתיים בהצלחה! 📦"
                with open(output_zip_path, "rb") as output_file:
                    await update.message.reply_document(
                        document=output_file,
                        filename=out_name,
                        caption=caption,
                        reply_markup=main_menu_keyboard(),
                    )
                processed_count = succeeded
            finally:
                safe_delete(output_zip_path)

        try:
            await status_msg.delete()
        except Exception:
            pass

        # הגדרות חד-פעמיות נצרכות רק לאחר שהתקבל פלט תקין ונשלח למשתמש.
        if processed_count > 0:
            context.user_data.pop("custom_settings", None)
        return processed_count

    except ValueError as exc:
        await status_msg.edit_text(f"❌ שגיאה בעיבוד: {exc}")
        return 0
    except Exception as exc:
        logger.error("שגיאה בעיבוד קובץ עבור %s: %s", user_id, exc, exc_info=True)
        await status_msg.edit_text("❌ אירעה שגיאה לא צפויה בעיבוד הקובץ. נסה שוב.")
        return 0
    finally:
        safe_delete(temp_path)


def _read_file_content(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="windows-1255") as f:
                return f.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1", errors="replace") as f:
                return f.read()


async def _process_single_srt(
    srt_path: str, settings: CreditSettings, job_id: str, user_id: int
) -> str:
    content = _read_file_content(srt_path)
    processed = process_srt(content, settings)
    output_path = os.path.join(TEMP_DIR, f"out_{user_id}_{job_id}.{settings.output_format}")
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write(processed)
    return output_path


async def _process_zip(
    zip_path: str, settings: CreditSettings, job_id: str, user_id: int
) -> tuple[str, int, int]:
    extract_dir = os.path.join(TEMP_DIR, f"extract_{user_id}_{job_id}")
    os.makedirs(extract_dir, exist_ok=True)
    processed_files = []
    failed = 0

    try:
        srt_files = extract_srt_from_zip(zip_path, extract_dir)
        if not srt_files:
            raise ValueError("ה-ZIP לא מכיל קבצי SRT תקינים")

        for srt_path in srt_files:
            try:
                content = _read_file_content(srt_path)
                processed = process_srt(content, settings)
                base_path, _ = os.path.splitext(srt_path)
                out_path = base_path + f".processed.{settings.output_format}"
                with open(out_path, "w", encoding="utf-8-sig") as f:
                    f.write(processed)

                rel_base, _ = os.path.splitext(os.path.relpath(srt_path, extract_dir))
                arc_name = f"{rel_base}.{settings.output_format}".replace(os.sep, "/")
                processed_files.append((out_path, arc_name))
            except Exception as exc:
                failed += 1
                logger.error("שגיאה בעיבוד %s: %s", srt_path, exc)

        if not processed_files:
            raise ValueError("כל קבצי הכתוביות ב-ZIP נכשלו בעיבוד")

        output_zip = os.path.join(TEMP_DIR, f"out_{user_id}_{job_id}.zip")
        repack_to_zip(processed_files, output_zip)
        return output_zip, len(processed_files), failed
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)


def _build_settings(source) -> CreditSettings:
    if isinstance(source, dict):
        return CreditSettings(
            credit_text=source["credit_text"],
            color=source["color"],
            font=source["font"],
            position=source["position"],
            frequency=source["frequency"],
            duration_start=source["duration_start"],
            duration_middle=source["duration_middle"],
            duration_end=source["duration_end"],
            output_format=source.get("output_format", "srt"),
            font_size=source.get("font_size", 23),
            border_style=source.get("border_style", 1),
            outline_color=source.get("outline_color", "#000000"),
            outline_width=source.get("outline_width", 2),
            shadow_width=source.get("shadow_width", 0),
            bg_color=source.get("bg_color", "#000000"),
            is_bold=source.get("is_bold", 1),
        )
    return CreditSettings(
        credit_text=source.credit_text,
        color=source.color,
        font=source.font,
        position=source.position,
        frequency=source.frequency,
        duration_start=source.duration_start,
        duration_middle=source.duration_middle,
        duration_end=source.duration_end,
        output_format=getattr(source, "output_format", "srt"),
        font_size=getattr(source, "font_size", 23),
        border_style=getattr(source, "border_style", 1),
        outline_color=getattr(source, "outline_color", "#000000"),
        outline_width=getattr(source, "outline_width", 2),
        shadow_width=getattr(source, "shadow_width", 0),
        bg_color=getattr(source, "bg_color", "#000000"),
        is_bold=getattr(source, "is_bold", 1),
    )
