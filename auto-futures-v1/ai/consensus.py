import json
import subprocess

from concurrent.futures import (
    ThreadPoolExecutor,
)

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path


ROOT = Path(
    "/opt/trading/trading-api/auto-futures-v1"
)

AI_DIR = ROOT / "ai"
STATE_DIR = ROOT / "state"
LOG_DIR = ROOT / "logs"


AI_SCRIPTS = {

    "claude":
        "claude_trader.py",

    "deepseek":
        "deepseek_trader.py",

    "codex":
        "codex_trader.py",
}


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


def run_ai(
    name,
    script,
):

    try:

        process = subprocess.run(
            [
                "python3",
                script,
            ],
            cwd=AI_DIR,
            capture_output=True,
            text=True,
            timeout=210,
        )

    except subprocess.TimeoutExpired:

        return (
            name,
            {
                "status":
                    "ERROR",

                "error":
                    "TIMEOUT",

                "reviews":
                    {},
            },
        )


    except Exception as exc:

        return (
            name,
            {
                "status":
                    "ERROR",

                "error":
                    repr(exc),

                "reviews":
                    {},
            },
        )


    if process.returncode != 0:

        return (
            name,
            {
                "status":
                    "ERROR",

                "error":
                    process.stderr[
                        -2000:
                    ],

                "reviews":
                    {},
            },
        )


    output = (
        process.stdout.strip()
    )


    if not output:

        return (
            name,
            {
                "status":
                    "ERROR",

                "error":
                    "EMPTY_OUTPUT",

                "reviews":
                    {},
            },
        )


    try:

        result = json.loads(
            output.splitlines()[-1]
        )

    except Exception:

        return (
            name,
            {
                "status":
                    "INVALID_JSON",

                "error":
                    output[-2000:],

                "reviews":
                    {},
            },
        )


    reviews = result.get(
        "reviews",
        {},
    )


    if isinstance(
        reviews,
        dict,
    ):

        for review in reviews.values():

            if isinstance(
                review,
                dict,
            ):

                review[
                    "confidence"
                ] = (
                    normalize_confidence(
                        review.get(
                            "confidence",
                            0,
                        )
                    )
                )


    return (
        name,
        result,
    )


def main():

    print(
        "Starting Claude + DeepSeek + Codex in parallel...",
        flush=True,
    )


    results = {}


    with ThreadPoolExecutor(
        max_workers=3
    ) as pool:

        futures = [

            pool.submit(
                run_ai,
                name,
                script,
            )

            for name, script
            in AI_SCRIPTS.items()
        ]


        for future in futures:

            name, result = (
                future.result()
            )

            results[name] = (
                result
            )


    claude = results.get(
        "claude",
        {},
    )

    deepseek = results.get(
        "deepseek",
        {},
    )

    codex = results.get(
        "codex",
        {},
    )


    claude_reviews = (
        claude.get(
            "reviews",
            {},
        )
    )

    deepseek_reviews = (
        deepseek.get(
            "reviews",
            {},
        )
    )

    codex_reviews = (
        codex.get(
            "reviews",
            {},
        )
    )


    symbols = sorted(

        set(
            claude_reviews
        )

        | set(
            deepseek_reviews
        )

        | set(
            codex_reviews
        )
    )


    decisions = {}


    for symbol in symbols:

        reviews = {

            "claude":
                claude_reviews.get(
                    symbol
                ),

            "deepseek":
                deepseek_reviews.get(
                    symbol
                ),

            "codex":
                codex_reviews.get(
                    symbol
                ),
        }


        available = [

            review

            for review
            in reviews.values()

            if isinstance(
                review,
                dict,
            )
        ]


        actions = [

            str(
                review.get(
                    "action",
                    "WAIT",
                )
            ).upper()

            for review
            in available
        ]


        confidences = [

            normalize_confidence(
                review.get(
                    "confidence",
                    0,
                )
            )

            for review
            in available
        ]


        average_confidence = (

            round(
                sum(confidences)
                / len(confidences),
                2,
            )

            if confidences

            else 0.0
        )


        final_action = "WAIT"

        reason = (
            "NO_3_AI_TRADE_CONSENSUS"
        )


        #
        # REQUIRE ALL THREE AI LANES.
        #

        if len(available) == 3:

            #
            # All three must agree.
            #

            if len(set(actions)) == 1:

                agreed_action = (
                    actions[0]
                )


                if agreed_action in {
                    "LONG",
                    "SHORT",
                }:

                    #
                    # Confidence floor.
                    #

                    if (
                        average_confidence
                        >= 60
                    ):

                        final_action = (
                            agreed_action
                        )

                        reason = (
                            "3_OF_3_AI_AGREE"
                        )

                    else:

                        reason = (
                            "3_AI_AGREE_BUT_CONFIDENCE_LOW"
                        )


                else:

                    final_action = (
                        agreed_action
                    )

                    reason = (
                        "3_OF_3_AI_AGREE_NO_ENTRY"
                    )

            else:

                reason = (
                    "AI_DISAGREEMENT"
                )


        else:

            reason = (
                "MISSING_AI_REVIEW"
            )


        decisions[symbol] = {

            "reviews":
                reviews,

            "available_reviewers":
                len(available),

            "actions":
                actions,

            "average_confidence":
                average_confidence,

            "final_action":
                final_action,

            "reason":
                reason,
        }


    result = {

        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "claude_status":
            claude.get(
                "status",
                "ERROR",
            ),

        "deepseek_status":
            deepseek.get(
                "status",
                "ERROR",
            ),

        "codex_status":
            codex.get(
                "status",
                "ERROR",
            ),

        "symbols":
            decisions,
    }


    STATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


    (
        STATE_DIR
        / "ai_consensus.json"
    ).write_text(

        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),

        encoding="utf-8",
    )


    with (
        LOG_DIR
        / "ai_consensus.jsonl"
    ).open(
        "a",
        encoding="utf-8",
    ) as log:

        log.write(

            json.dumps(
                result,
                ensure_ascii=False,
            )

            + "\n"
        )


    print()

    print(
        "=========================================="
    )

    print(
        "3 AI CONSENSUS STATUS"
    )

    print(
        "=========================================="
    )

    print(
        "Claude   :",
        result[
            "claude_status"
        ],
    )

    print(
        "DeepSeek :",
        result[
            "deepseek_status"
        ],
    )

    print(
        "Codex    :",
        result[
            "codex_status"
        ],
    )

    print()


    for symbol, decision \
            in decisions.items():

        print(
            symbol,
            "| AI:",
            decision[
                "available_reviewers"
            ],
            "|",
            "/".join(
                decision[
                    "actions"
                ]
            ),
            "| FINAL:",
            decision[
                "final_action"
            ],
            "| CONF:",
            decision[
                "average_confidence"
            ],
            "|",
            decision[
                "reason"
            ],
        )


    print()

    print(
        "Consensus saved:",
        STATE_DIR
        / "ai_consensus.json",
    )


if __name__ == "__main__":
    main()
