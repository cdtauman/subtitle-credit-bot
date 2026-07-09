"""
מטפל קבלת קבצים - SRT ו-ZIP
"""

import os
import logging
import uuid
from telegram import Update
from telegram.ext import ContextTypes
from config import TEMP_DIR
from database.db_manager import get_user, is_approved
from database.models import User
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


async def file_receiver_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """קבלת קבצים ועיבודם"""
    user_id = update.effective_user.id

    if not await is_approved(user_id):
        await update.message.reply_text("❌ אין לך גישה לבוט. שלח /start לבקשת גישה.")
        return

    db_user = await get_user(user_id)
    if not db_user or not db_user.setup_done:
        await update.message.reply_text(
            "⚠️ יש להשלים הגדרה ראשונית תחילה. שלח /start"
        )
        return

    if not db_user.credit_text:
        await update.message.reply_text(
            "⚠️ טקסט הקרדיט לא הוגדר. עבור ל⚙️ הגדרות והגדר אותו."
        )
        return

    doc = update.message.document
    if not doc:
        await update.message.reply_text("❌ לא זוהה קובץ. שלח קובץ .srt או .zip")
        return

    file_name = doc.file_name or "file"
    is_zip = file_name.lower().endswith(".zip")
    is_srt = file_name.lower().endswith(".srt")

    if not is_zip and not is_srt:
        await update.message.reply_text(
            "❌ פורמט קובץ לא נתמך.\n"
            "אני מקבל רק קבצי `.srt` או `.zip` המכילים כתוביות."
        )
        return

    # שליפת הגדרות מותאמות אישית אם קיימות (מעבודה חד-פעמית)
    custom = context.user_data.get("custom_settings")
    settings = _build_settings(custom or db_user)

    status_msg = await update.message.reply_text("⏳ מוריד קובץ...")

    # הורדת הקובץ
    job_id = str(uuid.uuid4())[:8]
    temp_path = os.path.join(TEMP_DIR, f"{user_id}_{job_id}_{file_name}")

    try:
        tg_file = await doc.get_file()
        await tg_file.download_to_drive(temp_path)
        await status_msg.edit_text("⚙️ מעבד כתוביות...")

        if is_srt:
            output_path = await _process_single_srt(temp_path, settings, job_id, user_id)
            base_name, _ = os.path.splitext(file_name)
            out_name = f"processed_{base_name}.{settings.output_format}"
            await update.message.reply_document(
                document=open(output_path, "rb"),
                filename=out_name,
                caption="✅ עיבוד הכתוביות הסתיים בהצלחה! 🎬",
                reply_markup=main_menu_keyboard(),
            )
            safe_delete(output_path)

        elif is_zip:
            if not is_valid_zip(temp_path):
                await status_msg.edit_text("❌ קובץ ZIP פגום.")
                return

            if not zip_contains_srt(temp_path):
                await status_msg.edit_text("❌ ה-ZIP לא מכיל קבצי .srt")
                return

            output_zip_path = await _process_zip(temp_path, settings, job_id, user_id)
            out_name = f"processed_{file_name}"
            await update.message.reply_document(
                document=open(output_zip_path, "rb"),
                filename=out_name,
                caption="✅ עיבוד כל הכתוביות הסתיים בהצלחה! 📦",
                reply_markup=main_menu_keyboard(),
            )
            safe_delete(output_zip_path)

        await status_msg.delete()

    except ValueError as e:
        await status_msg.edit_text(f"❌ שגיאה בעיבוד: {e}")
    except Exception as e:
        logger.error(f"שגיאה בעיבוד קובץ עבור {user_id}: {e}", exc_info=True)
        await status_msg.edit_text(
            "❌ אירעה שגיאה לא צפויה בעיבוד הקובץ. נסה שוב."
        )
    finally:
        safe_delete(temp_path)
        # ניקוי הגדרות חד-פעמיות אחרי שימוש
        if "custom_settings" in context.user_data:
            del context.user_data["custom_settings"]


def _read_file_content(path: str) -> str:
    """קריאת תוכן קובץ עם ניסיון זיהוי קידוד"""
    try:
        # ניסיון ראשון: UTF-8 (כולל BOM אם קיים)
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            # ניסיון שני: Windows-1255 (עברית)
            with open(path, "r", encoding="windows-1255") as f:
                return f.read()
        except UnicodeDecodeError:
            # ניסיון אחרון: קריאה סלחנית
            with open(path, "r", encoding="latin-1", errors="replace") as f:
                return f.read()


async def _process_single_srt(
    srt_path: str, settings: CreditSettings, job_id: str, user_id: int
) -> str:
    """עיבוד קובץ SRT בודד"""
    content = _read_file_content(srt_path)
    processed = process_srt(content, settings)

    output_path = os.path.join(TEMP_DIR, f"out_{user_id}_{job_id}.{settings.output_format}")
    # שמירה כ-UTF-8 עם BOM
    with open(output_path, "w", encoding="utf-8-sig") as f:
        f.write(processed)

    return output_path


async def _process_zip(
    zip_path: str, settings: CreditSettings, job_id: str, user_id: int
) -> str:
    """עיבוד ZIP המכיל קבצי SRT"""
    extract_dir = os.path.join(TEMP_DIR, f"extract_{user_id}_{job_id}")
    os.makedirs(extract_dir, exist_ok=True)

    processed_files = []

    try:
        srt_files = extract_srt_from_zip(zip_path, extract_dir)

        for srt_path in srt_files:
            try:
                content = _read_file_content(srt_path)
                processed = process_srt(content, settings)

                base_path, _ = os.path.splitext(srt_path)
                out_path = base_path + f".processed.{settings.output_format}"
                # שמירה כ-UTF-8 עם BOM
                with open(out_path, "w", encoding="utf-8-sig") as f:
                    f.write(processed)

                rel_base, _ = os.path.splitext(os.path.relpath(srt_path, extract_dir))
                arc_name = f"{rel_base}.{settings.output_format}"
                processed_files.append((out_path, arc_name))

            except Exception as e:
                logger.error(f"שגיאה בעיבוד {srt_path}: {e}")

        output_zip = os.path.join(TEMP_DIR, f"out_{user_id}_{job_id}.zip")
        repack_to_zip(processed_files, output_zip)
        return output_zip

    finally:
        # ניקוי תיקיית חילוץ
        import shutil
        try:
            shutil.rmtree(extract_dir, ignore_errors=True)
        except Exception:
            pass


def _build_settings(source) -> CreditSettings:
    """בניית הגדרות עיבוד ממשתמש או מ-dict"""
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
            font_size=source.get("font_size", 20),
            border_style=source.get("border_style", 1),
            outline_color=source.get("outline_color", "#000000"),
            outline_width=source.get("outline_width", 2),
            shadow_width=source.get("shadow_width", 2),
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
        font_size=getattr(source, "font_size", 20),
        border_style=getattr(source, "border_style", 1),
        outline_color=getattr(source, "outline_color", "#000000"),
        outline_width=getattr(source, "outline_width", 2),
        shadow_width=getattr(source, "shadow_width", 2),
        bg_color=getattr(source, "bg_color", "#000000"),
        is_bold=getattr(source, "is_bold", 1),
    )
