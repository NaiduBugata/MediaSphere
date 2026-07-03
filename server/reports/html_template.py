"""Professional HTML email builder for the daily report.

Uses table-based layout and inline styles for maximum compatibility with
Gmail and Outlook. Branded with the MediaSphere colors.
"""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Any

from . import config
from .data_service import format_location, format_time

PRIMARY = config.PRIMARY_COLOR
SECONDARY = config.SECONDARY_COLOR
BORDER = config.BORDER_COLOR
TEXT = config.TEXT_COLOR
MUTED = config.MUTED_COLOR

PRIORITY_BG = {"High": "#1E3A8A", "Medium": "#3B82F6", "Low": "#94A3B8"}
SENTIMENT_BG = {
    "Positive": "#1E3A8A",
    "Negative": "#334155",
    "Problem": "#334155",
    "Statement": "#64748B",
    "Neutral": "#94A3B8",
}


def _e(value: Any) -> str:
    return escape(str(value if value is not None else ""))


def _section_title(title: str) -> str:
    return (
        f'<tr><td style="padding:24px 24px 8px 24px;">'
        f'<h2 style="margin:0;font-size:16px;font-weight:700;color:{PRIMARY};'
        f'text-transform:uppercase;letter-spacing:0.5px;">{_e(title)}</h2>'
        f'<div style="height:2px;width:48px;background:{PRIMARY};margin-top:6px;"></div>'
        f"</td></tr>"
    )


def _metric_cell(label: str, value: Any) -> str:
    return (
        f'<td width="33%" style="padding:8px;">'
        f'<div style="border:1px solid {BORDER};border-radius:8px;padding:14px;background:{SECONDARY};">'
        f'<div style="font-size:24px;font-weight:700;color:{PRIMARY};">{_e(value)}</div>'
        f'<div style="font-size:12px;color:{MUTED};margin-top:2px;">{_e(label)}</div>'
        f"</div></td>"
    )


def _metrics_grid(stats: dict[str, Any]) -> str:
    metrics = [
        ("Total Articles", stats["total"]),
        ("Positive News", stats["positive"]),
        ("Negative News", stats["negative"]),
        ("Statement / Neutral", stats["statement"] + stats["neutral"]),
        ("Problems Identified", stats["problems"]),
        ("High Priority", stats["high_priority_problems"]),
        ("Districts Covered", stats["districts_covered"]),
        ("Mandals Covered", stats["mandals_covered"]),
        ("Villages Covered", stats["villages_covered"]),
    ]
    rows = []
    for i in range(0, len(metrics), 3):
        cells = "".join(_metric_cell(label, value) for label, value in metrics[i : i + 3])
        rows.append(f"<tr>{cells}</tr>")
    return (
        f'<tr><td style="padding:0 16px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'
        f"</td></tr>"
    )


def _badge(text: str, bg: str) -> str:
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:10px;'
        f'background:{bg};color:#ffffff;font-size:11px;font-weight:600;">{_e(text)}</span>'
    )


def _action_items(stats: dict[str, Any]) -> str:
    items = stats["action_items"]
    if not items:
        return (
            '<tr><td style="padding:0 24px 8px 24px;color:%s;font-size:14px;">'
            "No actionable issues were reported for this period.</td></tr>" % MUTED
        )
    cards = []
    for item in items:
        priority = item.get("priority", "Low")
        cards.append(
            f'<tr><td style="padding:8px 24px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border:1px solid {BORDER};border-left:4px solid {PRIMARY};border-radius:8px;">'
            f'<tr><td style="padding:14px;">'
            f'<div style="font-size:14px;font-weight:700;color:{TEXT};margin-bottom:6px;">{_e(item["title"])}</div>'
            f'<div style="font-size:13px;color:{TEXT};line-height:1.5;margin-bottom:8px;">{_e(item["problem_summary"])}</div>'
            f'<div style="margin-bottom:8px;">{_badge(priority + " Priority", PRIORITY_BG.get(priority, "#94A3B8"))}'
            f'&nbsp;{_badge(item["category"], PRIMARY)}</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;color:{MUTED};">'
            f'<tr><td style="padding:1px 0;"><strong style="color:{TEXT};">Location:</strong> {_e(format_location(item["location"]))}</td></tr>'
            f'<tr><td style="padding:1px 0;"><strong style="color:{TEXT};">Department:</strong> {_e(item["department"])}</td></tr>'
            f'<tr><td style="padding:1px 0;"><strong style="color:{TEXT};">Published:</strong> {_e(format_time(item))}</td></tr>'
            f"</table>"
            f"</td></tr></table></td></tr>"
        )
    return "".join(cards)


