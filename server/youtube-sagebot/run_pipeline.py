"""Full Telugu YouTube news pipeline orchestrator."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import config
from clean_transcripts import TranscriptCleaner
from collect_news import run_collect
from deduplicate_stories import StoryDeduplicator
from generate_articles import ArticleGenerator
from search_youtube import run_search


def _load_transcript_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return list(data.values())
    return []


def _save_transcript_list(path: Path, items: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


class NewsPipeline:
    def __init__(self, days_back: int = 2):
        self.days_back = days_back
        self.data_dir = Path(config.DATA_DIR)
        self.data_dir.mkdir(exist_ok=True)

        self.cleaner = TranscriptCleaner()
        self._deduplicator: StoryDeduplicator | None = None
        self._generator: ArticleGenerator | None = None

        self.log_file = self.data_dir / "pipeline.log"

    @property
    def deduplicator(self) -> StoryDeduplicator:
        if self._deduplicator is None:
            self._deduplicator = StoryDeduplicator(similarity_threshold=config.SIMILARITY_THRESHOLD)
        return self._deduplicator

    @property
    def generator(self) -> ArticleGenerator | None:
        if self._generator is None and config.GROQ_API_KEY:
            self._generator = ArticleGenerator(config.GROQ_API_KEY)
        return self._generator

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
        print(f"[{timestamp}] {message}")

    def stage1_search(self) -> list[dict]:
        self.log("Stage 1: Searching YouTube...")
        run_search(["--days", str(self.days_back)])
        videos_path = self.data_dir / "videos.json"
        with open(videos_path, "r", encoding="utf-8") as f:
            videos = json.load(f)
        self.log(f"Total unique videos: {len(videos)}")
        return videos

    def stage2_collect_transcripts(self) -> list[dict]:
        self.log("Stage 2: Collecting transcripts...")
        transcripts = run_collect()
        self.log(f"Total transcripts: {len(transcripts)}")
        return transcripts

    def stage3_clean_transcripts(self) -> list[dict]:
        self.log("Stage 3: Cleaning transcripts...")
        transcripts = _load_transcript_list(self.data_dir / "transcripts.json")
        clean_transcripts: list[dict] = []
        news_count = 0
        non_news_count = 0

        for data in transcripts:
            result = self.cleaner.clean(
                data.get("transcript", ""),
                data.get("title", ""),
                data.get("channel", ""),
            )
            if result["is_news"]:
                clean_transcripts.append({
                    **data,
                    "clean_text": result["clean_text"],
                    "is_news": True,
                    "category": result.get("category", "general"),
                })
                news_count += 1
            else:
                non_news_count += 1
                self.log(f"  Filtered: {data.get('title', '')[:60]}... (not news)")

        _save_transcript_list(self.data_dir / "clean_transcripts.json", clean_transcripts)
        self.log(f"News transcripts: {news_count}, Filtered out: {non_news_count}")
        return clean_transcripts

    def stage4_deduplicate(self) -> list[dict]:
        self.log("Stage 4: Deduplicating stories...")
        clean = _load_transcript_list(self.data_dir / "clean_transcripts.json")
        unique_stories = self.deduplicator.deduplicate(clean)
        with open(self.data_dir / "unique_stories.json", "w", encoding="utf-8") as f:
            json.dump(unique_stories, f, ensure_ascii=False, indent=2)
        self.log(f"Unique stories found: {len(unique_stories)}")
        return unique_stories

    def stage5_generate_articles(self, limit: int | None = None) -> dict:
        if not self.generator:
            self.log("Stage 5 skipped: GROQ_API_KEY not set.")
            return {}

        self.log("Stage 5: Generating articles...")
        with open(self.data_dir / "unique_stories.json", "r", encoding="utf-8") as f:
            unique_stories = json.load(f)

        articles_path = self.data_dir / "articles.json"
        articles: dict = {}
        if articles_path.exists():
            with open(articles_path, "r", encoding="utf-8") as f:
                articles = json.load(f)

        stories_to_process = unique_stories[:limit] if limit else unique_stories

        for story in stories_to_process:
            story_id = story["story_id"]
            if story_id in articles:
                self.log(f"  Skipping {story_id} (already generated)")
                continue

            try:
                article = self.generator.generate_article(story)
                articles[story_id] = {
                    **article,
                    "sources": story["sources"],
                    "video_urls": story["video_urls"],
                    "published_at": story["published_at"],
                }
                self.log(f"  Generated: {article['title'][:60]}...")
                with open(articles_path, "w", encoding="utf-8") as f:
                    json.dump(articles, f, ensure_ascii=False, indent=2)
            except Exception as exc:
                self.log(f"  Failed: {story.get('title', '')[:60]}... - {exc}")
                if "429" in str(exc):
                    self.log("  Rate limit hit, waiting 60 seconds...")
                    time.sleep(60)

        self.log(f"Total articles generated: {len(articles)}")
        return articles

    def stage6_create_final_output(self) -> list[dict]:
        self.log("Stage 6: Creating final output...")
        articles_path = self.data_dir / "articles.json"
        if not articles_path.exists():
            self.log("No articles.json found; skipping final output.")
            return []

        with open(articles_path, "r", encoding="utf-8") as f:
            articles = json.load(f)

        news_output = []
        for story_id, article in articles.items():
            news_output.append({
                "story_id": story_id,
                "title": article["title"],
                "content": article["content"],
                "summary": article.get("summary", ""),
                "people": article.get("people", []),
                "places": article.get("places", []),
                "organizations": article.get("organizations", []),
                "sources": article["sources"],
                "video_urls": article["video_urls"],
                "published_at": article["published_at"],
            })

        news_output.sort(key=lambda x: x.get("published_at", ""), reverse=True)
        with open(self.data_dir / "news.json", "w", encoding="utf-8") as f:
            json.dump(news_output, f, ensure_ascii=False, indent=2)

        self.log(f"Final output: {len(news_output)} stories")
        return news_output

    def export_latest_news_txt(self, min_length: int = 100) -> Path:
        self.log("Creating latest_news.txt")
        transcripts = _load_transcript_list(self.data_dir / "transcripts.json")
        output_file = self.data_dir / "latest_news.txt"

        with open(output_file, "w", encoding="utf-8") as out:
            for item in transcripts:
                transcript = item.get("transcript", "")
                if len(transcript) < min_length:
                    continue

                out.write("=" * 100 + "\n\n")
                out.write(f"TITLE:\n{item.get('title', '')}\n\n")
                out.write(f"CHANNEL:\n{item.get('channel', '')}\n\n")
                out.write(f"DATE:\n{item.get('published_at', '')}\n\n")
                out.write(f"URL:\n{item.get('url', '')}\n\n")
                out.write("CONTENT:\n")
                out.write(transcript)
                out.write("\n\n")

        self.log(f"Saved to {output_file}")
        return output_file

    def run(self, full: bool = False, limit: int | None = None) -> None:
        self.log("=" * 60)
        self.log("NARASARAOPET CONTENT COLLECTOR")
        self.log("=" * 60)

        self.stage1_search()
        self.stage2_collect_transcripts()
        self.export_latest_news_txt()

        if full:
            self.stage3_clean_transcripts()
            self.stage4_deduplicate()
            self.stage5_generate_articles(limit=limit)
            self.stage6_create_final_output()

        self.log("=" * 60)
        self.log("PIPELINE COMPLETE")
        self.log("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Telugu YouTube news pipeline")
    parser.add_argument("--days", type=int, default=config.SEARCH_PERIOD_DAYS, help="Days to look back")
    parser.add_argument("--limit", type=int, default=None, help="Limit articles to generate (full mode)")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run all stages: clean, deduplicate, generate articles, news.json",
    )
    args = parser.parse_args()

    pipeline = NewsPipeline(days_back=args.days)
    pipeline.run(full=args.full, limit=args.limit)
