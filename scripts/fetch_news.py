"""Reads: nothing (hits Google News RSS live). Writes: returns a list of article dicts to the caller.

Fetches today's India logistics, China logistics, India-China trade, and
"spillover" news from Google News RSS search feeds (free, no API key),
then deduplicates near-identical headlines and caps the total.
"""
import hashlib
import re
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
    """Fetch every query, dedupe by normalized headline, cap the total. Returns a list of article dicts."""
    seen_headlines = set()
    articles = []

    for category, hl, gl, query in QUERIES:
        url = f"https://news.google.com/rss/search?q={quote(query)}&hl={hl}&gl={gl}&ceid={gl}:{hl.split('-')[0]}"
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
        except Exception as exc:
            print(f"  [skip] query failed ({category}): {exc}")
            continue

        taken = 0
        for entry in feed.entries:
            if taken >= MAX_PER_QUERY:
                break
            title = getattr(entry, "title", "").strip()
            if not title:
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
            })
            taken += 1

    articles = articles[:MAX_TOTAL]
    print(f"Fetched {len(articles)} deduplicated articles across {len(QUERIES)} queries.")
    return articles