def _positive_items(stats: dict[str, Any]) -> str:
    items = stats["positive_items"]
    if not items:
        return (
            '<tr><td style="padding:0 24px 8px 24px;color:%s;font-size:14px;">'
            "No positive developments were recorded for this period.</td></tr>" % MUTED
        )
    cards = []
    for item in items:
        cards.append(
            f'<tr><td style="padding:8px 24px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border:1px solid {BORDER};border-radius:8px;background:{SECONDARY};">'
            f'<tr><td style="padding:14px;">'
            f'<div style="font-size:14px;font-weight:700;color:{TEXT};margin-bottom:4px;">{_e(item["title"])}</div>'
            f'<div style="font-size:13px;color:{TEXT};line-height:1.5;margin-bottom:6px;">{_e(item["summary"])}</div>'
            f'<div style="font-size:12px;color:{MUTED};">{_badge(item["category"], PRIMARY)}&nbsp;&nbsp;{_e(format_location(item["location"]))}</div>'
            f"</td></tr></table></td></tr>"
        )
    return "".join(cards)


def _simple_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(
        f'<th align="left" style="padding:8px 12px;font-size:12px;color:#ffffff;background:{PRIMARY};">{_e(h)}</th>'
        for h in headers
    )
    body = []
    for idx, row in enumerate(rows):
        bg = "#ffffff" if idx % 2 == 0 else SECONDARY
        cells = "".join(
            f'<td style="padding:8px 12px;font-size:13px;color:{TEXT};border-bottom:1px solid {BORDER};">{_e(c)}</td>'
            for c in row
        )
        body.append(f'<tr style="background:{bg};">{cells}</tr>')
    return (
        f'<tr><td style="padding:0 24px 8px 24px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="border:1px solid {BORDER};border-radius:8px;overflow:hidden;">'
        f"<tr>{head}</tr>{''.join(body)}</table></td></tr>"
    )


def _chips(items: list[dict]) -> str:
    if not items:
        return f'<tr><td style="padding:0 24px 8px 24px;color:{MUTED};font-size:13px;">None</td></tr>'
    chips = "".join(
        f'<span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:12px;'
        f'background:{SECONDARY};border:1px solid {BORDER};font-size:12px;color:{PRIMARY};">'
        f'{_e(item["name"])} ({item["count"]})</span>'
        for item in items
    )
    return f'<tr><td style="padding:0 24px 8px 24px;">{chips}</td></tr>'


def _digest(articles: list[dict]) -> str:
    if not articles:
        return f'<tr><td style="padding:0 24px 16px 24px;color:{MUTED};font-size:13px;">No articles.</td></tr>'
    cards = []
    for article in articles:
        sentiment = article.get("sentiment", "")
        link = article.get("source_url") or ""
        link_html = (
            f'<a href="{_e(link)}" style="color:{PRIMARY};font-size:12px;text-decoration:none;">Read original &rarr;</a>'
            if link
            else ""
        )
        cards.append(
            f'<tr><td style="padding:6px 24px;">'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-bottom:1px solid {BORDER};">'
            f'<tr><td style="padding:10px 0;">'
            f'<div style="font-size:14px;font-weight:600;color:{TEXT};margin-bottom:4px;">{_e(article["title"])}</div>'
            f'<div style="font-size:13px;color:{TEXT};line-height:1.5;margin-bottom:6px;">{_e(article["summary"])}</div>'
            f'<div style="font-size:12px;color:{MUTED};">'
            f'{_badge(article.get("category", "Others"), PRIMARY)}&nbsp;'
            f'{_badge(sentiment or "Unknown", SENTIMENT_BG.get(sentiment, "#94A3B8"))}&nbsp;&nbsp;'
            f'{_e(format_location(article["location"]))} &middot; {_e(format_time(article))}</div>'
            f'<div style="margin-top:4px;">{link_html}</div>'
            f"</td></tr></table></td></tr>"
        )
    return "".join(cards)


def _incremental_metrics(stats: dict[str, Any]) -> str:
    metrics = [
        ("Total New Articles", stats["total"]),
        ("Positive News", stats["positive"]),
        ("Negative News", stats["negative"]),
        ("Statements / Neutral", stats["statement"] + stats["neutral"]),
        ("Problems Identified", stats["problems"]),
        ("High Priority Problems", stats["high_priority_problems"]),
    ]
    rows = []
    for i in range(0, len(metrics), 3):
        cells = "".join(_metric_cell(label, value) for label, value in metrics[i : i + 3])
        rows.append(f"<tr>{cells}</tr>")
    return (
        f'<tr><td style="padding:0 16px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{"".join(rows)}</table>'
        f"</td></tr>"
    )


