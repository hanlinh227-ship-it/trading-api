import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"

SNAPSHOT_FILE = STATE / "market_snapshot.json"
CONSENSUS_FILE = STATE / "ai_consensus.json"
POSITIONS_FILE = STATE / "paper_positions.json"
DAILY_FILE = STATE / "daily_risk.json"
OUTPUT_FILE = STATE / "risk_decisions.json"

MODE = "PAPER"

# ============================================================
# HARD RISK SETTINGS
# ============================================================

RISK_PER_TRADE_PCT = 0.50

MAX_DAILY_LOSS_PCT = 2.0

MAX_OPEN_POSITIONS = 3

MAX_LEVERAGE = 3

MIN_AI_CONFIDENCE = 60

REQUIRE_AI_COUNT = 3

REQUIRE_SCANNER_MATCH = True


def utc_day():
    return datetime.now(
        timezone.utc
    ).strftime("%Y-%m-%d")


def load(path, default):
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return default


def save(path, data):
    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


snapshot = load(
    SNAPSHOT_FILE,
    {
        "setups": []
    }
)

consensus = load(
    CONSENSUS_FILE,
    {
        "symbols": {}
    }
)

position_state = load(
    POSITIONS_FILE,
    {
        "positions": []
    }
)

daily = load(
    DAILY_FILE,
    {
        "date": utc_day(),
        "starting_balance": 10000.0,
        "realized_pnl": 0.0,
        "kill_switch": False,
    }
)


# ============================================================
# RESET DAILY STATE
# ============================================================

if daily.get("date") != utc_day():

    daily = {
        "date": utc_day(),
        "starting_balance": 10000.0,
        "realized_pnl": 0.0,
        "kill_switch": False,
    }


# ============================================================
# CALCULATE REALIZED PAPER PNL
# ============================================================

positions = position_state.get(
    "positions",
    []
)

daily_realized = sum(
    float(
        p.get(
            "realized_pnl",
            0
        )
    )
    for p in positions
)

daily["realized_pnl"] = daily_realized

starting_balance = float(
    daily.get(
        "starting_balance",
        10000
    )
)

max_daily_loss_usd = (
    starting_balance
    * MAX_DAILY_LOSS_PCT
    / 100
)


if daily_realized <= -max_daily_loss_usd:

    daily["kill_switch"] = True


save(
    DAILY_FILE,
    daily
)


# ============================================================
# OPEN POSITION COUNT
# ============================================================

open_positions = [
    p for p in positions
    if p.get("status") == "OPEN"
]

open_symbols = {
    p.get("symbol")
    for p in open_positions
}


# ============================================================
# SETUPS
# ============================================================

setups = {
    x["symbol"]: x
    for x in snapshot.get(
        "setups",
        []
    )
    if x.get("symbol")
}


# ============================================================
# RISK DECISIONS
# ============================================================

decisions = {}


