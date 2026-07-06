import csv
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


if __name__ == "__main__":
    generate_article_txt()
