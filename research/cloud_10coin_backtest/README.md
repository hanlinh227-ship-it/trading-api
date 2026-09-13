# Cloud 10-Coin Backtest Engine

Research-only Binance USD-M perpetual backtest job for:

`BTCUSDT ETHUSDT BNBUSDT XRPUSDT SOLUSDT TRXUSDT DOGEUSDT LINKUSDT ADAUSDT XLMUSDT`

Hard research target per coin: at least 100 completed trades and observed win rate >=80% at RR 1:2 under a locked profile that survives chronological validation/holdout. RR 1:1 is diagnostic only.

## Safety boundary

This package is read-only research. It uses only public Binance market-data endpoints/archives. It contains no account credentials, private endpoints, order placement, leverage mutation, wallet actions, transfers, or withdrawals. It does not replace the repository's BTCUSDT Bybit production authority.

## Cloud execution

Railway service: `crypto-backtest-job`

- isolated service ID and lifecycle;
- no public domain;
- no shared volume/database with the research gateway;
- no exchange secrets;
- restart policy `NEVER`;
- root directory `/research/cloud_10coin_backtest`.

Run tests:

```bash
PYTHONPATH=. pytest tests -q
```

Smoke:

```bash
PYTHONPATH=. python run.py --symbols BTCUSDT,SOLUSDT --start 2026-08-01 --end 2026-08-07 --smoke
```

Full research run:

```bash
PYTHONPATH=. python run.py --start 2024-01-01 --end 2026-09-12
```

Outputs are written to `results/`: run manifest, data audit, locked profiles, coin summary, per-symbol evaluation trades, report, and final summary.
