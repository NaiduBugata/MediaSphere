import requests
import pandas as pd
import time
from datetime import datetime, timedelta

TAG_ID = 374
PAGE_SIZE = 100
CHECK_INTERVAL = 4 * 60 * 60  # 4 hours

CSV_FILE = "narasaraopet_news.csv"


def fetch_last_24hr_news():

    cutoff_time = datetime.now().astimezone() - timedelta(hours=24)

    articles = []

    page = 1

    while True:

        url = f"https://telugu.getlokalapp.com/api/posts?tag_id={TAG_ID}&post_type=1,2&page_size={PAGE_SIZE}&page={page}"

        response = requests.get(url)

        if response.status_code != 200:
            print("API Error:", response.status_code)
            break

        data = response.json()

        posts = data.get("results", [])

        if not posts:
            break

        stop_fetching = False

        for post in posts:

            post_time = datetime.fromisoformat(post["created_on"])

            if post_time < cutoff_time:
                stop_fetching = True
                break

            articles.append({
                "id": post["id"],
                "date": post["created_on"],
                "title": post["title"],
                "content": post["content"]
            })

        if stop_fetching:
            break

        page += 1

    return articles


def save_articles(new_articles):

    try:
        existing = pd.read_csv(CSV_FILE)
        existing_ids = set(existing["id"])
    except:
        existing = pd.DataFrame()
        existing_ids = set()

    fresh_articles = [
        article for article in new_articles
        if article["id"] not in existing_ids
    ]

    if fresh_articles:

        df_new = pd.DataFrame(fresh_articles)

        final_df = pd.concat([existing, df_new], ignore_index=True)

        final_df.to_csv(CSV_FILE, index=False)

        print(f"New Articles Added: {len(fresh_articles)}")

    else:
        print("No New Articles Found")

    try:
        total_df = pd.read_csv(CSV_FILE)
        print("Articles Collected In Last 24 Hours:", len(total_df))
    except:
        pass


print("News Collector Started...")

while True:

    print("\n" + "=" * 60)
    print("Fetching News:", datetime.now())
    print("=" * 60)

    articles = fetch_last_24hr_news()

    save_articles(articles)

    print("\nSleeping for 4 hours...")
    time.sleep(CHECK_INTERVAL)