def _article_card(article: dict) -> str:
    sentiment = article.get("sentiment", "")
    is_problem = bool(article.get("is_problem"))
    priority = article.get("priority", "Low")
    link = article.get("source_url") or ""
    location = article.get("location") or {}

    border = f"border:1px solid {BORDER};" if not is_problem else "border:1px solid #FCA5A5;border-left:4px solid #DC2626;"
    bg = "#ffffff" if not is_problem else "#FEF2F2"

    loc_rows = "".join(
        f'<tr><td style="padding:1px 0;font-size:12px;color:{MUTED};">'
        f'<strong style="color:{TEXT};">{label}:</strong> {_e(value)}</td></tr>'
        for label, value in (
            ("District", location.get("district") or "—"),
            ("Mandal", location.get("mandal") or "—"),
            ("Village", location.get("village") or location.get("town") or "—"),
        )
    )

    problem_block = ""
    if is_problem:
        problem_block = (
            f'<div style="margin-top:8px;padding:10px;background:#ffffff;border:1px solid #FECACA;border-radius:6px;">'
            f'<div style="font-size:11px;font-weight:700;color:#B91C1C;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:4px;">Problem Details</div>'
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:12px;color:{TEXT};">'
            f'<tr><td style="padding:1px 0;"><strong>Problem Summary:</strong> {_e(article.get("problem_summary") or "—")}</td></tr>'
            f'<tr><td style="padding:1px 0;"><strong>Responsible Department:</strong> {_e(article.get("department") or "—")}</td></tr>'
            f'<tr><td style="padding:1px 0;"><strong>Priority:</strong> {_e(priority)}</td></tr>'
            f'<tr><td style="padding:1px 0;"><strong>Action Required:</strong> {_e(article.get("recommended_action") or "—")}</td></tr>'
            f"</table></div>"
        )

    link_html = (
        f'<a href="{_e(link)}" style="display:inline-block;margin-top:8px;color:{PRIMARY};font-size:12px;font-weight:600;text-decoration:none;">Open Original Article &rarr;</a>'
        if link
        else ""
    )

    subcategory = f' &middot; {_e(article.get("subcategory"))}' if article.get("subcategory") else ""

    return (
        f'<tr><td style="padding:8px 24px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="{border}border-radius:8px;background:{bg};">'
        f'<tr><td style="padding:14px;">'
        f'<div style="font-size:15px;font-weight:700;color:{TEXT};margin-bottom:6px;">{_e(article.get("title"))}</div>'
        f'<div style="margin-bottom:8px;">'
        f'{_badge(sentiment or "Unknown", SENTIMENT_BG.get(sentiment, "#94A3B8"))}&nbsp;'
        f'{_badge(article.get("category", "Others"), PRIMARY)}'
        f'{("&nbsp;" + _badge(priority + " Priority", PRIORITY_BG.get(priority, "#94A3B8"))) if is_problem else ""}</div>'
        f'<div style="font-size:13px;color:{TEXT};line-height:1.5;margin-bottom:8px;">{_e(article.get("summary"))}</div>'
        f'<div style="font-size:12px;color:{MUTED};margin-bottom:6px;"><strong style="color:{TEXT};">Category:</strong> '
        f'{_e(article.get("category", "Others"))}{subcategory}</div>'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0">{loc_rows}</table>'
        f'<div style="font-size:12px;color:{MUTED};margin-top:6px;"><strong style="color:{TEXT};">Published:</strong> {_e(format_time(article))}</div>'
        f"{problem_block}"
        f"{link_html}"
        f"</td></tr></table></td></tr>"
    )


def build_incremental_html(
    generated_at: datetime,
    articles: list[dict],
    stats: dict[str, Any],
    executive_summary: str,
) -> str:
    """Assemble the incremental (per-cycle) HTML update email."""
    gen_time = generated_at.astimezone(config.REPORT_TIMEZONE).strftime("%d %b %Y, %I:%M %p IST")
    cards = "".join(_article_card(a) for a in articles)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>MediaSphere News Update</title>
</head>
<body style="margin:0;padding:0;background:{SECONDARY};font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{SECONDARY};padding:16px 0;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border:1px solid {BORDER};border-radius:12px;overflow:hidden;">

<tr><td style="background:{PRIMARY};padding:24px;">
<div style="font-size:20px;font-weight:800;color:#ffffff;letter-spacing:0.5px;">MediaSphere</div>
<div style="font-size:12px;color:#C7D2FE;margin-top:2px;">AI Powered MP Constituency Monitoring System</div>
<div style="font-size:15px;color:#ffffff;font-weight:600;margin-top:10px;">News Update &middot; Latest Monitoring Cycle</div>
<div style="font-size:12px;color:#C7D2FE;margin-top:4px;"><strong style="color:#ffffff;">Generated:</strong> {gen_time}</div>
</td></tr>

<tr><td style="padding:20px 24px 4px 24px;">
<div style="background:{SECONDARY};border:1px solid {BORDER};border-left:4px solid {PRIMARY};border-radius:8px;padding:14px;font-size:14px;line-height:1.6;color:{TEXT};">{_e(executive_summary)}</div>
</td></tr>

