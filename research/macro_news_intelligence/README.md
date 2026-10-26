# Macro news intelligence — FX / Gold / Oil (read-only candidate)

Small no-key Python 3.10+ research CLI for RSS/Atom and offline JSON. Filters headlines by topic and Forex/XAUUSD/WTI/Brent relevance, normalizes source timestamps, deduplicates titles and outputs auditable JSON.

## Offline reproducibility
\`\`\`sh
python -m unittest discover -s research/macro_news_intelligence -p 'test_*.py' -v
python research/macro_news_intelligence/news_skill.py --input-json research/macro_news_intelligence/example_articles.json --now 2026-10-26T00:00:00Z
\`\`\`

## Optional bounded online collection (only after approving sources)
\`\`\`sh
python research/macro_news_intelligence/news_skill.py \
  --feed-url https://www.federalreserve.gov/feeds/press_monetary.xml \
  --max-age-hours 48 \
  --output /tmp/macro-news.json
\`\`\`
Accepted RSS hosts: Fed, ECB, EIA, Google News; HTTPS only, redirects rejected, max 2 MB/feed, 100 items/feed, 12 feeds, 7s request timeout. \`--input-json\` is the default safe/offline mode. Online commands have **not** been smoke-tested against live feeds in this branch.

## Safety
\`hardNewsClearance=NEWS_UNVERIFIED\` in every output; topic scores are **not** verified event impact, probabilities, trade signals, or confirmed market direction. An empty RSS result is **not** \`NEWS_CLEAR\`. No cron, production feed, GitHub Actions, bot order path, secret, subscription, or V4 Stable registration is included.

See [SKILL.md](SKILL.md) and [UPSTREAM_REVIEW.md](UPSTREAM_REVIEW.md).
