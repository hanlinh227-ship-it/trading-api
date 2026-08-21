import json
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path("/opt/trading/trading-api/auto-futures-v1")
STATE = ROOT / "state"
LOGS = ROOT / "logs"

POSITIONS_FILE = STATE / "paper_positions.json"
RISK_FILE = STATE / "risk_decisions.json"
TRADES_LOG = LOGS / "paper_trades.jsonl"

BASE = "https://fapi.binance.com"

ACCOUNT_BALANCE = 10000.0
RISK_PER_TRADE_PCT = 0.5
MAX_LEVERAGE = 3


def now():
    return datetime.now(timezone.utc).isoformat()


def get_price(symbol):
    url = f"{BASE}/fapi/v1/ticker/price?symbol={symbol}"

    with urllib.request.urlopen(
        url,
        timeout=10,
    ) as response:

        data = json.loads(
            response.read().decode()
        )

    return float(data["price"])


def load_json(path, default):

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


def save_json(path, data):

    path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def calculate_position_size(
    entry,
    stop,
):

    risk_usd = (
        ACCOUNT_BALANCE
        * RISK_PER_TRADE_PCT
        / 100
    )

    distance = abs(
        entry - stop
    )

    if distance <= 0:
        return 0.0

    qty = (
        risk_usd
        / distance
    )

    notional = (
        qty
        * entry
    )

    max_notional = (
        ACCOUNT_BALANCE
        * MAX_LEVERAGE
    )

    if notional > max_notional:

        qty = (
            max_notional
            / entry
        )

    return qty


def realized_pnl(
    side,
    entry,
    exit_price,
    qty,
):

    if side == "LONG":

        return (
            exit_price
            - entry
        ) * qty

    if side == "SHORT":

        return (
            entry
            - exit_price
        ) * qty

    return 0.0


def log_event(event):

    with TRADES_LOG.open(
        "a",
        encoding="utf-8",
    ) as log:

        log.write(
            json.dumps(
                event,
                ensure_ascii=False,
            )
            + "\n"
        )


def create_positions(
    positions,
    decisions,
):

    existing_symbols = {
        p["symbol"]
        for p in positions
        if p["status"] == "OPEN"
    }

    for symbol, decision \
            in decisions.items():

        if not decision.get(
            "approved"
        ):
            continue

        if symbol in existing_symbols:
            continue

        side = decision.get(
            "action"
        )

        if side not in (
            "LONG",
            "SHORT",
        ):
            continue

        entry = decision.get(
            "entry"
        )

        stop = decision.get(
            "stop_loss"
        )

        if (
            entry is None
            or stop is None
        ):
            continue

        qty = calculate_position_size(
            float(entry),
            float(stop),
        )

        if qty <= 0:
            continue

        position = {

            "id":
                f"{symbol}-{int(datetime.now().timestamp())}",

            "symbol":
                symbol,

            "side":
                side,

            "entry":
                float(entry),

            "stop_loss":
                float(stop),

            "initial_stop":
                float(stop),

            "tp1":
                decision.get(
                    "tp1"
                ),

            "tp2":
                decision.get(
                    "tp2"
                ),

            "tp3":
                decision.get(
                    "tp3"
                ),

            "quantity":
                qty,

            "remaining_qty":
                qty,

            "tp1_done":
                False,

            "tp2_done":
                False,

            "break_even":
                False,

            "trailing_active":
                False,

            "trail_price":
                None,

            "realized_pnl":
                0.0,

            "status":
                "OPEN",

            "opened_at":
                now(),

            "closed_at":
                None,
        }

        positions.append(
            position
        )

        log_event({
            "event":
                "PAPER_OPEN",

            "timestamp":
                now(),

            **position,
        })


def close_partial(
    position,
    price,
    fraction,
    event_name,
):

    qty = (
        position[
            "quantity"
        ]
        * fraction
    )

    qty = min(
        qty,
        position[
            "remaining_qty"
        ],
    )

    pnl = realized_pnl(

        position[
            "side"
        ],

        position[
            "entry"
        ],

        price,

        qty,
    )

    position[
        "remaining_qty"
    ] -= qty

    position[
        "realized_pnl"
    ] += pnl

    log_event({

        "event":
            event_name,

        "timestamp":
            now(),

        "symbol":
            position[
                "symbol"
            ],

        "price":
            price,

        "quantity":
            qty,

        "pnl":
            pnl,

        "remaining_qty":
            position[
                "remaining_qty"
            ],
    })


def close_all(
    position,
    price,
    reason,
):

    qty = position[
        "remaining_qty"
    ]

    pnl = realized_pnl(

        position[
            "side"
        ],

        position[
            "entry"
        ],

        price,

        qty,
    )

    position[
        "realized_pnl"
    ] += pnl

    position[
        "remaining_qty"
    ] = 0

    position[
        "status"
    ] = "CLOSED"

    position[
        "closed_at"
    ] = now()

    log_event({

        "event":
            "PAPER_CLOSE",

        "timestamp":
            now(),

        "symbol":
            position[
                "symbol"
            ],

        "price":
            price,

        "reason":
            reason,

        "pnl":
            pnl,

        "total_pnl":
            position[
                "realized_pnl"
            ],
    })


