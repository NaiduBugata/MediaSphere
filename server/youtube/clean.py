"""Filter non-news YouTube transcripts."""

import re


class TranscriptCleaner:
    def __init__(self):
        self.news_channels = [
            "tv9", "ntv", "abn", "sakshi", "etv", "prime9",
            "tv5", "rtv", "inews", "big tv", "cvr", "sumantv",
            "10tv", "hmtv", "t news", "v6",
        ]
        self.non_news_keywords = [
            "shorts", "drone", "aerial", "plots", "sale",
            "shopping", "movie", "trailer", "song", "marriage",
            "wedding", "comedy", "dance", "cooking", "recipe",
            "makeup", "fashion", "gaming", "unboxing", "review",
            "reaction", "prank", "challenge",
        ]
        self.news_indicators = [
            "న్యూస్", "వార్తలు", "నివేదిక", "ఘటన", "సంఘటన",
            "ప్రమాదం", "మృతి", "హత్య", "అరెస్ట్", "పోలీస్",
            "కోర్టు", "ప్రభుత్వం", "మంత్రి", "ఎమ్మెల్యే",
            "ఎన్నికలు", "సభ", "సమావేశం", "ధర్నా", "ప్రదర్శన",
        ]
        self.tv_filler_patterns = [
            r"మా\s*ప్రతినిధి",
            r"మరిన్ని\s*వివరాలు",
            r"subscribe",
            r"like\s+and\s+share",
        ]

    def _text(self, transcript) -> str:
        if isinstance(transcript, str):
            return transcript
        return str(transcript or "")

    def is_news_content(self, title: str, channel: str, transcript) -> bool:
        title_lower = (title or "").lower()
        channel_lower = (channel or "").lower()
        text = self._text(transcript)
        is_news_channel = any(ch in channel_lower for ch in self.news_channels)
        has_non_news = any(kw in title_lower for kw in self.non_news_keywords)
        has_indicators = any(ind in text for ind in self.news_indicators)
        if is_news_channel and not has_non_news:
            return True
        return has_indicators and not has_non_news

    def _normalize(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
        for pattern in self.tv_filler_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def clean(self, transcript, title: str, channel: str) -> dict:
        raw = self._text(transcript)
        is_news = self.is_news_content(title, channel, raw)
        clean_text = self._normalize(raw) if is_news else ""
        return {"is_news": is_news, "clean_text": clean_text}
