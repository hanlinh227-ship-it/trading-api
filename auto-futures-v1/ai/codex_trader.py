import json
import subprocess

from common import (
    load_snapshot,
    compact_setup,
)


MODEL = "gpt-5.6-sol"


PROMPT = """
You are the third independent reviewer in a Binance Futures
paper-trading research system.

Your job is to independently evaluate the supplied market setups.

Do NOT blindly agree with:
- the scanner
- Claude
- DeepSeek
- candidate_action

Evaluate each symbol independently.

Consider:
- 5m trend
- 15m trend
- 1h trend
- RSI
- momentum
- relative volume
- EMA extension
- funding
- open interest
- warnings
- blockers
- entry quality
- stop placement
- risk/reward

Be conservative.

If evidence is mixed, choose WAIT.

Reject:
- chasing
- overextended entries
- contradictory momentum
- weak volume confirmation
- poor risk/reward
- invalid stop placement

Never recommend:
- martingale
- averaging down into losses
- increasing risk after a loss

Return ONLY valid JSON.

Required schema:

{
  "reviews": [
    {
      "symbol": "BTCUSDT",
      "action": "LONG",
      "confidence": 70,
      "entry": 0,
      "stop_loss": 0,
      "tp1": 0,
      "tp2": 0,
      "tp3": 0,
      "trailing": "text",
      "invalidation": "text",
      "reason": "text"
    }
  ]
}

action must be exactly one of:

LONG
SHORT
WAIT
HOLD
EXIT

confidence must be from 0 to 100.

For WAIT:
entry, stop_loss and take profits may be null.

No markdown.
No explanation outside JSON.
"""


def normalize_confidence(value):

    try:
        value = float(value)
    except Exception:
        return 0.0

    if 0 <= value <= 1:
        value *= 100

    return round(
        max(
            0.0,
            min(
                100.0,
                value,
            ),
        ),
        2,
    )


def main():

    try:

        snapshot = load_snapshot()

    except Exception as exc:

        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error":
                        f"SNAPSHOT_LOAD_FAILED: {exc}",
                    "reviews": {},
                }
            )
        )

        return


    setups = []

    for setup in snapshot.get(
        "setups",
        [],
    ):

        try:

            setups.append(
                compact_setup(
                    setup
                )
            )

        except Exception:
            continue


    if not setups:

        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error":
                        "NO_MARKET_SETUPS",
                    "reviews": {},
                }
            )
        )

        return


    full_prompt = (
        PROMPT
        + "\n\nMARKET DATA:\n"
        + json.dumps(
            setups,
            ensure_ascii=False,
        )
    )


    try:

        process = subprocess.run(
            [
                "/usr/bin/codex",
                "exec",
                full_prompt,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )

    except subprocess.TimeoutExpired:

        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error":
                        "CODEX_TIMEOUT",
                    "reviews": {},
                }
            )
        )

        return

    except Exception as exc:

        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error":
                        repr(exc),
                    "reviews": {},
                }
            )
        )

        return


    if process.returncode != 0:

        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error":
                        process.stderr[-2000:],
                    "reviews": {},
                }
            )
        )

        return


    #
    # Codex CLI writes diagnostic information separately.
    # We only parse stdout for the final model response.
    #

    text = process.stdout.strip()

    start = text.find("{")
    end = text.rfind("}")


    if start < 0 or end <= start:

        print(
            json.dumps(
                {
                    "status":
                        "INVALID_JSON",

                    "error":
                        text[-1500:],

                    "reviews": {},
                },
                ensure_ascii=False,
            )
        )

        return


    try:

        parsed = json.loads(
            text[start:end + 1]
        )

    except Exception as exc:

        print(
            json.dumps(
                {
                    "status":
                        "INVALID_JSON",

                    "error":
                        str(exc),

                    "reviews": {},
                }
            )
        )

        return


    reviews = parsed.get(
        "reviews",
        [],
    )


    if not isinstance(
        reviews,
        list,
    ):

        print(
            json.dumps(
                {
                    "status":
                        "INVALID_SCHEMA",

                    "error":
                        "reviews must be array",

                    "reviews": {},
                }
            )
        )

        return


    clean = {}


    for review in reviews:

        if not isinstance(
            review,
            dict,
        ):
            continue


        symbol = str(
            review.get(
                "symbol",
                "",
            )
        ).strip().upper()


        action = str(
            review.get(
                "action",
                "WAIT",
            )
        ).strip().upper()


        if not symbol:
            continue


        if action not in {
            "LONG",
            "SHORT",
            "WAIT",
            "HOLD",
            "EXIT",
        }:

            action = "WAIT"


        clean[symbol] = {

            "symbol":
                symbol,

            "action":
                action,

            "confidence":
                normalize_confidence(
                    review.get(
                        "confidence",
                        0,
                    )
                ),

            "entry":
                review.get(
                    "entry"
                ),

            "stop_loss":
                review.get(
                    "stop_loss"
                ),

            "tp1":
                review.get(
                    "tp1"
                ),

            "tp2":
                review.get(
                    "tp2"
                ),

            "tp3":
                review.get(
                    "tp3"
                ),

            "trailing":
                review.get(
                    "trailing",
                    "",
                ),

            "invalidation":
                review.get(
                    "invalidation",
                    "",
                ),

            "reason":
                review.get(
                    "reason",
                    "",
                ),
        }


    print(
        json.dumps(
            {
                "status":
                    "OK",

                "model":
                    MODEL,

                "review_count":
                    len(clean),

                "reviews":
                    clean,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
