import os
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from PIL import Image, ImageDraw, ImageFont

from services.srt_processor import CreditSettings, _srt_time_to_td, process_srt
from services.zip_handler import extract_srt_from_zip, repack_to_zip
from utils.helpers import parse_style_string


SAMPLE_SRT = """1\n00:00:01,000 --> 00:00:02,000\nשלום\n\n2\n00:00:04,000 --> 00:00:05,000\nעולם\n"""


class SubtitleRegressionTests(unittest.TestCase):
    def test_ass_box_uses_background_color_not_outline_color(self):
        settings = CreditSettings(
            credit_text="קרדיט",
            color="#FFFFFF",
            font="Assistant",
            position="top",
            frequency=0,
            duration_start=1,
            duration_middle=0,
            duration_end=1,
            output_format="ass",
            border_style=3,
            outline_color="#0000FF",
            bg_color="#000000",
            outline_width=2,
            shadow_width=3,
        )
        output = process_srt(SAMPLE_SRT, settings)
        style = next(line for line in output.splitlines() if line.startswith("Style: Default"))
        fields = [part.strip() for part in style.split(":", 1)[1].split(",")]
        self.assertEqual(fields[5], "&H00000000")  # OutlineColour = black box
        self.assertEqual(fields[15], "3")
        self.assertEqual(fields[17], "0")  # no shadow for opaque box style

    def test_srt_fractional_seconds_are_scaled_correctly(self):
        self.assertEqual(_srt_time_to_td("00:00:01,5").microseconds, 500_000)
        self.assertEqual(_srt_time_to_td("00:00:01,05").microseconds, 50_000)
        self.assertEqual(_srt_time_to_td("00:00:01,005").microseconds, 5_000)

    def test_import_keeps_decimals_and_ass_boolean_values(self):
        parsed = parse_style_string("Fontsize=23.5,Bold=-1,Shadow=0.1,BorderStyle=3")
        self.assertEqual(parsed["font_size"], 24)
        self.assertEqual(parsed["is_bold"], 1)
        self.assertEqual(parsed["shadow_width"], 0)
        self.assertEqual(parsed["border_style"], 3)

    def test_import_supports_full_ass_style_line(self):
        parsed = parse_style_string(
            "Style: Default,Assistant,23.5,&H00FFFFFF,&H000000FF,&H00FF0000,"
            "&H00000000,-1,0,0,0,100,100,0,0,3,2,0,2,10,10,10,1"
        )
        self.assertEqual(parsed["font"], "Assistant")
        self.assertEqual(parsed["font_size"], 24)
        self.assertEqual(parsed["color"], "#FFFFFF")
        self.assertEqual(parsed["outline_color"], "#0000FF")
        self.assertEqual(parsed["bg_color"], "#000000")
        self.assertEqual(parsed["is_bold"], 1)
        self.assertEqual(parsed["border_style"], 3)

    def test_malformed_ass_style_does_not_crash(self):
        parsed = parse_style_string(
            "Style: Broken,Assistant,xx,&H00FFFFFF,&H0,&H0,&H0,-1,0,0,0,100,100,0,0,nope,xx,xx,2,10,10,10,1"
        )
        self.assertEqual(parsed.get("font"), "Assistant")
        self.assertNotIn("border_style", parsed)


class ZipRegressionTests(unittest.TestCase):
    def test_zip_traversal_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "bad.zip")
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("../evil.srt", SAMPLE_SRT)
            with self.assertRaises(ValueError):
                extract_srt_from_zip(zip_path, os.path.join(temp_dir, "extract"))
            self.assertFalse(Path(temp_dir, "evil.srt").exists())

    def test_empty_repack_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(ValueError):
                repack_to_zip([], os.path.join(temp_dir, "empty.zip"))

    def test_oversized_srt_member_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, "large.zip")
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
                zf.writestr("large.srt", b"x" * (5 * 1024 * 1024 + 1))
            with self.assertRaises(ValueError):
                extract_srt_from_zip(zip_path, os.path.join(temp_dir, "extract"))


class FileReceiverRegressionTests(unittest.TestCase):
    def test_uploaded_filename_cannot_escape_temp_directory(self):
        from handlers.file_receiver import _safe_filename

        self.assertEqual(_safe_filename("../../evil.srt"), "evil.srt")
        self.assertEqual(_safe_filename(r"..\\..\\evil.srt"), "evil.srt")


