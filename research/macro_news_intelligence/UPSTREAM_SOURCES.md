# External repo intake — Forex, XAUUSD, WTI and Brent news

Reviewed 2026-10-26. Project READMEs and selected license text were inspected; tradeFeed and market-intelligence MIT claims come from READMEs because standalone LICENSE files were not independently retrieved; exact upstream commit pins, dependency audit, model licensing, runtime freshness and deployment are NOT verified. These projects are **REFERENCE ONLY**, and NO third-party code, models or datasets were copied.

| Upstream | Source / role | Declared repo license | Decision |
|---|---|---|---|
| kmullin8/Macro-Financial_News_Classification | https://github.com/kmullin8/Macro-Financial_News_Classification — RSS ingest, dedup, macro topic classification; uses DistilBERT, MongoDB | MIT (repo; check model/data licenses separately) | ADOPT bounded design patterns only |
| jflogol/tradeFeed | https://github.com/jflogol/tradeFeed — financial news digest, sentiment, COT reports | MIT claimed in README; LICENSE file not verified | REFERENCE ONLY, do not add vector DB or scraper stack |
| ProsusAI/finBERT | https://github.com/ProsusAI/finBERT — financial-text sentiment; 2026-10-12 license notice | Apache-2.0 **code only**; model weights and training dataset excluded | DEFER weights and inference; separate rights and resource review |
| tradingeconomics/tradingeconomics-python | https://github.com/tradingeconomics/tradingeconomics-python — calendar/economic indicators | GPL-3.0 client; API authentication/subscription required | DEFER paid credentials/API and GPL client; use documentation as reference only |
| hasnain-akhtar-ha/market-intelligence | https://github.com/hasnain-akhtar-ha/market-intelligence — example cross-asset macro research | MIT claimed in README; LICENSE file not verified | REFERENCE ONLY |

## Why a small original implementation

- Required capability is traceable collection + data classification, not an ML training service.
- Standard-library original code in news_skill.py and pure offline unit tests avoid MongoDB, scraping third-party paywalls, huge model downloads, keys and hidden cost.
- The classifier does NOT use the above source code or model weights. Repository license claims apply only at project level; they do not grant article republishing or feed/API rights.
- Never persist full retrieved articles or external copyrighted payloads.
- Use a reviewed feed whitelist and bounded URL validation; no arbitrary target URL or local machine URL can be requested.
- No production behavior, skill router, scheduler or live execution changed in this PR.

## Known quality gaps

1. Keyword extraction is deterministic but imperfect. HIGH_POTENTIAL expresses topic salience, not official event impact; misses multilingual, implicit or unexpected macro headlines.
2. Shared headline does not necessarily prove independent source corroboration: multiple RSS mirrors can syndicate one article.
3. News is not an economic calendar. A scheduled high-impact release must have a separately verified event ID, scheduled instant, instrument/currency applicability, source and freshness.
4. No actual provider endpoint/source-liveness or current data coverage has been verified. Valid empty RSS result is NOT news clearance.
5. For any future production use, pin specific upstream commits only if importing code, verify every asset's license, measure feed precision/recall, add official economic-calendar adapter and enforce independent hard-news gate.
