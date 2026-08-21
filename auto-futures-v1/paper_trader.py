import json
import statistics
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://fapi.binance.com"

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE_DIR = ROOT / "state"
LOG_DIR = ROOT / "logs"

STATE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
]

TIMEFRAMES = ["5m", "15m", "1h"]


# ============================================================
# HTTP
# ============================================================

def get_json(path):
    req = urllib.request.Request(
        BASE + path,
        headers={
            "User-Agent": "AUTO-FUTURES-V3-PAPER/1.0"
        },
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode())


def get_klines(symbol, interval, limit=250):
    return get_json(
        f"/fapi/v1/klines?"
        f"symbol={symbol}&interval={interval}&limit={limit}"
    )


def get_funding(symbol):
    data = get_json(
        f"/fapi/v1/premiumIndex?symbol={symbol}"
    )

    return float(data.get("lastFundingRate", 0.0))


def get_open_interest(symbol):
    data = get_json(
        f"/fapi/v1/openInterest?symbol={symbol}"
    )

    return float(data.get("openInterest", 0.0))


# ============================================================
# INDICATORS
# ============================================================

def ema(values, length):
    if not values:
        return 0.0

    alpha = 2 / (length + 1)

    value = values[0]

    for current in values[1:]:
        value = (
            alpha * current
            + (1 - alpha) * value
        )

    return value


def rsi(values, length=14):
    if len(values) < length + 1:
        return 50.0

    gains = []
    losses = []

    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]

        if delta > 0:
            gains.append(delta)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(delta))

    gains = gains[-length:]
    losses = losses[-length:]

    avg_gain = sum(gains) / length
    avg_loss = sum(losses) / length

    if avg_loss == 0:
        return 100.0

    relative_strength = avg_gain / avg_loss

    return 100 - (
        100 / (1 + relative_strength)
    )


def atr(highs, lows, closes, length=14):
    ranges = []

    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )

        ranges.append(tr)

    if not ranges:
        return 0.0

    recent = ranges[-length:]

    return sum(recent) / len(recent)


def pct_change(current, previous):
    if previous == 0:
        return 0.0

    return (
        (current - previous)
        / previous
        * 100
    )


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(symbol, interval):
    rows = get_klines(
        symbol,
        interval,
        250,
    )

    # Bỏ cây nến đang chạy.
    rows = rows[:-1]

    closes = [
        float(row[4])
        for row in rows
    ]

    highs = [
        float(row[2])
        for row in rows
    ]

    lows = [
        float(row[3])
        for row in rows
    ]

    volumes = [
        float(row[5])
        for row in rows
    ]

    price = closes[-1]

    ema20 = ema(
        closes[-100:],
        20,
    )

    ema50 = ema(
        closes[-150:],
        50,
    )

    ema200 = ema(
        closes,
        200,
    )

    rsi14 = rsi(
        closes[-100:],
        14,
    )

    atr14 = atr(
        highs[-100:],
        lows[-100:],
        closes[-100:],
        14,
    )

    recent_high = max(
        highs[-20:]
    )

    recent_low = min(
        lows[-20:]
    )

    avg_volume = statistics.mean(
        volumes[-21:-1]
    )

    volume_ratio = (
        volumes[-1] / avg_volume
        if avg_volume > 0
        else 0.0
    )

    momentum_3 = pct_change(
        closes[-1],
        closes[-4],
    )

    momentum_10 = pct_change(
        closes[-1],
        closes[-11],
    )

    distance_ema20_pct = pct_change(
        price,
        ema20,
    )

    distance_ema50_pct = pct_change(
        price,
        ema50,
    )

    atr_pct = (
        atr14 / price * 100
        if price
        else 0.0
    )

    trend = "NEUTRAL"

    if (
        price > ema20
        > ema50
        > ema200
    ):
        trend = "STRONG_BULL"

    elif (
        price > ema20
        > ema50
    ):
        trend = "BULL"

    elif (
        price < ema20
        < ema50
        < ema200
    ):
        trend = "STRONG_BEAR"

    elif (
        price < ema20
        < ema50
    ):
        trend = "BEAR"

    return {
        "interval": interval,

        "price": price,

        "ema20": ema20,
        "ema50": ema50,
        "ema200": ema200,

        "rsi14": rsi14,
        "atr14": atr14,
        "atr_pct": atr_pct,

        "recent_high": recent_high,
        "recent_low": recent_low,

        "volume_ratio": volume_ratio,

        "momentum_3": momentum_3,
        "momentum_10": momentum_10,

        "distance_ema20_pct":
            distance_ema20_pct,

        "distance_ema50_pct":
            distance_ema50_pct,

        "trend": trend,
    }


