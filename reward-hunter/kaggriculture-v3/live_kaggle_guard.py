#!/usr/bin/env python3
"""Single-writer Kaggriculture live submit/status controller.

This module never runs local matches. It lists Kaggle live submissions, updates the durable
LATEST/CURRENT_BEST/BEST_EVER ledger, submits only a genuinely new agent SHA when no other live
submission is active, and applies a per-SHA backoff after platform/quota/validation failures.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from live_score_ledger import parse_rows, update_ledger

COMPETITION = "kaggriculture"
ACTIVE_STATES = ("PENDING", "RUNNING", "QUEUED")


def utcnow():
    return dt.datetime.now(dt.timezone.utc)


def stamp(value=None):
    value = value or utcnow()
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def atomic_json(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def safe_run(args):
    return subprocess.run(args, text=True, capture_output=True, check=False)


def list_submissions(output_path: Path):
    p = safe_run(["kaggle", "competitions", "submissions", "-c", COMPETITION])
    if p.returncode != 0:
        print(f"KAGGLE_LIVE_LIST_FAILED code={p.returncode}; no submission attempted")
        return None
    output_path.write_text(p.stdout)
    print(p.stdout, end="")
    return parse_rows(p.stdout)


def update_score_state(ledger_path: Path, rows, desc, sha, summary_path: Path):
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    current, summary = update_ledger(ledger, rows, desc, sha)
    atomic_json(ledger_path, ledger)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print("LIVE_SCOREBOARD", json.dumps({
        "candidate_result": summary["candidate_result"],
        "latest_ref": summary["latest"].get("submission_ref"),
        "latest_score": summary["latest"].get("public_score"),
        "current_best_ref": summary["current_best"].get("submission_ref"),
        "current_best_score": summary["current_best"].get("public_score"),
        "best_ever_score": summary["best_ever"].get("public_score"),
        "delta_current_best": summary.get("latest_vs_current_best_delta"),
        "delta_best_ever": summary.get("latest_vs_best_ever_delta"),
    }, sort_keys=True))
    for change in summary.get("score_changes", []):
        print(f"LIVE_SUBMISSION_SCORE_CHANGE ref={change['ref']} previous={change['previous']} new={change['new']} delta={change['delta']}")
    return ledger, current, summary


def mark_visible(ledger_path: Path, current, sha, desc):
    ledger = json.loads(ledger_path.read_text())
    ledger["sha256"] = sha
    ledger["description"] = desc
    ledger["source_run"] = os.getenv("GITHUB_RUN_ID", "")
    ledger["submission_ref"] = current["ref"]
    status = current.get("status", "")
    if "COMPLETE" in status:
        ledger["status"] = "complete"
        if ledger.get("pending_submit_at"):
            ledger["submitted_at"] = ledger["pending_submit_at"]
        ledger.pop("pending_submit_sha", None)
        ledger.pop("pending_submit_at", None)
        ledger.pop("pending_description", None)
        print(f"KAGGLE_LIVE_COMPLETE ref={current['ref']} no duplicate submission")
    else:
        ledger["status"] = "pending_visible"
        ledger.setdefault("pending_submit_sha", sha)
        ledger.setdefault("pending_description", desc)
        print(f"KAGGLE_LIVE_PENDING_VISIBLE ref={current['ref']} no duplicate submission")
    atomic_json(ledger_path, ledger)


def failure_backoff_remaining(ledger, sha, seconds):
    if ledger.get("last_submit_failure_sha") != sha:
        return 0
    then = parse_time(ledger.get("last_submit_failure_at"))
    if then is None:
        return 0
    age = max(0, int((utcnow() - then).total_seconds()))
    return max(0, seconds - age)


def record_failure(ledger_path: Path, sha, desc, returncode, backoff):
    ledger = json.loads(ledger_path.read_text())
    if ledger.get("last_submit_failure_sha") == sha:
        count = int(ledger.get("last_submit_failure_count", 0) or 0) + 1
    else:
        count = 1
    ledger.update({
        "last_submit_failure_sha": sha,
        "last_submit_failure_at": stamp(),
        "last_submit_failure_count": count,
        "last_submit_failure_code": int(returncode),
        "last_submit_failure_description": desc,
        "last_submit_failure_backoff_seconds": int(backoff),
        "status": "submit_backoff",
    })
    atomic_json(ledger_path, ledger)


def clear_failure(ledger):
    for key in (
        "last_submit_failure_sha", "last_submit_failure_at", "last_submit_failure_count",
        "last_submit_failure_code", "last_submit_failure_description",
        "last_submit_failure_backoff_seconds",
    ):
        ledger.pop(key, None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--main", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--label-prefix", default="V6.2 live-production-first")
    ap.add_argument("--failure-backoff-seconds", type=int, default=3600)
    ap.add_argument("--visibility-wait-seconds", type=int, default=10)
    args = ap.parse_args()

    ledger_path = Path(args.ledger)
    main_path = Path(args.main)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "live-scoreboard.json"

    if not os.getenv("KAGGLE_API_TOKEN"):
        print("KAGGLE_LIVE_DEFERRED missing credential; no simulator fallback")
        return 0

    sha = hashlib.sha256(main_path.read_bytes()).hexdigest()
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    if ledger.get("sha256") == sha and ledger.get("description"):
        desc = ledger["description"]
    elif ledger.get("pending_submit_sha") == sha and ledger.get("pending_description"):
        desc = ledger["pending_description"]
    else:
        desc = f"{args.label_prefix} {sha[:12]}"

    decision = {
        "sha256": sha,
        "description": desc,
        "confirmed_sha256": ledger.get("sha256", ""),
        "confirmed_description": ledger.get("description", ""),
        "pending_submit_sha": ledger.get("pending_submit_sha", ""),
        "failure_backoff_seconds": args.failure_backoff_seconds,
    }
    (out / "live-decision.json").write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n")
    print("LIVE_ONLY_DECISION", json.dumps(decision, sort_keys=True))

    rows = list_submissions(out / "kaggle-before.txt")
    if rows is None:
        return 0
    ledger, current, _ = update_score_state(ledger_path, rows, desc, sha, summary_path)

    if current:
        mark_visible(ledger_path, current, sha, desc)
        return 0

    if ledger.get("pending_submit_sha") == sha:
        print("KAGGLE_LIVE_PENDING_SHA_WAIT no duplicate submission")
        return 0
    if ledger.get("sha256") == sha:
        print("KAGGLE_LIVE_CURRENT_SHA_CONFIRMED no duplicate submission")
        return 0
    if any(any(state in str(r.get("status", "")) for state in ACTIVE_STATES) for r in rows):
        print("KAGGLE_LIVE_ACTIVE_SUBMISSION_WAIT no overlapping submission; no simulator fallback")
        return 0

    remaining = failure_backoff_remaining(ledger, sha, args.failure_backoff_seconds)
    if remaining > 0:
        print(f"KAGGLE_LIVE_SUBMISSION_BACKOFF sha={sha[:12]} remaining_seconds={remaining}; no repeated submit")
        return 0

    print("KAGGLE_LIVE_PREDECESSOR_COMPLETE new SHA eligible for guarded live submission")
    print("KAGGLE_LIVE_SUBMISSION_READY")
    p = safe_run(["kaggle", "competitions", "submit", "-c", COMPETITION, "-f", str(main_path), "-m", desc])
    if p.returncode != 0:
        record_failure(ledger_path, sha, desc, p.returncode, args.failure_backoff_seconds)
        print(f"KAGGLE_LIVE_SUBMISSION_COMMAND_FAILED code={p.returncode}; backoff={args.failure_backoff_seconds}s; platform quota/validation respected")
        return 0

    ledger = json.loads(ledger_path.read_text())
    clear_failure(ledger)
    ledger.update({
        "pending_submit_sha": sha,
        "pending_submit_at": stamp(),
        "pending_description": desc,
        "status": "submitted_pending_visibility",
        "latest_sha256": sha,
        "latest_description": desc,
    })
    atomic_json(ledger_path, ledger)
    print("KAGGLE_LIVE_SUBMISSION_SENT")

    if args.visibility_wait_seconds > 0:
        time.sleep(args.visibility_wait_seconds)
    rows = list_submissions(out / "kaggle-after.txt")
    if rows is None:
        return 0
    _, current, _ = update_score_state(ledger_path, rows, desc, sha, summary_path)
    if current:
        mark_visible(ledger_path, current, sha, desc)
        print("KAGGLE_LIVE_SUBMISSION_VISIBLE")
    else:
        print("KAGGLE_LIVE_SUBMISSION_SENT_NOT_VISIBLE_YET pending only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
