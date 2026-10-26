# Macro News Intelligence — Forex / Gold / WTI / Brent

**Status: research-only candidate on Draft PR; not running production.** Python 3.10+ standard library, no keys or required paid services.

Collects bounded RSS/Atom headlines or offline JSON, deduplicates, labels rate decisions/CPI/payroll/OPEC/EIA/geopolitics, tags currencies, markets and UTC freshness. Optional BLS official .ics release calendar supplies scheduled event times, which are different from a story's publication timestamp.

## Local offline tests and replay

```bash
python -m unittest discover -s research/macro_news_intelligence -p 'test_*.py' -v
python research/macro_news_intelligence/news_skill.py --input-json research/macro_news_intelligence/example_articles.json --now 2026-10-26T04:00:00Z
```

Replay a downloaded calendar file (always labelled **unverified offline input**):

```bash
python research/macro_news_intelligence/news_skill.py --calendar-ics /path/to/calendar.ics --now 2026-11-06T13:00:00Z --pre-event-minutes 60 --post-event-minutes 30
```

## Explicit online collection (never enabled automatically)

```bash
python research/macro_news_intelligence/news_skill.py --feed-url https://www.federalreserve.gov/feeds/press_monetary.xml --official-bls-calendar --max-age-hours 48 --output macro-news.json
python research/macro_news_intelligence/news_skill.py --feed-url https://www.eia.gov/rss/todayinenergy.xml --feed-url https://www.eia.gov/rss/press_rss.xml
```

Official links are source examples, not liveness guarantees. Always review permitted automated access. HTTPS allowlist Fed/ECB/EIA/BLS/Google News only; no redirects or nonstandard port; up to 12 feeds, 7-second timeout each; 2 MB RSS or 1 MB ICS caps.

## Output contracts

- articles[] preserves source URLs, UTC publication time, freshness, topic, market and currency tags.
- summary contains by-topic/by-market/by-freshness counts and up to ten linked headlines.
- calendar (optional) contains BLS release times; sourceVerified true ONLY for successfully retrieved exact official BLS ICS URL, never for user/offline ICS. activeEventCount reports a configurable alert window but is advisory only.
- hardNewsClearance = NEWS_UNVERIFIED; economicCalendarVerified = false; executionAuthorized = false always. Missing articles or events do not prove market safety.

## Integration boundaries

Supports V4 canonical market_analysis; not a second router, execution authority or live production hard-news gate. Does not alter the active Forex strategy classification, Bybit/MT5/Exness orders, risk limits, TRADING_STATE, deployment workflows, skill catalog/index or release pointer. No scheduler or paid CI is added.

Reference: [SKILL.md](SKILL.md), [UPSTREAM_SOURCES.md](UPSTREAM_SOURCES.md), [UPSTREAM_REVIEW.md](UPSTREAM_REVIEW.md).
