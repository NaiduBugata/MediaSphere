from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import hashlib


class StoryDeduplicator:

    def __init__(self, similarity_threshold=0.85):

        self.similarity_threshold = similarity_threshold

        print("Loading embedding model...")

        self.embedding_model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        self.embedding_cache = {}

    def get_embedding(self, text):

        text = text[:2000]

        cache_key = hashlib.md5(
            text.encode("utf-8")
        ).hexdigest()

        if cache_key not in self.embedding_cache:

            self.embedding_cache[cache_key] = (
                self.embedding_model.encode(
                    text,
                    convert_to_numpy=True
                )
            )

        return self.embedding_cache[cache_key]

    def calculate_similarity(self, story1, story2):

        text1 = (
            story1.get("title", "")
            + " "
            + story1.get("transcript", "")[:1500]
        )

        text2 = (
            story2.get("title", "")
            + " "
            + story2.get("transcript", "")[:1500]
        )

        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)

        similarity = cosine_similarity(
            [emb1],
            [emb2]
        )[0][0]

        return float(similarity)

    def cluster_stories(self, transcripts):

        clusters = []
        processed = set()

        total = len(transcripts)

        for i in range(total):

            if i in processed:
                continue

            current_cluster = [transcripts[i]]
            processed.add(i)

            for j in range(i + 1, total):

                if j in processed:
                    continue

                similarity = self.calculate_similarity(
                    transcripts[i],
                    transcripts[j]
                )

                if similarity >= self.similarity_threshold:

                    current_cluster.append(
                        transcripts[j]
                    )

                    processed.add(j)

            clusters.append(current_cluster)

        return clusters

    def create_unique_story(self, cluster):

        best_source = max(
            cluster,
            key=lambda x: len(
                x.get("transcript", "")
            )
        )

        title = best_source.get(
            "title",
            ""
        )

        combined_text = "\n\n".join(
            [
                item.get(
                    "transcript",
                    ""
                )
                for item in cluster[:3]
            ]
        )[:6000]

        story_id = hashlib.md5(
            (
                title +
                combined_text[:500]
            ).encode("utf-8")
        ).hexdigest()[:12]

        urls = []

        for item in cluster:

            url = item.get(
                "url",
                ""
            )

            if url and url not in urls:
                urls.append(url)

        channels = []

        for item in cluster:

            ch = item.get(
                "channel",
                ""
            )

            if ch and ch not in channels:
                channels.append(ch)

        dates = [
            x.get(
                "published_at",
                ""
            )
            for x in cluster
            if x.get("published_at")
        ]

        latest_date = max(dates) if dates else ""

        return {
            "story_id": story_id,
            "title": title,
            "clean_text": combined_text,
            "sources": channels,
            "video_urls": urls,
            "published_at": latest_date,
            "source_count": len(cluster)
        }

    def deduplicate(self, transcripts_list):

        if not transcripts_list:
            return []

        print(
            f"Deduplicating {len(transcripts_list)} transcripts..."
        )

        clusters = self.cluster_stories(
            transcripts_list
        )

        print(
            f"Unique stories found: {len(clusters)}"
        )

        unique_stories = []

        for cluster in clusters:

            unique_story = self.create_unique_story(
                cluster
            )

            unique_stories.append(
                unique_story
            )

        unique_stories.sort(
            key=lambda x: x["source_count"],
            reverse=True
        )

        return unique_stories
