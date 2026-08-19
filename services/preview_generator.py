import io
import logging
import os
import urllib.request

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

FONTS_DIR = os.path.join("temp_files", "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

FONT_URLS = {
    "Assistant-Regular": "https://github.com/hafontia/Assistant/raw/master/fonts/ttf/Assistant-Regular.ttf",
    "Assistant-Bold": "https://github.com/hafontia/Assistant/raw/master/fonts/ttf/Assistant-Bold.ttf",
    "Rubik-Regular": "https://github.com/googlefonts/rubik/raw/main/fonts/ttf/Rubik-Regular.ttf",
    "Rubik-Bold": "https://github.com/googlefonts/rubik/raw/main/fonts/ttf/Rubik-Bold.ttf",
    "Secular One-Regular": "https://github.com/google/fonts/raw/main/ofl/secularone/SecularOne-Regular.ttf",
    "Secular One-Bold": "https://github.com/google/fonts/raw/main/ofl/secularone/SecularOne-Regular.ttf",
    "David-Regular": "https://github.com/google/fonts/raw/main/ofl/davidlibre/DavidLibre-Regular.ttf",
    "David-Bold": "https://github.com/google/fonts/raw/main/ofl/davidlibre/DavidLibre-Bold.ttf",
    "Arial-Regular": "https://github.com/google/fonts/raw/main/ofl/arimo/Arimo%5Bwght%5D.ttf",
    "Arial-Bold": "https://github.com/google/fonts/raw/main/ofl/arimo/Arimo%5Bwght%5D.ttf",
    "Verdana-Regular": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf",
    "Verdana-Bold": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf",
    "Tahoma-Regular": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Regular.ttf",
    "Tahoma-Bold": "https://github.com/google/fonts/raw/main/apache/roboto/static/Roboto-Bold.ttf",
    "Times New Roman-Regular": "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/static/PlayfairDisplay-Regular.ttf",
    "Times New Roman-Bold": "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/static/PlayfairDisplay-Bold.ttf",
}


def _get_font(font_name: str, is_bold: bool, size: int) -> ImageFont.ImageFont:
    """טוען גופן מתיקיית המטמון, מוריד חלופה חופשית במידת הצורך, ואז נופל לגופן מערכת."""
    suffix = "Bold" if is_bold else "Regular"
    key = f"{font_name}-{suffix}"
    if key not in FONT_URLS:
        key = f"Arial-{suffix}"

    font_path = os.path.join(FONTS_DIR, f"{key}.ttf")
    if not os.path.exists(font_path) or os.path.getsize(font_path) == 0:
        url = FONT_URLS.get(key)
        if url:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "subtitle-credit-bot/1.0"})
                with urllib.request.urlopen(req, timeout=10) as response, open(font_path, "wb") as output:
                    output.write(response.read())
            except Exception as exc:
                logger.warning("Failed to download preview font %s: %s", key, exc)
                try:
                    if os.path.exists(font_path):
                        os.remove(font_path)
                except OSError:
                    pass

    if os.path.exists(font_path) and os.path.getsize(font_path) > 0:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception as exc:
            logger.warning("Failed to load preview font %s: %s", key, exc)

    system_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if is_bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if is_bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if is_bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\tahomabd.ttf" if is_bold else "C:\\Windows\\Fonts\\tahoma.ttf",
    ]
    for path in system_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _hex_to_rgb(hex_value: str) -> tuple[int, int, int]:
    value = (hex_value or "").strip().lstrip("#")
    if len(value) != 6:
        return (255, 255, 255)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (255, 255, 255)


