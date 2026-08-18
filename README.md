# Google News Article Aggregator

A Python-based news aggregation project that collects news from **Google News** for a fleet of **apps**,
each with its own set of feeds (topic, country, language), extracts complete article details, uses the
**Gemini API** to summarize articles, and saves the results as per-app, per-feed JSON files ready to be
consumed directly by client apps (e.g. an iOS news app).

The project runs automatically every hour using **GitHub Actions** and stores the generated news data
directly in the GitHub repository.

## Features

* Configure any number of **apps**, each with its own set of Google News feeds (top headlines or named topic,
  by country/language)
* Extract article title, image, source/publisher, author, published date, and full content
* Summarize and clean articles with the Google Gemini API
* Each feed's JSON file holds at most `max_results` articles; older articles roll off into an archive file
  instead of being lost
* Duplicate/reprocessing protection via a shared cache, so the same article seen from two different feeds
  isn't fetched or summarized twice
* Fully automated via GitHub Actions, hourly (or manual)

## Project Structure

```text
NewsAllApps/
├── .github/workflows/news.yml         # hourly + manual GitHub Action
├── config/
│   ├── apps.json                      # index of app config files
│   └── apps/
│       ├── config_usanews.json        # one config file per app
│       ├── config_canadanews.json
│       └── config_hailal.json
├── src/
│   ├── apps_config.py                 # loads apps.json + per-app configs
│   ├── google_news.py                 # Google News RSS search + URL resolution
│   ├── article_extractor.py           # full article fetch + extraction (trafilatura)
│   ├── gemini.py                      # Gemini summarization
│   ├── processor.py                   # pipeline orchestration + cap/archive + cache
│   └── utils.py                       # logging, retries, ids, JSON I/O
├── data/
│   ├── processed_cache.json           # id -> processed article, shared across all apps/feeds
│   └── <app_name>/
│       ├── <filename>.json            # live feed, capped at max_results, newest first
│       └── archive/<filename>.json    # articles rolled off the live feed
├── tests/
├── main.py
└── requirements.txt
```

## Configuration

`config/apps.json` lists which app config files to run:

```json
{
  "apps": [
    "config_usanews.json",
    "config_canadanews.json",
    "config_hailal.json"
  ]
}
```

Each file under `config/apps/` defines one app's feeds — no code changes needed to add an app or a feed:

```json
{
  "app_name": "usanews",
  "repository": "faroukdubai2/fetch_news",
  "news_sources": [
    {
      "function": "get_top_news",
      "language": "en",
      "country": "US",
      "max_results": 99,
      "filename": "usa_top_news.json"
    },
    {
      "function": "get_news_by_topic",
      "topic": "WORLD",
      "language": "en",
      "country": "US",
      "max_results": 99,
      "filename": "usa_world_news.json"
    }
  ]
}
```

* `function` — `get_top_news` (front-page headlines) or `get_news_by_topic` (a named Google News section:
  world, nation, business, technology, entertainment, sports, science, health)
* `max_results` — the cap for this feed's live JSON file
* `filename` — where this feed's output is written, under `data/<app_name>/`
* `repository` is currently informational only; the pipeline doesn't act on it

## How a run behaves

Each run is deliberately conservative so it fits comfortably within Gemini's rate limits, since the workflow
runs every hour:

1. For every feed, scan up to 50 recent Google News entries for the **first one not already saved** (live
   file or archive).
2. Process only that **one** new article (resolve → extract → summarize), save it to the top of the feed's
   live JSON file, then move on to the next feed. If nothing new is found, the feed is left untouched.
3. If a feed's live file grows past `max_results`, the oldest entries are moved into
   `data/<app_name>/archive/<filename>.json` — so nothing is lost, but each iOS-facing file stays capped and
   fast to load.

Because feeds refill roughly one article per hour, `max_results: 99` means the live file takes about four
days to fill after a cold start — bump `max_results` down for feeds you want to fill faster.

## JSON Output

```json
{
  "id": "a1b2c3d4e5f6...",
  "title": "Article title",
  "source": "Publisher",
  "author": "Author Name",
  "published_at": "2026-08-18T10:30:00+00:00",
  "image": "https://example.com/image.jpg",
  "url": "https://example.com/article",
  "google_news_url": "https://news.google.com/rss/articles/...",
  "content": "Full article content...",
  "summary": "Gemini generated summary...",
  "key_points": ["...", "..."],
  "language": "en",
  "country": "US",
  "topic": "WORLD",
  "app": "usanews",
  "collected_at": "2026-08-18T12:00:00+00:00"
}
```

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
copy .env.example .env        # then fill in GEMINI_API_KEY

python main.py
```

Run tests with:

```bash
python -m unittest discover tests
```

## Environment Variables

| Variable | Description |
|---|---|
| `GEMINI_API_KEY` | Required. Google Gemini API key, never committed to the repo. |
| `GEMINI_MODEL` | Optional. Defaults to `gemini-2.5-flash`. |

## GitHub Actions

`.github/workflows/news.yml` runs the pipeline every hour (`workflow_dispatch` also allows manual runs),
commits any changed files under `data/`, and pushes them back to the repository. Add `GEMINI_API_KEY` as a
repository secret before enabling the schedule.

## Error Handling

The pipeline is resilient by design: a failed search, a failed extraction, or a failed Gemini call is logged
and skipped, moving on to the next candidate article without stopping the run. When full extraction fails,
the Google News metadata for that article (title, source, link) is still saved.

## Future Improvements

RSS support for additional providers, `get_news_by_query`/`get_news_by_topic_url` functions for niche feeds,
automatic categorization, sentiment analysis, keyword extraction, image downloading, translation, database
storage, a REST API, and a searchable web dashboard.
