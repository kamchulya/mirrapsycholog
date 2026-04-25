import os
import textwrap
from PIL import Image, ImageDraw, ImageFont
import tempfile


def generate_result_card(
    test_name: str,
    insight: str,
    user_name: str = ""
) -> str:
    """Генерируем красивую карточку результата теста для сторис"""

    # Размер карточки — вертикальный формат для сторис (9:16)
    W, H = 1080, 1350

    # Создаём изображение
    img = Image.new("RGB", (W, H), color=(15, 10, 25))
    draw = ImageDraw.Draw(img)

    # ── ГРАДИЕНТНЫЙ ФОН ──
    for y in range(H):
        r = int(15 + (40 - 15) * y / H)
        g = int(10 + (15 - 10) * y / H)
        b = int(25 + (60 - 25) * y / H)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # ── ДЕКОРАТИВНЫЕ КРУГИ ──
    # Большой полупрозрачный круг справа сверху
    _draw_circle(draw, W - 100, -80, 400, (120, 60, 180, 30))
    # Маленький круг слева снизу
    _draw_circle(draw, -60, H - 100, 300, (80, 40, 140, 20))
    # Средний акцентный круг
    _draw_circle(draw, W // 2, H // 2 - 50, 600, (60, 20, 120, 15))

    # ── ЛИНИИ ДЕКОРА ──
    for i in range(5):
        y_pos = 180 + i * 3
        alpha = 60 - i * 10
        draw.line([(80, y_pos), (W - 80, y_pos)], fill=(180, 120, 255, alpha), width=1)

    # ── ЛОГОТИП MIRRA ──
    try:
        font_title = _get_font(120)
        font_subtitle = _get_font(36)
        font_body = _get_font(44)
        font_insight = _get_font(40)
        font_small = _get_font(30)
        font_handle = _get_font(32)
    except Exception:
        font_title = font_subtitle = font_body = font_insight = font_small = font_handle = None

    # Mirra логотип
    draw.text((W // 2, 90), "🌙 MIRRA", font=font_title,
              fill=(220, 180, 255), anchor="mm")

    # Тонкая линия под логотипом
    draw.line([(200, 155), (W - 200, 155)], fill=(120, 70, 200), width=2)

    # ── НАЗВАНИЕ ТЕСТА ──
    draw.text((W // 2, 210), test_name, font=font_subtitle,
              fill=(160, 120, 220), anchor="mm")

    # ── ЗВЁЗДОЧКИ ДЕКОРА ──
    stars_y = 270
    for i, x in enumerate([120, 200, W // 2, W - 200, W - 120]):
        size = 6 if i % 2 == 0 else 4
        draw.ellipse([x - size, stars_y - size, x + size, stars_y + size],
                     fill=(200, 160, 255))

    # ── БЛОК ИНСАЙТА ──
    # Рамка
    margin = 80
    box_top = 310
    box_bottom = H - 220
    box_w = W - margin * 2

    # Фон блока
    _draw_rounded_rect(draw, margin, box_top, W - margin, box_bottom,
                       radius=30, fill=(30, 15, 50, 180))

    # Декоративная полоса слева
    draw.rectangle([margin, box_top + 30, margin + 6, box_bottom - 30],
                   fill=(150, 80, 255))

    # Заголовок блока
    draw.text((W // 2, box_top + 55), "✨ МОЙ ИНСАЙТ", font=font_small,
              fill=(180, 130, 255), anchor="mm")

    # Текст инсайта — переносим по словам
    insight_clean = insight.replace("*", "").replace("_", "").replace("#", "")
    wrapped = _wrap_text(insight_clean, max_chars=38)

    line_height = 58
    total_height = len(wrapped) * line_height
    text_start_y = (box_top + box_bottom) // 2 - total_height // 2 + 20

    for i, line in enumerate(wrapped):
        y = text_start_y + i * line_height
        draw.text((W // 2, y), line, font=font_insight,
                  fill=(240, 220, 255), anchor="mm")

    # ── ИМЯ ПОЛЬЗОВАТЕЛЯ ──
    if user_name:
        draw.text((W // 2, box_bottom - 50), f"— {user_name}",
                  font=font_small, fill=(140, 100, 200), anchor="mm")

    # ── НИЖНИЙ БЛОК ──
    # Разделитель
    draw.line([(120, H - 190), (W - 120, H - 190)],
              fill=(80, 50, 140), width=1)

    # Текст призыва
    draw.text((W // 2, H - 155),
              "Узнай свой результат", font=font_small,
              fill=(160, 120, 220), anchor="mm")

    draw.text((W // 2, H - 105),
              "@mirrapsycholog_bot", font=font_subtitle,
              fill=(200, 160, 255), anchor="mm")

    # Маленькие точки декора
    for x in [W // 2 - 80, W // 2 - 40, W // 2, W // 2 + 40, W // 2 + 80]:
        draw.ellipse([x - 3, H - 55 - 3, x + 3, H - 55 + 3],
                     fill=(120, 80, 180))

    # ── СОХРАНЯЕМ ──
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_path = tmp.name
    tmp.close()
    img.save(tmp_path, "PNG", quality=95)
    return tmp_path


def _draw_circle(draw, cx, cy, r, color):
    """Рисуем круг (без alpha в PIL)"""
    r_val = color[0] if len(color) > 0 else 100
    g_val = color[1] if len(color) > 1 else 60
    b_val = color[2] if len(color) > 2 else 180
    draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                 outline=(r_val, g_val, b_val), width=1)


def _draw_rounded_rect(draw, x1, y1, x2, y2, radius, fill):
    """Прямоугольник со скруглёнными углами"""
    r = fill[:3] if len(fill) >= 3 else (30, 15, 50)
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=r)


def _get_font(size: int):
    """Пробуем найти хороший шрифт"""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _wrap_text(text: str, max_chars: int = 38) -> list:
    """Переносим текст по словам"""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = current + " " + word if current else word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    # Максимум 8 строк
    return lines[:8]
