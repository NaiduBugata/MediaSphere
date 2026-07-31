"""Legacy shim — re-exports from ai.article_generator for backward compatibility."""
# ruff: noqa: F401

from ai.article_generator import (  # noqa: F401
    generate_article_txt,
    generate_article_txt_from_json,
    generate_article_txt_from_youtube_json,
)

# Re-export config names that tests patch on this module
from config import ARTICLE_PATH, CSV_PATH  # noqa: F401
