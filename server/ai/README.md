# ai/

AI analysis module for Telugu news categorization and summarization.

| File | Purpose |
|------|---------|
| `telugu_ai_news_analyzer.py` | Main analyzer (2900 lines, runs as subprocess) |
| `article_generator.py` | Converts collector JSON → article.txt input format |
| `analyzer.py` | Facade for invoking the analyzer subprocess |

## Usage

The analyzer is invoked as a subprocess by pipeline runners. It reads `article.txt`
and produces categorized output in `news_output.json`, `statistics.json`, etc.
