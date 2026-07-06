from youtube_transcript_api import YouTubeTranscriptApi

api = YouTubeTranscriptApi()

transcript = api.fetch("PzkPyld6Duc")

print(type(transcript))
print(transcript)