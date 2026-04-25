import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Цвета Mirra
PURPLE_DARK = colors.HexColor("#4A235A")
PURPLE_MID = colors.HexColor("#7D3C98")
PURPLE_LIGHT = colors.HexColor("#D7BDE2")
PURPLE_BG = colors.HexColor("#F5EEF8")
GRAY = colors.HexColor("#888888")
WHITE = colors.white

MODE_NAMES = {
    "psychologist": "🧠 Психолог",
    "iching": "🔮 И-Цзин",
    "mak": "🃏 МАК-карта",
    "numerology": "🔢 Нумерология",
    "meditation": "🧘 Медитация",
    "diary_followup": "📖 Дневник",
    "mood": "😊 Настроение",
    "day": "📝 День",
}

MOOD_EMOJI = {
    "😊 Хорошо": "😊",
    "😐 Нормально": "😐",
    "😔 Грустно": "😔",
    "😰 Тревожно": "😰",
    "😤 Злюсь": "😤",
    "😴 Устала": "😴",
}


def generate_diary_pdf(user_name: str, dialogs: list, diary_entries: list, output_path: str):
    """Генерируем красивый PDF дневника"""

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=15*mm,
        bottomMargin=15*mm,
    )

    # Стили
    styles = _build_styles()
    story = []

    # ── ОБЛОЖКА ──
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph("🌙 MIRRA", styles["title_main"]))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("Личный дневник", styles["subtitle"]))
    story.append(Spacer(1, 5*mm))

    month_year = datetime.now().strftime("%B %Y")
    story.append(Paragraph(f"{user_name}  •  {month_year}", styles["meta"]))
    story.append(Spacer(1, 8*mm))
    story.append(HRFlowable(width="100%", thickness=2, color=PURPLE_MID))
    story.append(Spacer(1, 10*mm))

    # ── СТАТИСТИКА ──
    modes_used = {}
    for d in dialogs:
        m = d.get("mode", "")
        modes_used[m] = modes_used.get(m, 0) + 1

    moods = [e for e in diary_entries if e.get("entry_type") == "mood"]
    day_entries = [e for e in diary_entries if e.get("entry_type") == "day"]

    story.append(Paragraph("Твой месяц в цифрах", styles["section_header"]))
    story.append(Spacer(1, 4*mm))

    stats_data = [
        ["Всего диалогов", str(len(dialogs))],
        ["Записей в дневнике", str(len(day_entries))],
        ["Отметок настроения", str(len(moods))],
    ]
    for mode, count in modes_used.items():
        name = MODE_NAMES.get(mode, mode)
        stats_data.append([name, str(count)])

    stats_table = Table(stats_data, colWidths=[120*mm, 30*mm])
    stats_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PURPLE_BG),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [PURPLE_BG, WHITE]),
        ("TEXTCOLOR", (0, 0), (-1, -1), PURPLE_DARK),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (0, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, PURPLE_LIGHT),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 10*mm))

    # ── НАСТРОЕНИЯ ──
    if moods:
        story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE_LIGHT))
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("Настроение месяца", styles["section_header"]))
        story.append(Spacer(1, 4*mm))

        mood_counts = {}
        for m in moods:
            mood = m.get("mood", "")
            mood_counts[mood] = mood_counts.get(mood, 0) + 1

        mood_text = "  ".join([f"{mood} × {cnt}" for mood, cnt in mood_counts.items()])
        story.append(Paragraph(mood_text, styles["body"]))
        story.append(Spacer(1, 8*mm))

    # ── ЗАПИСИ ДНЕВНИКА ──
    if day_entries:
        story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE_LIGHT))
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("Записи дней", styles["section_header"]))
        story.append(Spacer(1, 4*mm))

        for entry in day_entries:
            date_str = ""
            if entry.get("created_at"):
                d = entry["created_at"]
                if isinstance(d, str):
                    d = datetime.fromisoformat(d)
                date_str = d.strftime("%d %B")

            story.append(Paragraph(f"● {date_str}", styles["date_label"]))
            content = entry.get("content", "").replace("*", "").replace("_", "")
            story.append(Paragraph(content, styles["diary_entry"]))
            story.append(Spacer(1, 4*mm))

    # ── ДИАЛОГИ ──
    if dialogs:
        story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE_LIGHT))
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("Все диалоги с Mirra", styles["section_header"]))
        story.append(Spacer(1, 4*mm))

        # Группируем по дням
        by_day = {}
        for d in dialogs:
            date_obj = d.get("created_at")
            if isinstance(date_obj, str):
                date_obj = datetime.fromisoformat(date_obj)
            day = date_obj.strftime("%d %B") if date_obj else "—"
            by_day.setdefault(day, []).append(d)

        for day, day_dialogs in by_day.items():
            story.append(Paragraph(day, styles["day_header"]))
            for d in day_dialogs:
                mode = MODE_NAMES.get(d.get("mode", ""), d.get("mode", ""))
                story.append(Paragraph(f"<b>{mode}</b>", styles["mode_label"]))

                user_msg = d.get("user_message", "")[:300].replace("*", "").replace("_", "")
                story.append(Paragraph(f"Ты: {user_msg}", styles["user_msg"]))

                bot_msg = d.get("bot_response", "")[:400].replace("*", "").replace("_", "").replace("#", "")
                story.append(Paragraph(f"Mirra: {bot_msg}", styles["bot_msg"]))
                story.append(Spacer(1, 3*mm))

    # ── ФУТЕР ──
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=PURPLE_MID))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        f"Создано Mirra • {datetime.now().strftime('%d.%m.%Y')} • Следующий дневник придёт через месяц 💜",
        styles["footer"]
    ))

    doc.build(story)
    return output_path


