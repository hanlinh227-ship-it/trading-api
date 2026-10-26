# Upstream reference review — 2026-10-26

Status: **REFERENCE_ONLY / NO THIRD-PARTY CODE IMPORTED / NO RUNTIME ACTIVATION**

| Repository | Relevant pattern | Adoption decision | Blockers / caveats |
| --- | --- | --- | --- |
| https://github.com/kmullin8/Macro-Financial_News_Classification | RSS fetch, topic taxonomy for macro/energy/metals/currencies, dedup | Reference only; independently authored stdlib prototype | Confirm exact commit and license before any source import. DistilBERT + MongoDB too heavyweight for zero-billing bounded baseline |
| https://github.com/jflogol/tradeFeed | RSS multi-source categories, CFTC COT as separate evidence, event/news views | Reference only | Multi-DB/LLM/queue stack unnecessary; COT is weekly positioning not hard-news clearance. Repo describes portions as ongoing |
| https://github.com/hasnain-akhtar-ha/market-intelligence | Forex/gold/WTI/Brent research interface; evidence source separation | Reference only | Beware demo/mock prices and unverified timing; do not use as live trade execution evidence |
| https://github.com/ProsusAI/finBERT | Finance-text sentiment pattern | Defer | 2026-10-12 README notice: Apache-2.0 covers code, **not** pretrained weights/training data; inspect separate licensing. Sentiment is not asset direction |
| https://github.com/tradingeconomics/tradingeconomics-python | Authenticated official macro calendar feed (future option) | Defer | API subscription/key required; GPL-3.0 client; do not enable metered APIs by default |

First-party RSS references:
- Federal Reserve: https://www.federalreserve.gov/feeds/feeds.htm
- ECB: https://www.ecb.europa.eu/home/html/rss.en.html
- EIA: https://www.eia.gov/tools/rssfeeds/

Validation checklist before enabling a feed: current actual URL and host, permitted automated access, content/time quality, licensing and redistribution terms, redirect policy, rate limits, downtime fallback, objective timestamp provenance. Official source article does **not** automatically verify the exact scheduled release calendar.

Provenance: public GitHub README/source-documentation pages reviewed 2026-10-26. Exact immutable upstream SHAs, maintenance audits and license scans **not completed**; therefore all are still references, not dependencies. Do not cite this note as code-audit evidence.

The new \`news_skill.py\` is original purpose-built stdlib code, not a fork or license-unknown third-party code. Never put a news dataset into Git.

## Official release-time sources (validated documentation, not live ingestion)

- U.S. Bureau of Labor Statistics official RSS directory: https://www.bls.gov/feed/ — supported BLS publisher for CPI, NFP and jobs/inflation releases.
- Official iCalendar subscription documented by BLS: https://www.bls.gov/schedule/news_release/bls.ics — added as an **optional exact URL** adapter, explicitly invoked only. No live fetch has been executed or validated here. An exact-URL network success is necessary to label sourceVerified; it remains insufficient to claim complete worldwide news clearance.
- U.S. EIA RSS feeds: https://www.eia.gov/tools/rssfeeds/ — oil-related news and reports.
- EIA Weekly Petroleum Status Report official schedule: https://www.eia.gov/petroleum/supply/weekly/schedule.php — Wednesday typically 10:30 Eastern with holidays and exceptions. **Do not hardcode recurring event time** or fabricate upcoming release dates without parsing and verifying current EIA exceptions. WTI and Brent contexts must not inherit BLS event coverage.

Research adapter permissions remain read-only; broker-side/exchange-side quote verification and executable hard-news gating are separate approved workstreams.
