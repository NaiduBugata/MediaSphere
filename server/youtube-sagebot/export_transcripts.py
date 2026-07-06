import json
import os
import re

INPUT_FILE = "data/transcripts.json"
OUTPUT_DIR = "data/raw_transcripts"

os.makedirs(OUTPUT_DIR, exist_ok=True)

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    transcripts = json.load(f)

for item in transcripts:
    video_id = item.get("video_id", "unknown")
    title = item.get("title", "")
    channel = item.get("channel", "")
    date = item.get("published_at", "")
    url = item.get("url", "")
    transcript = item.get("transcript", "")

    safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)[:80]

    filename = f"{video_id}_{safe_title}.txt"
    filepath = os.path.join(OUTPUT_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as out:
        out.write(f"TITLE:\n{title}\n\n")
        out.write(f"CHANNEL:\n{channel}\n\n")
        out.write(f"DATE:\n{date}\n\n")
        out.write(f"URL:\n{url}\n\n")
        out.write("TRANSCRIPT:\n\n")
        out.write(transcript)

print(f"Exported {len(transcripts)} transcript files to {OUTPUT_DIR}")