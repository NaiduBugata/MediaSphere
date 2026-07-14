"""AI analysis module: Groq-backed Telugu news categorizer and summarizer.

The main analyzer is invoked as a subprocess by pipeline runners.
Article text generation converts collector JSON into the analyzer's input format.
"""

from ai.article_generator import (  # noqa: F401
    generate_article_txt,
    generate_article_txt_from_json,
    generate_article_txt_from_youtube_json,
)
