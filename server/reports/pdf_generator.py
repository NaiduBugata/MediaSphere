"""PDF report generator using reportlab.

Produces Daily_Report_YYYY_MM_DD.pdf containing the executive summary,
statistics, problems, positive news, and the full article digest.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import config
from .data_service import format_location, format_time
from .logger import get_logger

logger = get_logger("reports.pdf")

PRIMARY = colors.HexColor(config.PRIMARY_COLOR)
SECONDARY = colors.HexColor(config.SECONDARY_COLOR)
BORDER = colors.HexColor(config.BORDER_COLOR)
MUTED = colors.HexColor(config.MUTED_COLOR)


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "MSTitle", parent=base["Title"], fontSize=20, textColor=PRIMARY, spaceAfter=2, alignment=TA_LEFT
        ),
        "subtitle": ParagraphStyle(
            "MSSub", parent=base["Normal"], fontSize=9, textColor=MUTED, spaceAfter=2
        ),
        "section": ParagraphStyle(
            "MSSection", parent=base["Heading2"], fontSize=13, textColor=PRIMARY, spaceBefore=14, spaceAfter=6
        ),
        "body": ParagraphStyle(
            "MSBody", parent=base["Normal"], fontSize=10, leading=15, textColor=colors.HexColor(config.TEXT_COLOR)
        ),
        "small": ParagraphStyle(
            "MSSmall", parent=base["Normal"], fontSize=8.5, leading=12, textColor=MUTED
        ),
        "item_title": ParagraphStyle(
            "MSItemTitle", parent=base["Normal"], fontSize=10.5, leading=14,
            textColor=colors.HexColor(config.TEXT_COLOR), spaceAfter=2,
        ),
    }


def _section(title: str, styles) -> list:
    return [
        Spacer(1, 4),
        Paragraph(title, styles["section"]),
        HRFlowable(width="100%", thickness=1, color=BORDER, spaceAfter=6),
    ]


def _stat_table(stats: dict[str, Any]) -> Table:
    data = [
        ["Total Articles", stats["total"], "Positive News", stats["positive"]],
        ["Negative News", stats["negative"], "Statement / Neutral", stats["statement"] + stats["neutral"]],
        ["Problems Identified", stats["problems"], "High Priority", stats["high_priority_problems"]],
        ["Districts Covered", stats["districts_covered"], "Mandals Covered", stats["mandals_covered"]],
        ["Villages Covered", stats["villages_covered"], "Most Active Category", stats["most_common_category"]],
    ]
    table = Table(data, colWidths=[45 * mm, 35 * mm, 45 * mm, 35 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), PRIMARY),
                ("TEXTCOLOR", (2, 0), (2, -1), PRIMARY),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, SECONDARY]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _kv_table(rows: list[list[str]], col_widths: list[float]) -> Table:
    table = Table(rows, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SECONDARY]),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def generate_pdf(
    target: date,
    generated_at: datetime,
    articles: list[dict],
    stats: dict[str, Any],
    executive_summary: str,
) -> Path:
    """Render the PDF report and return its path."""
    config.ensure_output_dir()
    filename = f"Daily_Report_{target.strftime('%Y_%m_%d')}.pdf"
    path = config.REPORT_OUTPUT_DIR / filename

    styles = _styles()
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"MediaSphere Daily Report {target.isoformat()}",
    )

    story: list = []
    story.append(Paragraph("MediaSphere", styles["title"]))
    story.append(Paragraph("AI Powered MP Constituency Monitoring System", styles["subtitle"]))
    story.append(Paragraph("Daily Intelligence Report", styles["subtitle"]))
    gen_time = generated_at.astimezone(config.REPORT_TIMEZONE).strftime("%d %b %Y, %I:%M %p IST")
    story.append(
        Paragraph(
            f"<b>Constituency:</b> {config.CONSTITUENCY_NAME} &nbsp;|&nbsp; "
            f"<b>Report Date:</b> {target.strftime('%d %B %Y')} &nbsp;|&nbsp; "
            f"<b>Generated:</b> {gen_time}",
            styles["small"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY, spaceBefore=8, spaceAfter=4))

    story += _section("Executive Summary", styles)
    story.append(Paragraph(executive_summary.replace("\n", "<br/>"), styles["body"]))

    story += _section("Key Metrics", styles)
    story.append(_stat_table(stats))

    story += _section("Action Required", styles)
    if stats["action_items"]:
        for item in stats["action_items"]:
            story.append(Paragraph(f"<b>{item['title']}</b>", styles["item_title"]))
            story.append(Paragraph(item.get("problem_summary") or "", styles["body"]))
            story.append(
                Paragraph(
                    f"<b>Priority:</b> {item['priority']} &nbsp;|&nbsp; "
                    f"<b>Category:</b> {item['category']} &nbsp;|&nbsp; "
                    f"<b>Location:</b> {format_location(item['location'])}<br/>"
                    f"<b>Department:</b> {item['department']} &nbsp;|&nbsp; "
                    f"<b>Published:</b> {format_time(item)}",
                    styles["small"],
                )
            )
            story.append(Spacer(1, 6))
    else:
        story.append(Paragraph("No actionable issues were reported for this period.", styles["small"]))

    story += _section("Positive Developments", styles)
    if stats["positive_items"]:
        for item in stats["positive_items"]:
            story.append(Paragraph(f"<b>{item['title']}</b>", styles["item_title"]))
            story.append(Paragraph(item.get("summary") or "", styles["body"]))
            story.append(
                Paragraph(
                    f"<b>Category:</b> {item['category']} &nbsp;|&nbsp; "
                    f"<b>Location:</b> {format_location(item['location'])}",
                    styles["small"],
                )
            )
            story.append(Spacer(1, 6))
    else:
        story.append(Paragraph("No positive developments were recorded for this period.", styles["small"]))

    story += _section("Category Summary", styles)
    cat_rows = [["Category", "Articles"]] + [[c["name"], str(c["count"])] for c in stats["category_summary"]]
    story.append(_kv_table(cat_rows, [110 * mm, 50 * mm]))

    story += _section("Location & Sentiment Summary", styles)
    loc_rows = [
        ["Metric", "Value"],
        ["Most Affected District", stats["most_affected_district"]],
        ["Most Affected Mandal", stats["most_affected_mandal"]],
        ["Most Affected Village", stats["most_affected_village"]],
        ["Positive Share", f"{stats['sentiment_pct']['Positive']}%"],
        ["Negative Share", f"{stats['sentiment_pct']['Negative']}%"],
        ["Statement Share", f"{stats['sentiment_pct']['Statement']}%"],
        ["Neutral Share", f"{stats['sentiment_pct']['Neutral']}%"],
    ]
    story.append(_kv_table(loc_rows, [110 * mm, 50 * mm]))

    if stats["top_keywords"]:
        story += _section("Top Keywords", styles)
        kw = ", ".join(f"{k['name']} ({k['count']})" for k in stats["top_keywords"])
        story.append(Paragraph(kw, styles["body"]))

    if stats["top_entities"]:
        story += _section("Top Entities", styles)
        en = ", ".join(f"{e['name']} ({e['count']})" for e in stats["top_entities"])
        story.append(Paragraph(en, styles["body"]))

    story += _section("Article Digest", styles)
    if articles:
        for article in articles:
            story.append(Paragraph(f"<b>{article['title']}</b>", styles["item_title"]))
            story.append(Paragraph(article.get("summary") or "", styles["body"]))
            meta = (
                f"<b>Category:</b> {article.get('category', 'Others')} &nbsp;|&nbsp; "
                f"<b>Sentiment:</b> {article.get('sentiment') or 'Unknown'} &nbsp;|&nbsp; "
                f"<b>Location:</b> {format_location(article['location'])} &nbsp;|&nbsp; "
                f"<b>Published:</b> {format_time(article)}"
            )
            if article.get("source_url"):
                meta += f'<br/><link href="{article["source_url"]}" color="#1E3A8A">Read original article</link>'
            story.append(Paragraph(meta, styles["small"]))
            story.append(Spacer(1, 8))
    else:
        story.append(Paragraph("No articles were recorded for this period.", styles["small"]))

    doc.build(story)
    logger.info("PDF report written to %s", path)
    return path
