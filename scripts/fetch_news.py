"""Reads: nothing (hits Google News RSS live). Writes: returns a list of article dicts to the caller.

Fetches today's India logistics, China logistics, India-China trade, and
"spillover" news from Google News RSS search feeds (free, no API key),
then deduplicates near-identical headlines and caps the total.
"""
import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Each query belongs to a category tag shown on the card, and an edition
# (which Google News regional/language edition to search in).
QUERIES = [
    # category, edition (hl, gl, ceid), query string
    ("India Logistics", "en-IN", "IN", "(India) (logistics OR freight OR trucking OR warehousing OR ports OR shipping) when:1d"),
    ("India Logistics", "en-IN", "IN", '(India) ("logistics policy" OR "National Logistics Policy" OR "PM Gati Shakti") when:1d'),
    ("China Logistics", "en-US", "US", "(China) (logistics OR freight OR shipping OR ports OR trucking) when:1d"),
    ("China Logistics", "en-US", "US", '(China) ("COSCO" OR "China logistics policy" OR customs) when:1d'),
    ("India-China Trade", "en-IN", "IN", '("India China" OR "India-China") (trade OR tariff OR customs OR import OR export) when:1d'),
    ("India-China Trade", "en-IN", "IN", '(India) (China) ("rare earth" OR electronics OR solar OR API) (import OR export) when:1d'),
    ("Spillover", "en-US", "US", '("Red Sea" OR "Suez Canal") (shipping OR freight OR disruption) when:1d'),
    ("Spillover", "en-US", "US", '("Baltic Dry Index" OR "container freight rate" OR "Shanghai Containerized Freight Index") when:1d'),
    ("Spillover", "en-US", "US", "(crude oil price) (Brent OR WTI) when:1d"),
    ("Spillover", "en-US", "US", "(INR OR rupee OR yuan OR CNY) (currency) when:1d"),
    ("Spillover", "en-US", "US", '("export control" OR "trade tension" OR tariff) (US China) when:1d'),
]

MAX_PER_QUERY = 6
MAX_TOTAL = 25

# Google News' "when:1d" search filter is unreliable — it sometimes surfaces re-indexed
# older articles anyway. This is the real, hard cutoff enforced in code.
MAX_AGE_DAYS = 2


def _entry_datetime(entry):
    """Returns the entry's published time as a UTC datetime, or None if it can't be parsed."""
    parsed = getattr(entry, "published_parsed", None)
    if not parsed:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def _clean_snippet(html_snippet):
    text = BeautifulSoup(html_snippet or "", "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_headline(title):
    text = title.lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    words = text.split()[:8]
    return " ".join(words)


def _article_id(title, source, published):
    raw = f"{title}|{source}|{published}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def fetch_all():
    """Fetch every query, drop anything older than MAX_AGE_DAYS, dedupe by normalized
    headline, cap the total. Returns a list of article dicts, newest first."""
    seen_headlines = set()
    articles = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
    skipped_old = 0

    for category, hl, gl, query in QUERIES:
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}"
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as exc:
            print(f"  [skip] query failed ({category}): {exc}")
            continue

        # Sort newest-first so MAX_PER_QUERY keeps the most recent items, not feed order.
        entries = sorted(feed.entries, key=lambda e: _entry_datetime(e) or cutoff, reverse=True)

        taken = 0
        for entry in entries:
            if taken >= MAX_PER_QUERY:
                break
            title = getattr(entry, "title", "").strip()
            if not title:
                continue

            entry_dt = _entry_datetime(entry)
            if entry_dt is not None and entry_dt < cutoff:
                skipped_old += 1
                continue

            key = _normalize_headline(title)
            if key in seen_headlines:
                continue
            seen_headlines.add(key)

            source = ""
            if hasattr(entry, "source") and getattr(entry.source, "title", None):
                source = entry.source.title
            published = getattr(entry, "published", "")
            snippet = _clean_snippet(getattr(entry, "summary", ""))
            link = getattr(entry, "link", "")

            articles.append({
                "id": _article_id(title, source, published),
                "category": category,
                "title": title,
                "source": source,
                "published": published,
                "snippet": snippet,
                "link": link,
                "_sort_dt": entry_dt or cutoff,
            })
            taken += 1

    articles.sort(key=lambda a: a["_sort_dt"], reverse=True)
    for a in articles:
        del a["_sort_dt"]
    articles = articles[:MAX_TOTAL]
    print(f"Fetched {len(articles)} deduplicated articles across {len(QUERIES)} queries "
          f"({skipped_old} dropped for being older than {MAX_AGE_DAYS} days).")
    return articles
