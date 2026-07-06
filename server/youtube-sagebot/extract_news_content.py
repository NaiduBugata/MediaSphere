import json
from groq import Groq
import config
from deduplicate_stories import StoryDeduplicator

# -----------------------------
# Initialize
# -----------------------------

client = Groq(api_key=config.GROQ_API_KEY)

print("Loading transcripts...")

with open("data/transcripts.json", "r", encoding="utf-8") as f:
    transcripts = json.load(f)

print(f"Original transcripts: {len(transcripts)}")

# -----------------------------
# Deduplicate first
# -----------------------------

deduplicator = StoryDeduplicator(
    similarity_threshold=0.75
)

stories = deduplicator.deduplicate(transcripts)
stories = stories[:20]
print(f"Processing only {len(stories)} stories")
print(f"Unique stories found: {len(stories)}")

# -----------------------------
# Output file
# -----------------------------

with open(
    "data/extracted_news.txt",
    "w",
    encoding="utf-8"
) as out:

    for idx, story in enumerate(stories, start=1):

        text = (
            story.get("clean_text")
            or story.get("transcript")
            or ""
        )

        print(
            f"Story {idx}: {len(text)} chars"
        )

        if len(text) < 300:
            continue
        if len(text) > 1500:
            text = text[:1500]

        urls = "\n".join(
            story.get("video_urls", [])
        )

        prompt = f"""
ఈ ట్రాన్స్క్రిప్ట్‌ల సమూహం ఒకే వార్తకు సంబంధించినవి.

టీవీ యాంకర్ మాటలు, ప్రమోషన్లు,
థ్యాంక్యూ, వెల్కమ్ వంటి అవసరం లేని
భాగాలను తొలగించండి.

ఈ వార్తలోని అసలు విషయాన్ని మాత్రమే
సంక్షిప్తంగా రాయండి.

FORMAT:

TITLE:
...

CONTENT:
...

KEY FACTS:
- ...
- ...
- ...

TRANSCRIPT:
{text}
"""

        try:

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=250
            )

            result = (
                response
                .choices[0]
                .message
                .content
            )

            out.write("\n")
            out.write("=" * 100)
            out.write("\n")

            out.write(
                f"STORY #{idx}\n\n"
            )

            out.write(
                f"SOURCE COUNT: "
                f"{story['source_count']}\n\n"
            )

            out.write(
                "SOURCE URLS:\n"
            )

            out.write(urls)

            out.write("\n\n")

            out.write(result)

            out.write("\n\n")

            print(
                f"Processed story "
                f"{idx}/{len(stories)}"
            )

        except Exception as e:

            print(
                f"Failed story {idx}: {e}"
            )

print(
    "\nFinished. Output saved to:"
)

print(
    "data/extracted_news.txt"
)
