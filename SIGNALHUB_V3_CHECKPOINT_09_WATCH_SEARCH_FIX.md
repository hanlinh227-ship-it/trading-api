# SignalHub V3.18 Watch Search Fix Checkpoint

- Root cause fixed: Watchlist was fully re-rendered by live ticker/analysis refreshes while the EditText was focused. That destroyed the input view, dropped focus, and prevented the software keyboard/search flow from being usable.
- Watchlist search now owns persistent focus while typing; background live refreshes do not rebuild the Watchlist until input focus is released.
- Explicit keyboard invocation via InputMethodManager and Activity adjustResize added for OEM keyboards/HyperOS behavior.
- Search supports BTC, BTCUSDT, BTC/USDT and similar input normalization.
- Live suggestions are generated from the current Crypto ticker universe and can be tapped to add/analyze a coin.
- Keyboard IME Search/Done submits directly; the Tìm / thêm button also explicitly opens the keyboard when the field is empty.
- Watchlist remains read-only analysis and does not consume the fixed 2 SCALP + 2 SWING signal slots.
- Backend signal engine is unchanged from V3.16/V3.17 in this checkpoint.
- Build signing remains debug signing.
