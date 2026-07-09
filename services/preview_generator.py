import os
import io
import urllib.request
import logging
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

FONTS_DIR = os.path.join("temp_files", "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

# מיפוי גופנים לכתובות הורדה מ-Google Fonts וחלופות חופשיות
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
    "Times New Roman-Bold": "https://github.com/google/fonts/raw/main/ofl/playfairdisplay/static/PlayfairDisplay-Bold.ttf"
}

def _get_font(font_name: str, is_bold: bool, size: int) -> ImageFont.FreeTypeFont:
    """הורדה וטעינה של הגופן המבוקש בצורה בטוחה"""
    suffix = "Bold" if is_bold else "Regular"
    key = f"{font_name}-{suffix}"
    
    # fallback to Arial if font not mapped
    if key not in FONT_URLS:
        key = f"Arial-{suffix}"
        
    font_filename = f"{key}.ttf"
    font_path = os.path.join(FONTS_DIR, font_filename)
    
    if not os.path.exists(font_path) or os.path.getsize(font_path) == 0:
        url = FONT_URLS.get(key)
        if url:
            try:
                logger.info(f"Downloading font {key} from {url}...")
                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    with open(font_path, 'wb') as f:
                        f.write(response.read())
                logger.info(f"Successfully downloaded font {key}")
            except Exception as e:
                logger.error(f"Failed to download font {key}: {e}")
                if os.path.exists(font_path):
                    try:
                        os.remove(font_path)
                    except Exception:
                        pass
                
    if os.path.exists(font_path) and os.path.getsize(font_path) > 0:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception as e:
            logger.error(f"Failed to load downloaded font {key}: {e}")
            
    # במקרה של כשל בהורדה, ננסה לטעון גופן מערכת שתומך בעברית (כדי למנוע ריבועים)
    system_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\tahoma.ttf",
    ]
    if is_bold:
        system_paths.insert(0, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
        system_paths.insert(1, "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf")
        system_paths.insert(2, "C:\\Windows\\Fonts\\arialbd.ttf")
        
    for path in system_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
                
    # Default fallback
    return ImageFont.load_default()

def _draw_styled_text(image, draw, text, x, y, anchor, font, text_color, outline_color, bg_color, border_style, outline_width, shadow_width):
    """מצייר טקסט מעוצב על גבי תמונה לפי סגנון ASS (גבול/צל/קופסה)"""
    # חישוב גבולות הטקסט
    bbox = draw.textbbox((x, y), text, font=font, anchor=anchor)
    
    if border_style == 3:
        # ציור קופסה כהה/רקע מאחורי הטקסט
        pad_x, pad_y = 12, 6
        box_left = bbox[0] - pad_x
        box_top = bbox[1] - pad_y
        box_right = bbox[2] + pad_x
        box_bottom = bbox[3] + pad_y
        
        # יצירת שכבת RGBA לשקיפות
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle([box_left, box_top, box_right, box_bottom], fill=bg_color + (180,))
        
        # שילוב השכבות
        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(image)
        
        # ציור הטקסט מעל הקופסה
        draw.text((x, y), text, fill=text_color, font=font, anchor=anchor)
    else:
        # ציור צל
        if shadow_width > 0:
            shadow_x = x + shadow_width
            shadow_y = y + shadow_width
            draw.text((shadow_x, shadow_y), text, fill=bg_color, font=font, anchor=anchor)
            
        # ציור הטקסט עם גבול
        draw.text(
            (x, y),
            text,
            fill=text_color,
            font=font,
            anchor=anchor,
            stroke_width=outline_width,
            stroke_fill=outline_color
        )
    return image, draw


def generate_subtitle_preview(
    text: str,
    font_name: str,
    font_size: int,
    color_hex: str,
    border_style: int,      # 1 = outline+shadow, 3 = box
    outline_color_hex: str,
    outline_width: int,
    shadow_width: int,
    bg_color_hex: str,
    is_bold: int,
    position: str = "bottom"
) -> io.BytesIO:
    """ייצור תמונת תצוגה מקדימה מפוצלת המראה דיאלוג על רקע בהיר ורקע כהה, וקרדיט למטה"""
    width, height = 800, 450
    image = Image.new("RGB", (width, height), color="#181820")
    draw = ImageDraw.Draw(image)
    
    # ציור צד שמאל - רקע בהיר (☀️)
    draw.rectangle([0, 0, width // 2, height], fill="#eef0f3")
    # ציור צד ימין - רקע כהה (🌙)
    draw.rectangle([width // 2, 0, width, height], fill="#181820")
    
    # ציור קו מפריד דק
    draw.line([width // 2, 0, width // 2, height - 15], fill="#888888", width=2)
    
    # ציור קו מדומה של נגן וידאו למטה
    draw.rectangle([0, height-15, width, height], fill="#111115")
    draw.rectangle([0, height-15, int(width*0.4), height], fill="#e50914") # playbar red
    draw.ellipse([int(width*0.4)-5, height-18, int(width*0.4)+5, height-12], fill="#e50914")
    
    # חישוב יחס קנה מידה (פרופורציה)
    # הרזולוציה המדומיינת של ה-ASS היא 640x360, בעוד שתמונת התצוגה המקדימה היא 800x450 (פי 1.25).
    # לכן, עלינו להכפיל את הגופן והגבולות ב-1.25 כדי לשמור על יחס תצוגה מדויק וברור.
    scale = 1.25
    scaled_font_size = int(font_size * scale)
    scaled_outline_width = int(outline_width * scale)
    scaled_shadow_width = int(shadow_width * scale)
    
    # טעינת הגופנים (גופן כתובית וגופן תווית קטן)
    font = _get_font(font_name, is_bold == 1, scaled_font_size)
    label_font = _get_font("Arial", False, 16)
    
    # ציור תוויות רקע בהיר/כהה בראש התמונה (ללא אימוג'ים כדי למנוע ריבועים)
    draw.text((width // 4, 30), "רקע בהיר (Bright Scene)", fill="#333333", font=label_font, anchor="ms")
    draw.text((3 * width // 4, 30), "רקע כהה (Dark Scene)", fill="#cccccc", font=label_font, anchor="ms")
    
    # המרת קודי צבע HEX ל-RGB
    def hex_to_rgb(hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 6:
            return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
        return (255, 255, 255)
        
    text_color = hex_to_rgb(color_hex)
    outline_color = hex_to_rgb(outline_color_hex)
    bg_color = hex_to_rgb(bg_color_hex)
    
    # 1. ציור כתוביות דיאלוג לדוגמה - תמיד בצבע לבן (255, 255, 255)
    dialogue_text = "בוקר טוב! לאן אתה הולך?"
    # צד שמאל (על רקע בהיר)
    image, draw = _draw_styled_text(
        image, draw, dialogue_text, width // 4, height // 2 - 10, "ms",
        font, (255, 255, 255), outline_color, bg_color, border_style, scaled_outline_width, scaled_shadow_width
    )
    # צד ימין (על רקע כהה)
    image, draw = _draw_styled_text(
        image, draw, dialogue_text, 3 * width // 4, height // 2 - 10, "ms",
        font, (255, 255, 255), outline_color, bg_color, border_style, scaled_outline_width, scaled_shadow_width
    )
    
    # 2. ציור טקסט הקרדיט הממשי של המשתמש במרכז למטה
    credit_preview_text = f"קרדיט: {text}"
    image, draw = _draw_styled_text(
        image, draw, credit_preview_text, width // 2, height - 70, "ms",
        font, text_color, outline_color, bg_color, border_style, scaled_outline_width, scaled_shadow_width
    )
    
    # שמירת התמונה ל-BytesIO
    output = io.BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output
