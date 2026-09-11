from __future__ import annotations

import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation

import httpx

BASE_URL = "https://www.task-force.app"


def solve_challenge(prompt: str) -> str | None:
    text = prompt.strip()

    quoted = re.search(r"(?:reverse|backwards?)\s+(?:the\s+)?(?:string\s+)?[\"']([^\"']+)[\"']", text, re.IGNORECASE)
    if quoted:
        return quoted.group(1)[::-1]

    upper = re.search(r"(?:uppercase|upper-case|convert\s+to\s+uppercase)\s+(?:the\s+)?(?:string\s+)?[\"']([^\"']+)[\"']", text, re.IGNORECASE)
    if upper:
        return upper.group(1).upper()

    lower = re.search(r"(?:lowercase|lower-case|convert\s+to\s+lowercase)\s+(?:the\s+)?(?:string\s+)?[\"']([^\"']+)[\"']", text, re.IGNORECASE)
    if lower:
        return lower.group(1).lower()

    arithmetic = re.search(r"(-?\d+(?:\.\d+)?)\s*([+\-*/x×])\s*(-?\d+(?:\.\d+)?)", text)
    if arithmetic:
        try:
            left = Decimal(arithmetic.group(1))
            right = Decimal(arithmetic.group(3))
        except InvalidOperation:
            return None
        op = arithmetic.group(2)
        if op == "+":
            result = left + right
        elif op == "-":
            result = left - right
        elif op in {"*", "x", "×"}:
            result = left * right
        elif op == "/" and right != 0:
            result = left / right
        else:
            return None
        normalized = result.normalize()
        return format(normalized, "f")

    return None


def _headers_bearer(api_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}


def _headers_api_key(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "Accept": "application/json"}


def verify_if_needed(api_key: str, base_url: str = BASE_URL) -> dict[str, object]:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        probe = client.get(
            f"{base_url.rstrip('/')}/api/agent/tasks",
            params={"status": "ACTIVE", "limit": 1},
            headers=_headers_api_key(api_key),
        )
        if probe.status_code == 200:
            return {"verified": True, "action": "already_verified"}
        if probe.status_code not in (401, 403):
            return {"verified": False, "action": "probe_failed", "status_code": probe.status_code}

        challenge_response = client.post(
            f"{base_url.rstrip('/')}/api/agent/verify/challenge",
            headers=_headers_bearer(api_key),
        )
        challenge_response.raise_for_status()
        challenge = challenge_response.json()
        challenge_id = challenge.get("challengeId")
        prompt = str(challenge.get("prompt") or "")
        answer = solve_challenge(prompt)
        if not challenge_id or answer is None:
            return {
                "verified": False,
                "action": "challenge_unrecognized_no_submit",
                "prompt": prompt,
            }

        submit = client.post(
            f"{base_url.rstrip('/')}/api/agent/verify/submit",
            headers={**_headers_bearer(api_key), "Content-Type": "application/json"},
            json={"challengeId": challenge_id, "answer": answer},
        )
        try:
            payload = submit.json()
        except ValueError:
            payload = {}
        if submit.is_success:
            return {"verified": True, "action": "challenge_submitted", "status_code": submit.status_code}
        return {
            "verified": False,
            "action": "challenge_rejected",
            "status_code": submit.status_code,
            "message": str(payload.get("message") or payload.get("error") or "verification failed"),
        }


def main() -> None:
    api_key = os.getenv("TASKFORCE_API_KEY", "").strip()
    if not api_key:
        print(json.dumps({"verified": False, "action": "missing_api_key"}, sort_keys=True))
        raise SystemExit(2)
    result = verify_if_needed(api_key)
    print(json.dumps(result, sort_keys=True))
    if not result.get("verified"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