# ============================================================
# SETUP ENGINE
# ============================================================

def build_setup(symbol):

    timeframes = {
        interval:
            analyze_timeframe(
                symbol,
                interval,
            )

        for interval
        in TIMEFRAMES
    }

    funding = get_funding(symbol)
    open_interest = get_open_interest(symbol)

    tf5 = timeframes["5m"]
    tf15 = timeframes["15m"]
    tf1h = timeframes["1h"]

    score = 0

    reasons = []
    warnings = []
    blockers = []

    # --------------------------------------------------------
    # 1H STRUCTURE
    # --------------------------------------------------------

    if tf1h["trend"] == "STRONG_BULL":

        score += 3

        reasons.append(
            "1H strong bullish trend"
        )

    elif tf1h["trend"] == "BULL":

        score += 2

        reasons.append(
            "1H bullish trend"
        )

    elif tf1h["trend"] == "STRONG_BEAR":

        score -= 3

        reasons.append(
            "1H strong bearish trend"
        )

    elif tf1h["trend"] == "BEAR":

        score -= 2

        reasons.append(
            "1H bearish trend"
        )

    # --------------------------------------------------------
    # 15M CONFIRMATION
    # --------------------------------------------------------

    if tf15["trend"] in (
        "STRONG_BULL",
        "BULL",
    ):

        score += 2

        reasons.append(
            "15M bullish confirmation"
        )

    elif tf15["trend"] in (
        "STRONG_BEAR",
        "BEAR",
    ):

        score -= 2

        reasons.append(
            "15M bearish confirmation"
        )

    # --------------------------------------------------------
    # 5M ENTRY BIAS
    # --------------------------------------------------------

    if tf5["trend"] in (
        "STRONG_BULL",
        "BULL",
    ):

        score += 1

    elif tf5["trend"] in (
        "STRONG_BEAR",
        "BEAR",
    ):

        score -= 1

    # --------------------------------------------------------
    # MOMENTUM
    # --------------------------------------------------------

    if tf15["momentum_3"] >= 0.25:

        score += 1

        reasons.append(
            "15M positive momentum"
        )

    elif tf15["momentum_3"] <= -0.25:

        score -= 1

        reasons.append(
            "15M negative momentum"
        )

    # --------------------------------------------------------
    # VOLUME
    # --------------------------------------------------------

    if tf5["volume_ratio"] >= 1.30:

        if score > 0:

            score += 1

            reasons.append(
                "5M volume confirms bullish move"
            )

        elif score < 0:

            score -= 1

            reasons.append(
                "5M volume confirms bearish move"
            )

    # --------------------------------------------------------
    # FUNDING CROWDING
    # --------------------------------------------------------

    if funding >= 0.001:

        score -= 1

        warnings.append(
            "funding crowded on long side"
        )

    elif funding <= -0.001:

        score += 1

        warnings.append(
            "funding crowded on short side"
        )

    # --------------------------------------------------------
    # OVERBOUGHT / OVERSOLD
    # --------------------------------------------------------

    if (
        tf15["rsi14"] >= 70
        and score > 0
    ):

        score -= 2

        warnings.append(
            "15M RSI overbought"
        )

    if (
        tf15["rsi14"] <= 30
        and score < 0
    ):

        score += 2

        warnings.append(
            "15M RSI oversold"
        )

    # --------------------------------------------------------
    # DIRECTION / MOMENTUM CONFLICT
    # --------------------------------------------------------

    if (
        score > 0
        and tf15["momentum_3"] < 0
    ):

        score -= 2

        warnings.append(
            "bullish setup conflicts with falling 15M momentum"
        )

    if (
        score < 0
        and tf15["momentum_3"] > 0
    ):

        score += 2

        warnings.append(
            "bearish setup conflicts with rising 15M momentum"
        )

    # --------------------------------------------------------
    # CHASE / OVEREXTENSION FILTER
    # --------------------------------------------------------

    max_extension = max(
        0.80,
        tf15["atr_pct"] * 1.5,
    )

    if (
        tf15["distance_ema20_pct"]
        > max_extension
        and score > 0
    ):

        score -= 2

        warnings.append(
            "price extended above 15M EMA20"
        )

    if (
        tf15["distance_ema20_pct"]
        < -max_extension
        and score < 0
    ):

        score += 2

        warnings.append(
            "price extended below 15M EMA20"
        )

    # --------------------------------------------------------
    # HARD CHASE BLOCKER
    # --------------------------------------------------------

    hard_extension = max(
        1.50,
        tf15["atr_pct"] * 2.5,
    )

    if (
        tf15["distance_ema20_pct"]
        > hard_extension
    ):

        blockers.append(
            "LONG chase risk: price too far above 15M EMA20"
        )

    if (
        tf15["distance_ema20_pct"]
        < -hard_extension
    ):

        blockers.append(
            "SHORT chase risk: price too far below 15M EMA20"
        )

    # --------------------------------------------------------
    # EXTREME RSI + MOMENTUM AGAINST ENTRY
    # --------------------------------------------------------

    if (
        tf15["rsi14"] >= 72
        and tf15["momentum_3"] <= 0
    ):

        blockers.append(
            "LONG blocked: 15M overbought and momentum no longer rising"
        )

    if (
        tf15["rsi14"] <= 28
        and tf15["momentum_3"] >= 0
    ):

        blockers.append(
            "SHORT blocked: 15M oversold and momentum no longer falling"
        )

    # --------------------------------------------------------
    # CANDIDATE DIRECTION
    # --------------------------------------------------------

    direction = "WAIT"

    if score >= 5:
        direction = "LONG"

    elif score <= -5:
        direction = "SHORT"

    # Blocker phải đúng hướng setup.
    applicable_blockers = []

    for blocker in blockers:

        if (
            direction == "LONG"
            and "LONG" in blocker
        ):
            applicable_blockers.append(
                blocker
            )

        elif (
            direction == "SHORT"
            and "SHORT" in blocker
        ):
            applicable_blockers.append(
                blocker
            )

    if applicable_blockers:
        direction = "WAIT"

    # --------------------------------------------------------
    # ENTRY / SL / TARGETS
    # --------------------------------------------------------

    price = tf5["price"]
    atr_value = tf15["atr14"]

    entry = None
    stop = None

    tp1 = None
    tp2 = None
    tp3 = None

    rr_tp1 = None
    rr_tp2 = None
    rr_tp3 = None

    if direction == "LONG":

        entry = price

        atr_stop = (
            price
            - atr_value * 1.5
        )

        structural_stop = (
            tf15["recent_low"]
        )

        stop = max(
            atr_stop,
            structural_stop,
        )

        if stop >= entry:

            stop = atr_stop

        risk = entry - stop

        if risk <= 0:

            direction = "WAIT"

            applicable_blockers.append(
                "invalid LONG stop geometry"
            )

        else:

            tp1 = entry + risk * 1.5
            tp2 = entry + risk * 2.5
            tp3 = entry + risk * 4.0

            rr_tp1 = 1.5
            rr_tp2 = 2.5
            rr_tp3 = 4.0

    elif direction == "SHORT":

        entry = price

        atr_stop = (
            price
            + atr_value * 1.5
        )

        structural_stop = (
            tf15["recent_high"]
        )

        stop = min(
            atr_stop,
            structural_stop,
        )

        if stop <= entry:

            stop = atr_stop

        risk = stop - entry

        if risk <= 0:

            direction = "WAIT"

            applicable_blockers.append(
                "invalid SHORT stop geometry"
            )

        else:

            tp1 = entry - risk * 1.5
            tp2 = entry - risk * 2.5
            tp3 = entry - risk * 4.0

            rr_tp1 = 1.5
            rr_tp2 = 2.5
            rr_tp3 = 4.0

    # --------------------------------------------------------
    # SETUP QUALITY
    #
    # KHÔNG gọi đây là xác suất thắng.
    # --------------------------------------------------------

    setup_quality = min(
        100,
        abs(score) * 10,
    )

    return {
        "symbol": symbol,

        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "candidate_action":
            direction,

        "setup_score":
            score,

        "setup_quality":
            setup_quality,

        "entry": entry,

        "stop_loss": stop,

        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,

        "rr_tp1": rr_tp1,
        "rr_tp2": rr_tp2,
        "rr_tp3": rr_tp3,

        "funding_rate":
            funding,

        "open_interest":
            open_interest,

        "timeframes":
            timeframes,

        "reasons":
            reasons,

        "warnings":
            warnings,

        "blockers":
            applicable_blockers,

        "trailing_plan": {

            "enabled": True,

            "activate_after":
                "TP1",

            "move_stop_to":
                "BREAKEVEN_PLUS_FEES",

            "mode":
                "ATR_STRUCTURE",

            "atr_multiplier":
                1.0,

            "partial_close_tp1_pct":
                30,

            "partial_close_tp2_pct":
                30,

            "runner_pct":
                40,
        },

        # Bước sau:
        # Claude / DeepSeek / Codex sẽ ghi vào đây.
        "ai_reviews": {
            "claude": None,
            "deepseek": None,
            "codex": None,
        },

        "final_decision":
            "PENDING_AI_REVIEW",
    }


