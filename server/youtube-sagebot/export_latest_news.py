import json

with open(
    "data/transcripts.json",
    "r",
    encoding="utf-8"
) as f:
    transcripts = json.load(f)

with open(
    "data/latest_news.txt",
    "w",
    encoding="utf-8"
) as out:

    for item in transcripts:

        transcript = item.get(
            "transcript",
            ""
        )

        if len(transcript) < 100:
            continue

        out.write("=" * 100)
        out.write("\n\n")

        out.write(
            f"TITLE:\n{item.get('title','')}\n\n"
        )

        out.write(
            f"CHANNEL:\n{item.get('channel','')}\n\n"
        )

        out.write(
            f"DATE:\n{item.get('published_at','')}\n\n"
        )

        out.write(
            f"URL:\n{item.get('url','')}\n\n"
        )

        out.write("CONTENT:\n")
        out.write(transcript)

        out.write("\n\n")

print(
    "Created data/latest_news.txt"
)