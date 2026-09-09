# SignalHub V3.17 UX Polish Checkpoint

- Scope: Android UX/UI only. Signal engine and production backend are intentionally unchanged from V3.16.
- Navigation: 5 compact destinations — Home, Signals, Watchlist, Stats, Settings.
- Home: simplified system state, 2 SCALP + 2 SWING counters, empirical closed-trade evidence, and four reference-signal cards.
- Signals: clearer SCALP/SWING segmented control, separate LIVE and pending-entry counts, simplified cards, larger price hierarchy, Entry/SL/TP3 tiles, existing live/pending gauges retained.
- Detail: trade plan and market-analysis hierarchy separated; Entry/SL/TP/RR remain visible without dense text walls.
- Watchlist: simpler add flow and compact per-symbol SCALP/SWING analysis; read-only and does not consume the fixed 2+2 portfolio.
- Stats: only realized TP/SL history; sample-size caveat remains explicit.
- Accessibility/polish: >=44dp primary controls, content descriptions for key icons, larger body text, cleaner spacing, hidden scroll bar, consistent rounded surfaces and semantic colors.
- Signal behavior: no score/time/RR gate changes and no backend signal-selection changes in this checkpoint.
- Build signing: debug signing remains in use.
