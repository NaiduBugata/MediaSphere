# Telugu AI News Analyzer

Production-ready Telugu news analysis pipeline for processing OCR articles with Groq-backed semantic analysis, deterministic post-processing, and an automated news collection/orchestration layer.

## Project Overview

This package includes:
- A production analyzer for Telugu news data
- A Lokal News collector for retrieving recent articles
- An article generator for preparing analyzer input
- A pipeline orchestrator for unattended execution every 4 hours

## Features

- Groq-backed semantic analysis
- Validation and normalization of analysis output
- Duplicate detection and article filtering
- Automated CSV and article generation
- Fault-tolerant pipeline orchestration
- Portable relative-path configuration

## Folder Structure

- telugu_ai_news_analyzer.py: core analyzer
- lokal_news_collector.py: news fetcher
- generate_article_txt.py: article input generator
- orchestrator.py: production orchestrator
- run_pipeline.py: pipeline entrypoint
- config.py: centralized configuration
- tests/: regression tests
- output/: runtime output directory
- logs/: runtime logs

## Requirements

- Python 3.10+
- Windows, Linux, or macOS

## Installation

1. Create and activate a virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Environment Variables

Copy .env.example to .env and set your credentials:

```bash
copy .env.example .env
```

Required values:
- GROQ_API_KEY_1
- GROQ_API_KEY_2 (optional)
- WORKERS
- RETRY_COUNT
- CHECK_INTERVAL

## Running the Collector

```bash
python lokal_news_collector.py
```

## Running the Pipeline

```bash
python run_pipeline.py
```

## Running the Analyzer

```bash
python telugu_ai_news_analyzer.py --input article.txt --output-dir output
```

## Output Files

- output/: generated analyzer outputs
- logs/pipeline.log: orchestrator logs
- pipeline_status.json: latest pipeline report

## Troubleshooting

- Ensure .env exists with valid Groq credentials
- Ensure the output and logs directories are writable
- Re-run the collector and generator if no content is available

## License

This project is distributed under the MIT License.

## Author

Production release package for Telugu AI News Analyzer.
