# India-China Logistics Digest

A personal, free daily news app. Every morning it automatically gathers India logistics,
China logistics, India-China trade, and related "spillover" news (freight rates, Red Sea
disruptions, currency moves, etc.), has AI write a one-line "what this means" takeaway for
each story, and turns it into a swipeable card deck you read in a minute or two — with a
streak counter, points, and the occasional quiz card. Tap any card's source link to read the
full original article on the publisher's site.

**Cost: $0.** Runs on GitHub Actions (free), Google News RSS (free), Gemini's free API tier,
and GitHub Pages (free) — nothing here needs a card on file.

## How it works

1. Every morning, a GitHub Actions job runs `scripts/build_digest.py`, which:
   - Fetches today's news from Google News RSS (`scripts/fetch_news.py`)
   - Sends the headlines to Gemini for a one-line inference per story (`scripts/process_with_gemini.py`)
   - Saves the result to `docs/data/latest.json` and commits it back to this repo
2. GitHub Pages serves the `docs/` folder as a live website — the card-deck app in
   `docs/index.html` / `docs/app.js` reads that JSON and renders the deck.
3. Your phone/laptop just open the Pages URL — nothing runs on your own devices.

## Where your progress is stored

Your streak, points, and read/skipped cards are stored in your browser's `localStorage` —
per device, not synced. There's no account, login, or backend database.

## Changing things later

- **Change the daily time**: edit the `cron:` line in `.github/workflows/daily-digest.yml`
  (it's in UTC; the file has a comment showing the IST conversion).
- **Change what counts as news**: edit the `QUERIES` list in `scripts/fetch_news.py`.
- **Run it manually right now**: on GitHub, go to the "Actions" tab → "Daily Digest" →
  "Run workflow".
