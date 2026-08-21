import json
import subprocess
import sys

from common import (
    load_snapshot,
    compact_setup,
    validate_review,
)

MODEL = "sonnet"

SYSTEM = """
You are an independent professional Binance Futures trader.

Analyze every market setup independently.

Return JSON only:

{
  "reviews": [
    {
      "symbol": "BTCUSDT",
      "action": "LONG|SHORT|WAIT|EXIT|HOLD",
      "confidence": 0,
      "entry": null,
      "stop_loss": null,
      "tp1": null,
      "tp2": null,
      "tp3": null,
      "trailing": "text",
      "invalidation": "text",
      "reason": "short text"
    }
  ]
}

Rules:

- Do not blindly follow scanner candidate_action.
- Analyze 5m, 15m and 1h together.
- Consider trend, RSI, momentum, relative volume,
  EMA extension, funding and open interest.
- Reject chase entries.
- Reject contradictory momentum.
- Reject poor RR.
- Every LONG or SHORT must have a valid stop.
- Prefer WAIT when evidence is mixed.
- Never use martingale.
- Never increase risk after a loss.
- Do not output markdown.
- Output exactly one JSON object.
"""


def normalize_confidence(value):
    try:
        value = float(value)
    except Exception:
        return 0.0

    if 0 <= value <= 1:
        value *= 100

    return max(
        0.0,
        min(100.0, value),
    )


def main():
    try:
        snapshot = load_snapshot()
    except Exception as exc:
        print(json.dumps({
            "status": "ERROR",
            "error": f"SNAPSHOT_LOAD_FAILED: {exc}",
            "reviews": {},
        }))
        return

    setups = []

    for setup in snapshot.get("setups", []):
        try:
            setups.append(
                compact_setup(setup)
            )
        except Exception:
            continue

    if not setups:
        print(json.dumps({
            "status": "ERROR",
            "error": "NO_MARKET_SETUPS",
            "reviews": {},
        }))
        return

    prompt = (
        SYSTEM
        + "\n\nMARKET DATA:\n"
        + json.dumps(
            setups,
            ensure_ascii=False,
        )
    )

    try:
        process = subprocess.run(
            [
                "claude",
                "--model",
                MODEL,
                "-p",
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )

    except subprocess.TimeoutExpired:
        print(json.dumps({
            "status": "ERROR",
            "error": "CLAUDE_TIMEOUT",
            "reviews": {},
        }))
        return

    except Exception as exc:
        print(json.dumps({
            "status": "ERROR",
            "error": repr(exc),
            "reviews": {},
        }))
        return

    if process.returncode != 0:
        print(json.dumps({
            "status": "ERROR",
            "error": process.stderr[-1000:],
            "reviews": {},
        }))
        return

    text = process.stdout.strip()

    start = text.find("{")
    end = text.rfind("}")

    if start < 0 or end <= start:
        print(json.dumps({
            "status": "INVALID_JSON",
            "error": text[:1000],
            "reviews": {},
        }))
        return

    try:
        parsed = json.loads(
            text[start:end + 1]
        )
    except Exception as exc:
        print(json.dumps({
            "status": "INVALID_JSON",
            "error": str(exc),
            "reviews": {},
        }))
        return

    clean = {}

    for review in parsed.get(
        "reviews",
        [],
    ):
        if not validate_review(review):
            continue

        symbol = str(
            review.get(
                "symbol",
                "",
            )
        ).strip().upper()

        if not symbol:
            continue

        clean[symbol] = {
            "symbol": symbol,

            "action":
                review.get("action"),

            "confidence":
                normalize_confidence(
                    review.get(
                        "confidence",
                        0,
                    )
                ),

            "entry":
                review.get("entry"),

            "stop_loss":
                review.get(
                    "stop_loss"
                ),

            "tp1":
                review.get("tp1"),

            "tp2":
                review.get("tp2"),

            "tp3":
                review.get("tp3"),

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
                "status": "OK",
                "model": MODEL,
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
