#!/usr/bin/env python3
"""Maintain Kaggriculture live score/champion telemetry without local matches.

LATEST is the newest source candidate. CURRENT_BEST is the strongest score visible in Kaggle's
current table. BEST_EVER is the historical high-water observed by the canonical live loop. These
are intentionally separate so a new submission never looks like a leaderboard reset.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path


def parse_rows(text: str):
    rows = []
    for raw in text.splitlines():
        parts = re.split(r"\s{2,}", raw.strip())
        if len(parts) < 5 or not parts[0].isdigit():
            continue
        score = None
        if len(parts) > 5 and parts[5]:
            try:
                score = float(parts[5])
            except ValueError:
                score = None
        rows.append({
            "ref": parts[0],
            "file": parts[1] if len(parts) > 1 else "",
            "date": parts[2] if len(parts) > 2 else "",
            "description": parts[3] if len(parts) > 3 else "",
            "status": parts[4] if len(parts) > 4 else "",
            "public_score": score,
        })
    return rows


def _as_float(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def update_ledger(ledger: dict, rows: list[dict], current_description: str, current_sha: str):
    current = next((r for r in rows if r["description"] == current_description), None)
    scored = [r for r in rows if r["public_score"] is not None and "COMPLETE" in r["status"]]
    current_best = max(scored, key=lambda r: r["public_score"], default=None)

    previous_scores = ledger.get("submission_scores") if isinstance(ledger.get("submission_scores"), dict) else {}
    score_changes = []
    next_scores = dict(previous_scores)
    for row in rows:
        prev = previous_scores.get(row["ref"], {}) if isinstance(previous_scores.get(row["ref"]), dict) else {}
        old = _as_float(prev.get("public_score"))
        new = row["public_score"]
        if new is not None and old is not None and abs(new - old) > 1e-9:
            score_changes.append({"ref": row["ref"], "previous": old, "new": new, "delta": new - old})
        next_scores[row["ref"]] = {
            "description": row["description"],
            "status": row["status"],
            "public_score": new,
            "observed_at": _now(),
        }
    if len(next_scores) > 80:
        keep_refs = [r["ref"] for r in rows[:80]]
        next_scores = {ref: next_scores[ref] for ref in keep_refs if ref in next_scores}
    ledger["submission_scores"] = next_scores

    if current_best:
        ledger["current_best_public_score"] = float(current_best["public_score"])
        ledger["current_best_submission_ref"] = current_best["ref"]
        ledger["current_best_description"] = current_best["description"]
        ledger["current_best_status"] = current_best["status"]

    old_best_ever = _as_float(ledger.get("best_ever_public_score"))
    if old_best_ever is None:
        old_best_ever = _as_float(ledger.get("high_water_public_score"))
    observed_now = float(current_best["public_score"]) if current_best else None
    if old_best_ever is None:
        best_ever = observed_now
    elif observed_now is None:
        best_ever = old_best_ever
    else:
        best_ever = max(old_best_ever, observed_now)
    ledger["best_ever_public_score"] = best_ever
    ledger["high_water_public_score"] = best_ever
    if observed_now is not None and (old_best_ever is None or observed_now > old_best_ever + 1e-9):
        ledger["best_ever_submission_ref"] = current_best["ref"]
        ledger["best_ever_description"] = current_best["description"]
        ledger["best_ever_observed_at"] = _now()

    result = "not_visible"
    latest_delta_current_best = None
    latest_delta_best_ever = None
    if current:
        ledger["latest_sha256"] = current_sha
        ledger["latest_description"] = current_description
        ledger["latest_submission_ref"] = current["ref"]
        ledger["latest_status"] = current["status"]
        ledger["last_observed_ref"] = current["ref"]
        ledger["last_observed_status"] = current["status"]

        if current["public_score"] is not None and "COMPLETE" in current["status"]:
            score = float(current["public_score"])
            ledger["latest_public_score"] = score
            ledger["last_public_score"] = score
            ledger["last_scored_ref"] = current["ref"]
            ledger["last_scored_description"] = current_description
            if observed_now is not None:
                latest_delta_current_best = score - observed_now
            if best_ever is not None:
                latest_delta_best_ever = score - best_ever
            if observed_now is None or score >= observed_now - 1e-9:
                result = "current_best" if latest_delta_current_best == 0 else "promoted_current_best"
                ledger["champion_sha256"] = current_sha
                ledger["champion_submission_ref"] = current["ref"]
                ledger["champion_description"] = current_description
                ledger["champion_public_score"] = score
                ledger["champion_status"] = current["status"]
            else:
                result = "regression"
        else:
            # A pending/new live candidate has no score yet. Never make it inherit the previous
            # candidate's score, which visually looked like Kaggle had reset or reassigned points.
            ledger["latest_public_score"] = current["public_score"]
            result = "pending"
    else:
        # The source candidate exists but Kaggle has not exposed a row yet. Clear only LATEST
        # display fields; CURRENT_BEST/BEST_EVER remain durable and must never be reset by this.
        ledger["latest_sha256"] = current_sha
        ledger["latest_description"] = current_description
        ledger["latest_submission_ref"] = ""
        ledger["latest_status"] = "NOT_VISIBLE"
        ledger["latest_public_score"] = None

    ledger["candidate_result"] = result
    ledger["latest_vs_current_best_delta"] = latest_delta_current_best
    ledger["latest_vs_best_ever_delta"] = latest_delta_best_ever

    history = ledger.get("latest_score_history") if isinstance(ledger.get("latest_score_history"), list) else []
    if current:
        observation = {
            "observed_at": _now(),
            "ref": current["ref"],
            "status": current["status"],
            "public_score": current["public_score"],
        }
        if not history or any(history[-1].get(k) != observation.get(k) for k in ("ref", "status", "public_score")):
            history.append(observation)
    ledger["latest_score_history"] = history[-30:]

    summary = {
        "candidate_result": result,
        "latest": {
            "sha256": ledger.get("latest_sha256", ""),
            "description": ledger.get("latest_description", ""),
            "submission_ref": ledger.get("latest_submission_ref", ""),
            "status": ledger.get("latest_status", ""),
            "public_score": ledger.get("latest_public_score"),
        },
        "current_best": {
            "description": ledger.get("current_best_description", ""),
            "submission_ref": ledger.get("current_best_submission_ref", ""),
            "status": ledger.get("current_best_status", ""),
            "public_score": ledger.get("current_best_public_score"),
        },
        "best_ever": {
            "description": ledger.get("best_ever_description", ""),
            "submission_ref": ledger.get("best_ever_submission_ref", ""),
            "public_score": ledger.get("best_ever_public_score"),
            "observed_at": ledger.get("best_ever_observed_at", ""),
        },
        "latest_vs_current_best_delta": latest_delta_current_best,
        "latest_vs_best_ever_delta": latest_delta_best_ever,
        "score_changes": score_changes,
    }
    return current, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--submissions", required=True)
    ap.add_argument("--current-description", required=True)
    ap.add_argument("--current-sha", required=True)
    ap.add_argument("--summary", required=True)
    args = ap.parse_args()

    ledger_path = Path(args.ledger)
    submissions_path = Path(args.submissions)
    summary_path = Path(args.summary)
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() and ledger_path.stat().st_size else {}
    rows = parse_rows(submissions_path.read_text(errors="replace"))
    _, summary = update_ledger(ledger, rows, args.current_description, args.current_sha)

    tmp = ledger_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n")
    tmp.replace(ledger_path)
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
    for change in summary["score_changes"]:
        print(f"LIVE_SUBMISSION_SCORE_CHANGE ref={change['ref']} previous={change['previous']} new={change['new']} delta={change['delta']}")
    if summary["candidate_result"] in ("current_best", "promoted_current_best"):
        latest = summary["latest"]
        print(f"PROMOTION_READY LIVE_CURRENT_CHAMPION ref={latest.get('submission_ref')} score={latest.get('public_score')}")
    elif summary["candidate_result"] == "regression":
        latest = summary["latest"]
        print(f"LIVE_SCORE_REGRESSION ref={latest.get('submission_ref')} score={latest.get('public_score')} current_best={summary['current_best'].get('public_score')} delta={summary.get('latest_vs_current_best_delta')}")
    elif summary["candidate_result"] == "pending":
        latest = summary["latest"]
        print(f"LIVE_SCORE_PENDING ref={latest.get('submission_ref')} status={latest.get('status')}")


if __name__ == "__main__":
    main()