class PreviewRegressionTests(unittest.TestCase):
    def test_preview_honors_credit_position(self):
        import services.preview_generator as preview

        calls = []

        def fake_draw(image, draw, text, x, y, *args, **kwargs):
            calls.append((text, x, y))
            return image, draw

        with patch.object(preview, "_get_font", return_value=ImageFont.load_default()), patch.object(
            preview, "_draw_styled_text", side_effect=fake_draw
        ):
            preview.generate_subtitle_preview(
                text="בדיקה",
                font_name="Assistant",
                font_size=23,
                color_hex="#FFFFFF",
                border_style=1,
                outline_color_hex="#000000",
                outline_width=2,
                shadow_width=0,
                bg_color_hex="#000000",
                is_bold=1,
                position="top",
            )
        self.assertEqual(calls[-1][2], 95)

    def test_box_preview_is_opaque_background_color(self):
        import services.preview_generator as preview

        image = Image.new("RGB", (200, 100), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default()
        bbox = draw.textbbox((100, 50), "test", font=font, anchor="mm")
        preview._draw_styled_text(
            image,
            draw,
            "test",
            100,
            50,
            "mm",
            font,
            (255, 255, 255),
            (0, 0, 255),
            (1, 2, 3),
            3,
            2,
            9,
        )
        self.assertEqual(image.getpixel((bbox[0] - 1, bbox[1] - 1)), (1, 2, 3))


class DatabaseRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_init_db_does_not_overwrite_existing_style_preferences(self):
        import database.db_manager as dbm

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "bot.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                """CREATE TABLE users (
                    user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT NOT NULL,
                    is_approved INTEGER NOT NULL DEFAULT 0, is_banned INTEGER NOT NULL DEFAULT 0,
                    is_admin INTEGER NOT NULL DEFAULT 0, credit_text TEXT, color TEXT NOT NULL,
                    font TEXT NOT NULL, position TEXT NOT NULL, frequency INTEGER NOT NULL,
                    duration_start INTEGER NOT NULL, duration_middle INTEGER NOT NULL,
                    duration_end INTEGER NOT NULL, setup_done INTEGER NOT NULL,
                    output_format TEXT NOT NULL, font_size INTEGER NOT NULL,
                    border_style INTEGER NOT NULL, outline_color TEXT NOT NULL,
                    outline_width INTEGER NOT NULL, shadow_width INTEGER NOT NULL,
                    bg_color TEXT NOT NULL, is_bold INTEGER NOT NULL
                )"""
            )
            conn.execute(
                """INSERT INTO users VALUES (
                    123, NULL, 'Test', 1, 0, 0, 'credit', '#FFFFFF', 'Arial', 'bottom',
                    10, 5, 5, 5, 1, 'ass', 20, 1, '#000000', 2, 2, '#000000', 1
                )"""
            )
            conn.commit()
            conn.close()

            old_path, old_admins = dbm.DB_PATH, dbm.ADMIN_IDS
            try:
                dbm.DB_PATH = db_path
                dbm.ADMIN_IDS = []
                await dbm.init_db()
                conn = sqlite3.connect(db_path)
                row = conn.execute(
                    "SELECT font, font_size, shadow_width FROM users WHERE user_id = 123"
                ).fetchone()
                conn.close()
            finally:
                dbm.DB_PATH = old_path
                dbm.ADMIN_IDS = old_admins

            self.assertEqual(row, ("Arial", 20, 2))

    async def test_banned_database_admin_is_not_admin(self):
        import database.db_manager as dbm

        user = SimpleNamespace(is_admin=True, is_banned=True)
        with patch.object(dbm, "ADMIN_IDS", []), patch.object(dbm, "get_user", AsyncMock(return_value=user)):
            self.assertFalse(await dbm.is_admin(123))


class MainRegressionTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_file_processing_does_not_increment_stats(self):
        import main

        update = SimpleNamespace()
        context = SimpleNamespace()
        with patch.object(main, "file_receiver_handler", AsyncMock(return_value=0)), patch.object(
            main, "increment_processed_files", AsyncMock()
        ) as increment:
            await main.custom_file_receiver_handler(update, context)
            increment.assert_not_awaited()

    async def test_success_count_is_used_for_stats(self):
        import main

        update = SimpleNamespace()
        context = SimpleNamespace()
        with patch.object(main, "file_receiver_handler", AsyncMock(return_value=3)), patch.object(
            main, "increment_processed_files", AsyncMock()
        ) as increment:
            await main.custom_file_receiver_handler(update, context)
            increment.assert_awaited_once_with(3)

    async def test_reject_callback_requires_admin(self):
        import main

        query = SimpleNamespace(answer=AsyncMock())
        update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=999))
        with patch.object(main, "is_admin", AsyncMock(return_value=False)), patch.object(
            main, "reject_user_callback", AsyncMock()
        ) as reject:
            await main.secure_reject_user_callback(update, SimpleNamespace())
            reject.assert_not_awaited()
            query.answer.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
