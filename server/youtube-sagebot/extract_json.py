from youtube_transcript_api import YouTubeTranscriptApi
import json

api = YouTubeTranscriptApi()

transcript = api.fetch("PzkPyld6Duc")

data = {
    "video_id": transcript.video_id,
    "language": transcript.language,
    "language_code": transcript.language_code,
    "transcript": [
        {
            "text": item.text,
            "start": item.start,
            "duration": item.duration
        }
        for item in transcript
    ]
}

with open("output.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Saved to output.json")