def manage_long(
    position,
    price,
):

    if (
        price
        <= position[
            "stop_loss"
        ]
    ):

        close_all(
            position,
            price,
            "STOP_LOSS",
        )

        return

    if (
        not position[
            "tp1_done"
        ]
        and position[
            "tp1"
        ] is not None
        and price
        >= position[
            "tp1"
        ]
    ):

        close_partial(
            position,
            price,
            0.30,
            "TP1",
        )

        position[
            "tp1_done"
        ] = True

        position[
            "break_even"
        ] = True

        position[
            "stop_loss"
        ] = position[
            "entry"
        ]

    if (
        not position[
            "tp2_done"
        ]
        and position[
            "tp2"
        ] is not None
        and price
        >= position[
            "tp2"
        ]
    ):

        close_partial(
            position,
            price,
            0.30,
            "TP2",
        )

        position[
            "tp2_done"
        ] = True

        position[
            "trailing_active"
        ] = True

        position[
            "trail_price"
        ] = position[
            "tp1"
        ]

    if position[
        "trailing_active"
    ]:

        distance = (
            position[
                "entry"
            ]
            - position[
                "initial_stop"
            ]
        )

        candidate = (
            price
            - distance
        )

        if (
            position[
                "trail_price"
            ] is None
            or candidate
            > position[
                "trail_price"
            ]
        ):

            position[
                "trail_price"
            ] = candidate

            position[
                "stop_loss"
            ] = max(
                position[
                    "stop_loss"
                ],
                candidate,
            )

    if (
        position[
            "tp3"
        ] is not None
        and price
        >= position[
            "tp3"
        ]
    ):

        close_all(
            position,
            price,
            "TP3",
        )


def manage_short(
    position,
    price,
):

    if (
        price
        >= position[
            "stop_loss"
        ]
    ):

        close_all(
            position,
            price,
            "STOP_LOSS",
        )

        return

    if (
        not position[
            "tp1_done"
        ]
        and position[
            "tp1"
        ] is not None
        and price
        <= position[
            "tp1"
        ]
    ):

        close_partial(
            position,
            price,
            0.30,
            "TP1",
        )

        position[
            "tp1_done"
        ] = True

        position[
            "break_even"
        ] = True

        position[
            "stop_loss"
        ] = position[
            "entry"
        ]

    if (
        not position[
            "tp2_done"
        ]
        and position[
            "tp2"
        ] is not None
        and price
        <= position[
            "tp2"
        ]
    ):

        close_partial(
            position,
            price,
            0.30,
            "TP2",
        )

        position[
            "tp2_done"
        ] = True

        position[
            "trailing_active"
        ] = True

        position[
            "trail_price"
        ] = position[
            "tp1"
        ]

    if position[
        "trailing_active"
    ]:

        distance = (
            position[
                "initial_stop"
            ]
            - position[
                "entry"
            ]
        )

        candidate = (
            price
            + distance
        )

        if (
            position[
                "trail_price"
            ] is None
            or candidate
            < position[
                "trail_price"
            ]
        ):

            position[
                "trail_price"
            ] = candidate

            position[
                "stop_loss"
            ] = min(
                position[
                    "stop_loss"
                ],
                candidate,
            )

    if (
        position[
            "tp3"
        ] is not None
        and price
        <= position[
            "tp3"
        ]
    ):

        close_all(
            position,
            price,
            "TP3",
        )


def manage_positions(
    positions,
):

    for position in positions:

        if (
            position[
                "status"
            ]
            != "OPEN"
        ):
            continue

        try:

            price = get_price(
                position[
                    "symbol"
                ]
            )

        except Exception as exc:

            print(
                "PRICE ERROR:",
                position[
                    "symbol"
                ],
                exc,
            )

            continue

        if (
            position[
                "side"
            ]
            == "LONG"
        ):

            manage_long(
                position,
                price,
            )

        elif (
            position[
                "side"
            ]
            == "SHORT"
        ):

            manage_short(
                position,
                price,
            )


def main():

    risk = load_json(
        RISK_FILE,
        {
            "decisions": {}
        },
    )

    state = load_json(
        POSITIONS_FILE,
        {
            "mode":
                "PAPER",

            "positions":
                [],
        },
    )

    positions = state.get(
        "positions",
        [],
    )

    create_positions(

        positions,

        risk.get(
            "decisions",
            {},
        ),
    )

    manage_positions(
        positions
    )

    state = {

        "mode":
            "PAPER",

        "updated_at":
            now(),

        "positions":
            positions,
    }

    save_json(
        POSITIONS_FILE,
        state,
    )

    open_positions = [

        p
        for p
        in positions

        if p[
            "status"
        ] == "OPEN"
    ]

    closed_positions = [

        p
        for p
        in positions

        if p[
            "status"
        ] == "CLOSED"
    ]

    total_realized = sum(

        p.get(
            "realized_pnl",
            0.0,
        )

        for p
        in positions
    )

    print()
    print(
        "=========================================="
    )

    print(
        "PAPER POSITION MANAGER"
    )

    print(
        "=========================================="
    )

    print(
        "OPEN POSITIONS :",
        len(
            open_positions
        ),
    )

    print(
        "CLOSED         :",
        len(
            closed_positions
        ),
    )

    print(
        "REALIZED PNL   :",
        round(
            total_realized,
            4,
        ),
    )

    for p in open_positions:

        print(
            p[
                "symbol"
            ],
            p[
                "side"
            ],
            "| entry",
            p[
                "entry"
            ],
            "| SL",
            p[
                "stop_loss"
            ],
            "| remaining",
            round(
                p[
                    "remaining_qty"
                ],
                8,
            ),
        )

    print()
    print(
        "PAPER MODE ONLY"
    )

    print(
        "NO REAL BINANCE ORDER WAS SENT"
    )


if __name__ == "__main__":
    main()
