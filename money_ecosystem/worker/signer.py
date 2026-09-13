from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .protocol import sign_payload


def sign_request_file(request_path: Path | str, output_path: Path | str, secret: bytes) -> Path:
    if len(secret) < 32:
        raise ValueError("Worker secret must be at least 32 bytes")

    request_path = Path(request_path)
    output_path = Path(output_path)
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    envelope = sign_payload(payload, secret)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(envelope.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Sign an approved Curious Beyond worker request")
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--secret-env", default="CURIOUS_WORKER_HMAC_KEY")
    args = parser.parse_args()

    secret_text = os.environ.get(args.secret_env, "")
    if len(secret_text) < 32:
        raise SystemExit(f"Required secret {args.secret_env} is missing or too short")

    sign_request_file(args.request, args.output, secret_text.encode("utf-8"))
    print("Worker request signed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