def _draw_styled_text(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    anchor: str,
    font: ImageFont.ImageFont,
    text_color: tuple[int, int, int],
    outline_color: tuple[int, int, int],
    bg_color: tuple[int, int, int],
    border_style: int,
    outline_width: int,
    shadow_width: int,
):
    """מצייר בקירוב נאמן ל-ASS: BorderStyle=1 גבול+צל, BorderStyle=3 קופסה אטומה."""
    if border_style == 3:
        bbox = draw.textbbox((x, y), text, font=font, anchor=anchor)
        # libass משתמש ב-Outline גם כהרחבת הקופסה. נשמור יחס דומה במקום padding קבוע.
        pad = max(1, int(outline_width))
        draw.rectangle(
            [bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad],
            fill=bg_color,
        )
        draw.text((x, y), text, fill=text_color, font=font, anchor=anchor)
        return image, draw

    if shadow_width > 0:
        draw.text(
            (x + shadow_width, y + shadow_width),
            text,
            fill=bg_color,
            font=font,
            anchor=anchor,
        )
    draw.text(
        (x, y),
        text,
        fill=text_color,
        font=font,
        anchor=anchor,
        stroke_width=max(0, int(outline_width)),
        stroke_fill=outline_color,
    )
    return image, draw


def generate_subtitle_preview(
    text: str,
    font_name: str,
    font_size: int,
    color_hex: str,
    border_style: int,
    outline_color_hex: str,
    outline_width: int,
    shadow_width: int,
    bg_color_hex: str,
    is_bold: int,
    position: str = "bottom",
) -> io.BytesIO:
    """מייצר preview שמחקה את הגדרות ה-ASS בפועל, כולל מיקום הקרדיט וסגנון הקופסה."""
    width, height = 800, 450
    image = Image.new("RGB", (width, height), color="#181820")
    draw = ImageDraw.Draw(image)

    draw.rectangle([0, 0, width // 2, height], fill="#eef0f3")
    draw.rectangle([width // 2, 0, width, height], fill="#181820")
    draw.line([width // 2, 0, width // 2, height - 15], fill="#888888", width=2)
    draw.rectangle([0, height - 15, width, height], fill="#111115")
    draw.rectangle([0, height - 15, int(width * 0.4), height], fill="#e50914")
    draw.ellipse([int(width * 0.4) - 5, height - 18, int(width * 0.4) + 5, height - 12], fill="#e50914")

    scale = 1.25  # ASS PlayRes 640x360 -> preview 800x450
    scaled_font_size = max(1, int(round(font_size * scale)))
    scaled_outline_width = max(0, int(round(outline_width * scale)))
    scaled_shadow_width = max(0, int(round(shadow_width * scale)))

    font = _get_font(font_name, is_bold == 1, scaled_font_size)
    label_font = _get_font("Arial", False, 16)

    draw.text((width // 4, 30), "רקע בהיר (Bright Scene)", fill="#333333", font=label_font, anchor="ms")
    draw.text((3 * width // 4, 30), "רקע כהה (Dark Scene)", fill="#cccccc", font=label_font, anchor="ms")

    text_color = _hex_to_rgb(color_hex)
    outline_color = _hex_to_rgb(outline_color_hex)
    bg_color = _hex_to_rgb(bg_color_hex)
    actual_border_style = 3 if border_style == 3 else 1
    actual_shadow = 0 if actual_border_style == 3 else scaled_shadow_width

    dialogue_text = "בוקר טוב! לאן אתה הולך?"
    for x in (width // 4, 3 * width // 4):
        image, draw = _draw_styled_text(
            image,
            draw,
            dialogue_text,
            x,
            height // 2 - 10,
            "ms",
            font,
            (255, 255, 255),
            outline_color,
            bg_color,
            actual_border_style,
            scaled_outline_width,
            actual_shadow,
        )

    credit_y = 95 if position == "top" else height - 70
    credit_text = f"קרדיט: {text}"
    image, draw = _draw_styled_text(
        image,
        draw,
        credit_text,
        width // 2,
        credit_y,
        "ms",
        font,
        text_color,
        outline_color,
        bg_color,
        actual_border_style,
        scaled_outline_width,
        actual_shadow,
    )

    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output
