# Kaggriculture V5 — Public Meta Research

Updated: 2026-09-10

This document records public information used to design V5. V5 independently implements ideas; it does not copy private competitor code, and the submitted runtime never downloads replays or uses a network.

## Current engine

Kaggle Staff announced the final small balance change and explicitly asked competitors to update to `kaggle-environments >= 1.32.7`. The change makes eggs, tomatoes and carrots become much more valuable in some high-demand/no-production seasons rather than universally. PyPI 1.32.7 was released 2026-08-15. Therefore V3/V4 deep studies pinned to 1.32.4 are historical research only; V5 validation is pinned by version to 1.32.7 and records the exact simulator file hash in every report.

Sources:
- https://www.kaggle.com/competitions/kaggriculture/discussion/735311
- https://pypi.org/project/kaggle-environments/1.32.7/

## What strong public farms teach us

A public high-Elo replay study on an older meta slice reported a modal farm around 9 cows + 4 sheep + 1 wheat + 10 hands and three quadrants, with first land around day 6 and cows/sheep bought on day 0. This is a search prior, not a hard-coded target; the current engine and meta can differ.

Source:
- https://www.kaggle.com/code/cjlcjlcjl/kaggriculture-what-the-top-farms-do-a-live-meta

An MIT-licensed public project independently measured another livestock-led family around 8 cows + 6 sheep with feed wheat and fertilized strawberries. Its useful conceptual findings are: CARE can make livestock economically dominant; movement/action waste is often more important than nominal land capacity; metered selling avoids price collapse; shed overflow destroys harvested value; and copying acreage without copying the cash-flow engine can lose badly. We use these as hypotheses and re-test them on our own simulator/evaluation suite.

Source/license:
- https://github.com/lonespear/kaggriculture
- https://github.com/lonespear/kaggriculture/blob/master/LICENSE

A public market-analysis discussion emphasizes that expected demand is not enough because shops are randomized with replacement. Some products can have little/no seasonal shop demand, while 1.32.7 creates situational scarcity opportunities in carrot/tomato/egg. V5 therefore computes product scores from the current observation: live price ratio, current unlocked shop demand, horizon, seed cost, feed needs and expansion liquidity.

Source:
- https://www.kaggle.com/competitions/kaggriculture/discussion/734412

## Replay intelligence and continuous development

Kaggle Staff publicly stated that freely and publicly available material is fair use. Public discussions also provide/describe daily exported top-episode archives and replay-analysis workflows. V5 therefore contains an OFFLINE replay intelligence analyzer that accepts only public JSON/JSONL episode data and measures opening fingerprints, land/labor/herd timing, crop/animal shape, sell batches and money curves.

Sources:
- https://www.kaggle.com/competitions/kaggriculture/discussion/737788
- https://www.kaggle.com/competitions/kaggriculture/discussion/737764
- https://www.kaggle.com/competitions/kaggriculture/discussion/732114
- https://www.kaggle.com/competitions/kaggriculture/discussion/739273

A recent public measurement-pipeline discussion reported that strong public strategy lineages often improve monotonically enough that replay fingerprinting and fresh local round-robin testing are useful for detecting a new economic regime. We do not replay a competitor's fixed 720-action tape at runtime. Instead, replay data is used to propose parameter priors/opponent families for future local studies, while the V5 runtime remains observation-reactive.

## Public benchmark context

The competition Code page currently exposes public notebooks with scores around 2.5k–2.7k, including `Farming Score V3: Replay Revised`, `Adaptive Route Agent V2`, and `Shape the Shop Work the Pasture`. These public scores are context only, not directly comparable to our local money/margin metrics and not proof that any specific mechanic causes the score.

Source:
- https://www.kaggle.com/competitions/kaggriculture/code

## V5 design decisions derived from research

1. **Profit is the objective, not acreage by itself.** Full-farm capability remains a user-requested research constraint, but no candidate may be submitted merely because it unlocks four quadrants. It must also beat the incumbent on unseen 1.32.7 games.
2. **Livestock is a capital engine only if its action/logistics cost pays.** Search includes no-herd controls and multiple cow/sheep/goose mixes.
3. **CARE/FEED are high-priority obligations.** Losing an animal to missed feed is catastrophic; V5 carries wheat in batches and can buy feed insurance.
4. **Fertilizer is action-aware.** V5 buys cheap fertilizer only when crop acreage and labor make the fertilize chain reachable; otherwise it relies on herd production or leaves the feature off.
5. **Crops are chosen from current marginal economics.** Fast wheat/carrot can finance land, wheat secures feed, strawberry/tomato gain from fertilizer/demand, and melon is suppressed unless the live price state supports it.
6. **Market sales are metered.** Endgame liquidates aggressively; normal play sells smaller batches and reserves herd feed wheat.
7. **Every improvement is fail-closed.** Search, holdout, both seats, meta opponents, V1 direct duel, terminal inventory, full-farm utilization and raw-exec parity all matter before promotion.

## What V5 does NOT do

- It does not persist hidden learning between Kaggle matches.
- It does not call the network from the submitted agent.
- It does not use private team code or private episodes.
- It does not auto-submit to Kaggle.
- It does not assume the public modal farm is currently optimal.

The continuous loop is external and evidence-driven: public replay archive -> offline feature extraction -> proposed priors/meta opponents -> canonical 1.32.7 local search -> unseen promotion gate -> human/ChatGPT review -> optional explicit submission.
