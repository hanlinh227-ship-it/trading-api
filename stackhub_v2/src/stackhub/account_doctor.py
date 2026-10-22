from __future__ import annotations

import json
import os

from .accounts import account_status
from .telemetry import redact


def main() -> None:
    report = {
        "accounts": account_status(os.environ),
        "rules": {
            "secret_values_printed": False,
            "paypal_credentials_required": False,
            "wallet_private_keys_required": False,
            "wallet_seed_phrases_required": False,
        },
    }
    print(json.dumps(redact(report), sort_keys=True, default=str))


if __name__ == "__main__":
    main()
