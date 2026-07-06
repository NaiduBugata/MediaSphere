"""Stage 3: filter non-news transcripts and normalize text."""

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
            r"చూడండి",
            r"వినండి",
            r"తెలుసుకుందాం",
            r"బ్రేకింగ్\s*న్యూస్",
            r"subscribe",
            r"like\s+and\s+share",
        ]

    def _transcript_text(self, transcript) -> str:
        if isinstance(transcript, str):
            return transcript
        if isinstance(transcript, list):
            parts = []
            for item in transcript:
                if isinstance(item, dict):
                    parts.append(item.get("text", ""))
                else:
                    parts.append(getattr(item, "text", str(item)))
            return " ".join(parts)
        return str(transcript or "")

    def is_news_content(self, title: str, channel: str, transcript) -> bool:
        title_lower = (title or "").lower()
        channel_lower = (channel or "").lower()
        transcript_text = self._transcript_text(transcript)

        is_news_channel = any(news_ch in channel_lower for news_ch in self.news_channels)
        has_non_news = any(keyword in title_lower for keyword in self.non_news_keywords)
        has_news_indicators = any(indicator in transcript_text for indicator in self.news_indicators)

        if is_news_channel and not has_non_news:
            return True
        if has_news_indicators and not has_non_news:
            return True
        return False

    def _normalize_text(self, text: str) -> str:
        cleaned = text.replace("\n", " ").strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        for pattern in self.tv_filler_patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _guess_category(self, title: str, text: str) -> str:
        combined = f"{title} {text}".lower()
        if any(w in combined for w in ("police", "arrest", "crime", "పోలీస్", "అరెస్ట్")):
            return "crime"
        if any(w in combined for w in ("rain", "flood", "weather", "వర్ష", "వరద")):
            return "weather"
        if any(w in combined for w in ("minister", "election", "govt", "మంత్రి", "ఎన్నిక")):
            return "politics"
        return "general"

    def clean(self, transcript, title: str, channel: str) -> dict:
        """Return news filter result and normalized transcript text."""
        raw = self._transcript_text(transcript)
        is_news = self.is_news_content(title, channel, raw)
        clean_text = self._normalize_text(raw) if is_news else ""
        return {
            "is_news": is_news,
            "clean_text": clean_text,
            "category": self._guess_category(title, clean_text) if is_news else "filtered",
        }