# ============================================================
# OUTPUT
# ============================================================

def print_setup(setup):

    print()
    print("=" * 76)
    print(setup["symbol"])
    print("=" * 76)

    print(
        "ACTION       :",
        setup["candidate_action"],
    )

    print(
        "SETUP SCORE  :",
        setup["setup_score"],
    )

    print(
        "SETUP QUALITY:",
        setup["setup_quality"],
    )

    print(
        "FUNDING      :",
        setup["funding_rate"],
    )

    print(
        "OPEN INT     :",
        setup["open_interest"],
    )

    for interval in TIMEFRAMES:

        tf = setup[
            "timeframes"
        ][interval]

        print(
            interval.upper(),
            "| TREND:",
            tf["trend"],
            "| RSI:",
            round(
                tf["rsi14"],
                2,
            ),
            "| VOL:",
            round(
                tf["volume_ratio"],
                2,
            ),
            "| MOM3:",
            round(
                tf["momentum_3"],
                3,
            ),
            "| EMA20 DIST:",
            round(
                tf[
                    "distance_ema20_pct"
                ],
                3,
            ),
            "%",
        )

    if (
        setup["candidate_action"]
        != "WAIT"
    ):

        print()

        print(
            "ENTRY        :",
            setup["entry"],
        )

        print(
            "STOP LOSS    :",
            setup["stop_loss"],
        )

        print(
            "TP1          :",
            setup["tp1"],
        )

        print(
            "TP2          :",
            setup["tp2"],
        )

        print(
            "TP3          :",
            setup["tp3"],
        )

        print(
            "TRAIL        : ATR + structure after TP1"
        )

        print(
            "PARTIAL      : 30% / 30% / 40%"
        )

    if setup["warnings"]:

        print()
        print("WARNINGS:")

        for warning in setup["warnings"]:

            print(
                "-",
                warning,
            )

    if setup["blockers"]:

        print()
        print("BLOCKERS:")

        for blocker in setup["blockers"]:

            print(
                "-",
                blocker,
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 76)

    print(
        "AUTO FUTURES V3 — PAPER MARKET INTELLIGENCE"
    )

    print(
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    print("=" * 76)

    setups = []

    for symbol in SYMBOLS:

        try:

            setup = build_setup(
                symbol
            )

            setups.append(
                setup
            )

            print_setup(
                setup
            )

        except Exception as error:

            print()
            print(
                symbol,
                "ERROR:",
                repr(error),
            )

    ranked = sorted(
        setups,
        key=lambda item:
            abs(
                item[
                    "setup_score"
                ]
            ),
        reverse=True,
    )

    snapshot = {
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "mode":
            "PAPER",

        "live_trading":
            False,

        "engine":
            "AUTO_FUTURES_V3",

        "setups":
            ranked,
    }

    snapshot_path = (
        STATE_DIR
        / "market_snapshot.json"
    )

    snapshot_path.write_text(
        json.dumps(
            snapshot,
            indent=2,
        ),
        encoding="utf-8",
    )

    with (
        LOG_DIR
        / "scanner.jsonl"
    ).open(
        "a",
        encoding="utf-8",
    ) as log:

        log.write(
            json.dumps(
                {
                    "generated_at":
                        snapshot[
                            "generated_at"
                        ],

                    "top": [
                        {
                            "symbol":
                                item[
                                    "symbol"
                                ],

                            "action":
                                item[
                                    "candidate_action"
                                ],

                            "score":
                                item[
                                    "setup_score"
                                ],
                        }

                        for item
                        in ranked[:3]
                    ],
                }
            )
            + "\n"
        )

    print()
    print("=" * 76)
    print("TOP SETUPS")
    print("=" * 76)

    for item in ranked[:3]:

        print(
            item["symbol"],
            "|",
            item[
                "candidate_action"
            ],
            "| SCORE",
            item[
                "setup_score"
            ],
            "| QUALITY",
            item[
                "setup_quality"
            ],
        )

    print()
    print(
        "SNAPSHOT:",
        snapshot_path,
    )

    print(
        "PAPER MODE ONLY"
    )

    print(
        "NO BINANCE ORDER WAS SENT"
    )


if __name__ == "__main__":
    main()
