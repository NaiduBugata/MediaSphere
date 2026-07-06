import json

INPUT_FILE = "data/transcripts.json"
OUTPUT_FILE = "data/all_transcripts.txt"

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    transcripts = json.load(f)

with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
    for i, item in enumerate(transcripts, 1):

        out.write("\n")
        out.write("=" * 100 + "\n")
        out.write(f"ARTICLE {i}\n")
        out.write("=" * 100 + "\n\n")
        out.write(f"TITLE: {item.get('title','')}\n")
        out.write(f"CHANNEL: {item.get('channel','')}\n")
        out.write(f"DATE: {item.get('published_at','')}\n")
        out.write(f"URL: {item.get('url','')}\n\n")
        out.write("TRANSCRIPT:\n")
        out.write(item.get("transcript", ""))
        out.write("\n\n")

print(f"Combined {len(transcripts)} transcripts into {OUTPUT_FILE}")