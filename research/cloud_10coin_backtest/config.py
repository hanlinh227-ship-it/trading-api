from dataclasses import dataclass, field
from pathlib import Path

SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
    "TRXUSDT", "DOGEUSDT", "LINKUSDT", "ADAUSDT", "XLMUSDT",
)


@dataclass(frozen=True)
class CostModel:
    fee_bps_per_side: float = 5.0
    slippage_bps_per_side: float = 1.0


@dataclass(frozen=True)
class BacktestConfig:
    start: str = "2024-01-01"
    end: str | None = None
    development_fraction: float = 0.60
    validation_fraction: float = 0.20
    rr_primary: float = 2.0
    rr_secondary: float = 1.0
    min_completed_trades: int = 100
    target_wr: float = 0.80
    max_hold_bars_5m: int = 288
    max_candidate_profiles_per_family: int = 256
    top_k_validation: int = 12
    cache_dir: Path = Path(".cache/cloud_10coin_backtest")
    results_dir: Path = Path("results")
    costs: CostModel = field(default_factory=CostModel)


DEFAULT_CONFIG = BacktestConfig()
