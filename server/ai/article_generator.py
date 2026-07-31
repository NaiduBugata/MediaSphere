import csv
import json
from pathlib import Path

from config import ARTICLE_PATH, CSV_PATH


def generate_article_txt(csv_path: Path = CSV_PATH, article_path: Path = ARTICLE_PATH) -> Path:
    article_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    blocks: list[str] = []
    for row in rows:
        title = (row.get("title") or "").strip()
        content = (row.get("content") or "").strip()
        date_value = (row.get("date") or "").strip()
        if not title and not content:
            continue
        block = [
            "====================================================",
            "Title",
            title,
            "Date",
            date_value,
            "Content",
            content,
        ]
        blocks.append("\n".join(block))

    body = "\n\n".join(blocks)
    article_path.write_text(body, encoding="utf-8")
    return article_path


def generate_article_txt_from_json(json_path: Path, article_path: Path = ARTICLE_PATH) -> Path:
    """
    Build an analyzer-ready article.txt from the Lokal collector JSON.

    Purpose:
        Convert collected JSON articles into the dash-separated TITLE:/CONTENT:
        format expected by telugu_ai_news_analyzer.py.

    Parameters:
        json_path: Path to the Lokal collector JSON file.
        article_path: Destination path for the generated article.txt.

    Returns:
        Path to the written article.txt file.
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))
    articles = data.get("articles", [])
    blocks: list[str] = []

    for item in articles:
        title = (item.get("title") or "").strip()
        content = (item.get("content") or "").strip()
        if not title and not content:
            continue
        blocks.append(
            "----------------------------------------\n"
            f"TITLE: {title}\n\n"
            f"CONTENT: {content}"
        )

    article_path.parent.mkdir(parents=True, exist_ok=True)
    article_path.write_text("\n".join(blocks), encoding="utf-8")
    return article_path


def generate_article_txt_from_youtube_json(
    json_path: Path,
    article_path: Path,
    min_chars: int = 100,
) -> Path:
    """Build analyzer input from YouTube collector JSON (news-only articles)."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    articles = data.get("articles", [])
    blocks: list[str] = []

    max_content_chars = 0
    try:
        from youtube import config as yt_config

        max_content_chars = yt_config.YOUTUBE_MAX_CONTENT_CHARS
    except ImportError:
        max_content_chars = 12000

    for item in articles:
        title = (item.get("title") or "").strip()
        content = (item.get("content") or "").strip()
        if not title or len(content) < min_chars:
            continue
        if max_content_chars > 0 and len(content) > max_content_chars:
            content = content[:max_content_chars].rsplit(" ", 1)[0] + "…"
        blocks.append(
            "----------------------------------------\n"
            f"TITLE: {title}\n\n"
            f"CONTENT: {content}"
        )

    article_path.parent.mkdir(parents=True, exist_ok=True)
    article_path.write_text("\n".join(blocks), encoding="utf-8")
    return article_path


if __name__ == "__main__":
    generate_article_txt()
