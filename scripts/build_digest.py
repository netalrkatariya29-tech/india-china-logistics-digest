"""The one entry point. Reads: nothing. Writes: docs/data/latest.json,
docs/data/history/<date>.json, and (Sundays only) docs/data/weekly-summary.json.

Run order: fetch -> add inferences -> write today's files -> (Sunday) write weekly summary.
This is the only script GitHub Actions calls.
"""
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import fetch_news
import process_with_gemini

IST = ZoneInfo("Asia/Kolkata")
HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_DATA = os.path.join(HERE, "..", "docs", "data")
HISTORY_DIR = os.path.join(DOCS_DATA, "history")


def write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_week_history(today):
    """Loads the last 7 days of history files (including today) that exist, for the weekly summary."""
    from datetime import timedelta
    items = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        path = os.path.join(HISTORY_DIR, f"{day.date().isoformat()}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                items.extend(json.load(f).get("articles", []))
    return items


def main():
    print("== Step 1: Fetch news ==")
    articles = fetch_news.fetch_all()

    print("== Step 2: AI inferences ==")
    articles = process_with_gemini.add_inferences(articles)

    now = datetime.now(IST)
    date_str = now.date().isoformat()

    print("== Step 3: Write today's digest ==")
    daily_payload = {
        "date": date_str,
        "generated_at": now.isoformat(),
        "articles": articles,
    }
    write_json(os.path.join(DOCS_DATA, "latest.json"), daily_payload)
    write_json(os.path.join(HISTORY_DIR, f"{date_str}.json"), daily_payload)
    print(f"  Wrote {len(articles)} articles to latest.json and history/{date_str}.json")

    if now.weekday() == 6:  # Sunday
        print("== Step 4: Weekly big-picture summary (Sunday) ==")
        week_articles = load_week_history(now)
        summary = process_with_gemini.weekly_summary(week_articles)
        if summary:
            write_json(os.path.join(DOCS_DATA, "weekly-summary.json"), {
                "week_ending": date_str,
                "generated_at": now.isoformat(),
                "summary": summary,
            })
            print("  Wrote weekly-summary.json")
        else:
            print("  Skipped: no summary generated")
    else:
        print("== Step 4: skipped (not Sunday) ==")

    print("Done.")


if __name__ == "__main__":
    main()
