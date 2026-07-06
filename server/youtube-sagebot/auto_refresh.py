import os
import time

while True:

    print("\nRefreshing videos...\n")

    os.system(
        "python search_youtube.py --days 2"
    )

    os.system(
        "python collect_news.py"
    )

    os.system(
        "python export_latest_news.py"
    )

    print(
        "\nSleeping for 4 hours...\n"
    )

    time.sleep(
        4 * 60 * 60
    )