{_section_title("Summary Statistics")}
{_incremental_metrics(stats)}

{_section_title("New Articles")}
{cards}

<tr><td style="background:{PRIMARY};padding:16px 24px;">
<div style="font-size:12px;color:#C7D2FE;">Automated incremental update from MediaSphere for {_e(config.CONSTITUENCY_NAME)} constituency. A consolidated executive report is delivered daily at 07:00 IST.</div>
<div style="font-size:11px;color:#93A3D8;margin-top:4px;">&copy; MediaSphere &middot; AI Powered MP Constituency Monitoring System</div>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def build_email_html(
    target: date,
    generated_at: datetime,
    articles: list[dict],
    stats: dict[str, Any],
    executive_summary: str,
) -> str:
    """Assemble the full branded HTML email."""
    report_date = target.strftime("%d %B %Y")
    gen_time = generated_at.astimezone(config.REPORT_TIMEZONE).strftime("%d %b %Y, %I:%M %p IST")

    category_rows = [[c["name"], str(c["count"])] for c in stats["category_summary"]]
    location_rows = [
        ["Most Affected District", stats["most_affected_district"]],
        ["Most Affected Mandal", stats["most_affected_mandal"]],
        ["Most Affected Village", stats["most_affected_village"]],
    ]
    top_mandal_rows = [[m["name"], str(m["count"])] for m in stats["top_mandals"]]
    top_village_rows = [[v["name"], str(v["count"])] for v in stats["top_villages"]]
    sentiment_rows = [
        ["Positive", f"{stats['sentiment_pct']['Positive']}%"],
        ["Negative", f"{stats['sentiment_pct']['Negative']}%"],
        ["Statement", f"{stats['sentiment_pct']['Statement']}%"],
        ["Neutral", f"{stats['sentiment_pct']['Neutral']}%"],
    ]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>MediaSphere Daily Constituency Report</title>
</head>
<body style="margin:0;padding:0;background:{SECONDARY};font-family:Arial,Helvetica,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{SECONDARY};padding:16px 0;">
<tr><td align="center">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#ffffff;border:1px solid {BORDER};border-radius:12px;overflow:hidden;">

<tr><td style="background:{PRIMARY};padding:28px 24px;">
<div style="font-size:22px;font-weight:800;color:#ffffff;letter-spacing:0.5px;">MediaSphere</div>
<div style="font-size:12px;color:#C7D2FE;margin-top:2px;">AI Powered MP Constituency Monitoring System</div>
<div style="font-size:15px;color:#ffffff;font-weight:600;margin-top:12px;">Daily Intelligence Report</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
<tr>
<td style="font-size:12px;color:#C7D2FE;"><strong style="color:#ffffff;">Report Date:</strong> {report_date}</td>
<td align="right" style="font-size:12px;color:#C7D2FE;"><strong style="color:#ffffff;">Generated:</strong> {gen_time}</td>
</tr>
</table>
</td></tr>

{_section_title("Executive Summary")}
<tr><td style="padding:0 24px 8px 24px;">
<div style="background:{SECONDARY};border:1px solid {BORDER};border-left:4px solid {PRIMARY};border-radius:8px;padding:16px;font-size:14px;line-height:1.6;color:{TEXT};">{_e(executive_summary)}</div>
</td></tr>

{_section_title("Key Metrics")}
{_metrics_grid(stats)}

{_section_title("Action Required")}
{_action_items(stats)}

{_section_title("Positive Developments")}
{_positive_items(stats)}

{_section_title("Category Summary")}
{_simple_table(["Category", "Articles"], category_rows)}

{_section_title("Location Summary")}
{_simple_table(["Metric", "Location"], location_rows)}
{_simple_table(["Top Mandals", "Articles"], top_mandal_rows) if top_mandal_rows else ""}
{_simple_table(["Top Villages", "Articles"], top_village_rows) if top_village_rows else ""}

{_section_title("Sentiment Summary")}
{_simple_table(["Sentiment", "Share"], sentiment_rows)}

{_section_title("Top Keywords")}
{_chips(stats["top_keywords"])}

{_section_title("Top Entities")}
{_chips(stats["top_entities"])}

{_section_title("Article Digest")}
{_digest(articles)}

<tr><td style="background:{PRIMARY};padding:18px 24px;margin-top:16px;">
<div style="font-size:12px;color:#C7D2FE;">This is an automated report generated by MediaSphere for {_e(config.CONSTITUENCY_NAME)} constituency.</div>
<div style="font-size:11px;color:#93A3D8;margin-top:4px;">&copy; MediaSphere &middot; AI Powered MP Constituency Monitoring System</div>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