def _build_styles():
    return {
        "title_main": ParagraphStyle(
            "title_main", fontSize=28, textColor=PURPLE_DARK,
            alignment=TA_CENTER, spaceAfter=4, fontName="Helvetica-Bold"
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontSize=14, textColor=PURPLE_MID,
            alignment=TA_CENTER, spaceAfter=4, fontName="Helvetica"
        ),
        "meta": ParagraphStyle(
            "meta", fontSize=10, textColor=GRAY,
            alignment=TA_CENTER, fontName="Helvetica"
        ),
        "section_header": ParagraphStyle(
            "section_header", fontSize=13, textColor=PURPLE_DARK,
            fontName="Helvetica-Bold", spaceBefore=4, spaceAfter=4
        ),
        "day_header": ParagraphStyle(
            "day_header", fontSize=11, textColor=PURPLE_MID,
            fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=2,
            backColor=PURPLE_BG, leftIndent=4, rightIndent=4,
        ),
        "mode_label": ParagraphStyle(
            "mode_label", fontSize=9, textColor=PURPLE_MID,
            fontName="Helvetica", spaceAfter=1
        ),
        "user_msg": ParagraphStyle(
            "user_msg", fontSize=9, textColor=colors.HexColor("#333333"),
            fontName="Helvetica", leftIndent=8, spaceAfter=2
        ),
        "bot_msg": ParagraphStyle(
            "bot_msg", fontSize=9, textColor=PURPLE_DARK,
            fontName="Helvetica", leftIndent=8, spaceAfter=2
        ),
        "diary_entry": ParagraphStyle(
            "diary_entry", fontSize=10, textColor=colors.HexColor("#333333"),
            fontName="Helvetica", leftIndent=12, spaceAfter=2,
            backColor=PURPLE_BG,
        ),
        "date_label": ParagraphStyle(
            "date_label", fontSize=10, textColor=PURPLE_MID,
            fontName="Helvetica-Bold", spaceAfter=1
        ),
        "body": ParagraphStyle(
            "body", fontSize=10, textColor=colors.HexColor("#333333"),
            fontName="Helvetica", spaceAfter=4
        ),
        "footer": ParagraphStyle(
            "footer", fontSize=8, textColor=GRAY,
            alignment=TA_CENTER, fontName="Helvetica"
        ),
    }