for symbol, ai in consensus.get(
    "symbols",
    {}
).items():

    action = str(
        ai.get(
            "final_action",
            "WAIT"
        )
    ).upper()

    setup = setups.get(
        symbol,
        {}
    )

    approved = False

    reason = "NO_TRADE"


    # --------------------------------------------------------
    # HARD KILL SWITCH
    # --------------------------------------------------------

    if daily.get(
        "kill_switch"
    ):

        reason = "DAILY_LOSS_KILL_SWITCH"


    # --------------------------------------------------------
    # ONLY LONG / SHORT ARE NEW ENTRIES
    # --------------------------------------------------------

    elif action not in (
        "LONG",
        "SHORT"
    ):

        reason = "NO_TRADE"


    # --------------------------------------------------------
    # REQUIRE ALL THREE AI
    # --------------------------------------------------------

    elif ai.get(
        "available_reviewers",
        0
    ) != REQUIRE_AI_COUNT:

        reason = "REQUIRE_3_AI"


    # --------------------------------------------------------
    # CONFIDENCE FLOOR
    # --------------------------------------------------------

    elif float(
        ai.get(
            "average_confidence",
            0
        )
    ) < MIN_AI_CONFIDENCE:

        reason = "AI_CONFIDENCE_TOO_LOW"


    # --------------------------------------------------------
    # MAX POSITIONS
    # --------------------------------------------------------

    elif len(
        open_positions
    ) >= MAX_OPEN_POSITIONS:

        reason = "MAX_POSITIONS_REACHED"


    # --------------------------------------------------------
    # NO DUPLICATE SYMBOL
    # --------------------------------------------------------

    elif symbol in open_symbols:

        reason = "POSITION_ALREADY_OPEN"


    # --------------------------------------------------------
    # SCANNER / AI MUST AGREE
    # --------------------------------------------------------

    elif (
        REQUIRE_SCANNER_MATCH
        and setup.get(
            "candidate_action"
        ) != action
    ):

        reason = "SCANNER_AI_CONFLICT"


    # --------------------------------------------------------
    # SCANNER BLOCKERS
    # --------------------------------------------------------

    elif setup.get(
        "blockers"
    ):

        reason = "SCANNER_BLOCKER"


    # --------------------------------------------------------
    # ENTRY / STOP REQUIRED
    # --------------------------------------------------------

    elif setup.get(
        "entry"
    ) is None:

        reason = "NO_ENTRY"


    elif setup.get(
        "stop_loss"
    ) is None:

        reason = "NO_STOP"


    # --------------------------------------------------------
    # STOP GEOMETRY
    # --------------------------------------------------------

    elif (
        action == "LONG"
        and float(
            setup["stop_loss"]
        ) >= float(
            setup["entry"]
        )
    ):

        reason = "INVALID_LONG_STOP"


    elif (
        action == "SHORT"
        and float(
            setup["stop_loss"]
        ) <= float(
            setup["entry"]
        )
    ):

        reason = "INVALID_SHORT_STOP"


    # --------------------------------------------------------
    # PASS
    # --------------------------------------------------------

    else:

        approved = True

        reason = "PASS"


    decisions[symbol] = {

        "action":
            action,

        "approved":
            approved,

        "reason":
            reason,

        "entry":
            setup.get(
                "entry"
            ),

        "stop_loss":
            setup.get(
                "stop_loss"
            ),

        "tp1":
            setup.get(
                "tp1"
            ),

        "tp2":
            setup.get(
                "tp2"
            ),

        "tp3":
            setup.get(
                "tp3"
            ),

        "risk_pct":
            RISK_PER_TRADE_PCT,

        "max_leverage":
            MAX_LEVERAGE,

        "ai_confidence":
            ai.get(
                "average_confidence",
                0
            ),
    }


output = {

    "generated_at":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "mode":
        MODE,

    "kill_switch":
        daily.get(
            "kill_switch",
            False
        ),

    "daily_realized_pnl":
        daily_realized,

    "max_daily_loss_usd":
        max_daily_loss_usd,

    "open_positions":
        len(
            open_positions
        ),

    "max_open_positions":
        MAX_OPEN_POSITIONS,

    "decisions":
        decisions,
}


save(
    OUTPUT_FILE,
    output
)


print()
print(
    "=========================================="
)

print(
    "HARD RISK ENGINE"
)

print(
    "=========================================="
)

print(
    "MODE              :",
    MODE
)

print(
    "KILL SWITCH       :",
    output[
        "kill_switch"
    ]
)

print(
    "DAILY PNL         :",
    round(
        daily_realized,
        4
    )
)

print(
    "DAILY LOSS LIMIT  :",
    -max_daily_loss_usd
)

print(
    "OPEN POSITIONS    :",
    len(
        open_positions
    ),
    "/",
    MAX_OPEN_POSITIONS
)

print()


for symbol, decision \
        in decisions.items():

    print(
        symbol,
        "|",
        decision[
            "action"
        ],
        "| APPROVED:",
        decision[
            "approved"
        ],
        "|",
        decision[
            "reason"
        ]
    )


print()

print(
    "PAPER SAFETY ACTIVE"
)

print(
    "NO REAL BINANCE ORDER AUTHORITY"
)
