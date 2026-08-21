import json
import os
import urllib.request
import urllib.error

from common import (
    load_snapshot,
    compact_setup,
    validate_review,
)

URL = "https://api.deepseek.com/chat/completions"

MODEL = os.environ.get(
    "DEEPSEEK_MODEL",
    "deepseek-chat",
)

SYSTEM = """
You are an independent Binance Futures trader and adversarial risk reviewer.

Evaluate each setup like a disciplined human futures trader.

Return JSON only in exactly this structure:

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

Trading rules:

- Independently analyze the market data.
- Do not blindly follow candidate_action.
- Prefer WAIT over a weak setup.
- Reject overextended/chasing entries.
- Reject entries with contradictory momentum.
- Reject poor structure or poor risk/reward.
- Consider RSI, trend, momentum, volume, funding, open interest,
  EMA distance and multi-timeframe alignment.
- A strong trend alone is not enough to enter.
- Never recommend martingale.
- Never recommend averaging into a losing position.
- Never increase risk simply because the previous trade lost.
- Every LONG/SHORT must have a valid stop loss.
- TP levels should be structurally and mathematically coherent.
- trailing should explain when and how the stop should move.
- If evidence is conflicting, use WAIT.
- Do not output markdown.
- Do not output text outside the JSON object.
"""


def deepseek_request(setups):
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()

    if not key:
        return {
            "status": "UNAVAILABLE",
            "error": "DEEPSEEK_API_KEY_NOT_LOADED",
            "reviews": {},
        }

    request_body = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM,
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "market_setups": setups,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "temperature": 0.1,
        "max_tokens": 3000,
        "stream": False,
    }

    payload = json.dumps(
        request_body,
        ensure_ascii=False,
    ).encode("utf-8")

    request = urllib.request.Request(
        URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=120,
        ) as response:
            body = json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            error_body = str(exc)

        return {
            "status": "ERROR",
            "error": f"HTTP_{exc.code}: {error_body}",
            "reviews": {},
        }

    except urllib.error.URLError as exc:
        return {
            "status": "ERROR",
            "error": f"NETWORK_ERROR: {exc}",
            "reviews": {},
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "error": repr(exc),
            "reviews": {},
        }

    try:
        text = (
            body["choices"][0]["message"]["content"]
            .strip()
        )
    except Exception:
        return {
            "status": "ERROR",
            "error": "DEEPSEEK_RESPONSE_SHAPE_INVALID",
            "reviews": {},
        }

    start = text.find("{")
    end = text.rfind("}")

    if start < 0 or end <= start:
        return {
            "status": "INVALID_JSON",
            "error": text[:1000],
            "reviews": {},
        }

    json_text = text[start:end + 1]

    try:
        parsed = json.loads(json_text)
    except Exception as exc:
        return {
            "status": "INVALID_JSON",
            "error": str(exc),
            "reviews": {},
        }

    reviews = parsed.get("reviews")

    if not isinstance(reviews, list):
        return {
            "status": "INVALID_SCHEMA",
            "error": "reviews must be an array",
            "reviews": {},
        }

    clean = {}

    for review in reviews:
        if not validate_review(review):
            continue

        symbol = str(
            review.get("symbol", "")
        ).strip().upper()

        if not symbol:
            continue

        clean[symbol] = {
            "symbol": symbol,
            "action": review.get("action"),
            "confidence": float(
                review.get("confidence", 0)
            ),
            "entry": review.get("entry"),
            "stop_loss": review.get("stop_loss"),
            "tp1": review.get("tp1"),
            "tp2": review.get("tp2"),
            "tp3": review.get("tp3"),
            "trailing": review.get(
                "trailing",
                "",
            ),
            "invalidation": review.get(
                "invalidation",
                "",
            ),
            "reason": review.get(
                "reason",
                "",
            ),
        }

    return {
        "status": "OK",
        "model": MODEL,
        "review_count": len(clean),
        "reviews": clean,
    }


def main():
    try:
        snapshot = load_snapshot()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error": f"SNAPSHOT_LOAD_FAILED: {exc}",
                    "reviews": {},
                },
                ensure_ascii=False,
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
                compact_setup(setup)
            )
        except Exception:
            continue

    if not setups:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error": "NO_MARKET_SETUPS",
                    "reviews": {},
                },
                ensure_ascii=False,
            )
        )
        return

    result = deepseek_request(
        setups
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
