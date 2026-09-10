#!/usr/bin/env python3
"""Bounded worker for the public Bitcoin Puzzle #71 only.

Safety properties:
- Target and range are hard-coded to the published Puzzle #71 challenge.
- No arbitrary address/range CLI exists.
- Shards are visited through a bijective affine permutation, avoiding repeats.
- Checkpoint is committed only after a whole shard completes.
- A recovered key is never printed by this wrapper; raw hit output is moved to
  a mode-0600 local file and the worker stops.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

PUZZLE_ID = 71
TARGET = "1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU"
RANGE_START = int("400000000000000000", 16)
RANGE_END = int("7fffffffffffffffff", 16)
# 2^26 keys per shard: bounded restart loss, ~67 million keys.
SHARD_BITS = 26
SHARD_SIZE = 1 << SHARD_BITS
RANGE_SIZE = RANGE_END - RANGE_START + 1
SHARD_COUNT = RANGE_SIZE // SHARD_SIZE  # 2^44
# Odd A => multiplication is invertible mod 2^44, therefore a permutation.
PERM_A = 0x5DEECE66D
PERM_B = 0x123456789AB

STOP = False
CURRENT_CHILD: subprocess.Popen[str] | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def on_signal(signum, _frame) -> None:
    global STOP, CURRENT_CHILD
    STOP = True
    if CURRENT_CHILD and CURRENT_CHILD.poll() is None:
        try:
            CURRENT_CHILD.send_signal(signal.SIGINT)
        except ProcessLookupError:
            pass


def load_counter(state_file: Path) -> int:
    if not state_file.exists():
        return 0
    try:
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return int(data.get("next_counter", 0))
    except Exception:
        return 0


def append_log(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {line}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Public Bitcoin Puzzle #71 bounded worker")
    parser.add_argument("--engine", required=True, help="Path to pinned keyhunt binary")
    parser.add_argument("--runtime", required=True, help="Private runtime/checkpoint directory")
    parser.add_argument("--worker-id", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--threads", type=int, default=1)
    args = parser.parse_args()

    if args.workers < 1 or not (0 <= args.worker_id < args.workers):
        raise SystemExit("invalid worker partition")
    if args.threads != 1:
        # This VPS also hosts trading workloads; keep puzzle work deliberately low-impact.
        raise SystemExit("this deployment is capped at exactly 1 CPU thread")

    engine = Path(args.engine).resolve()
    if not engine.is_file() or not os.access(engine, os.X_OK):
        raise SystemExit(f"engine not executable: {engine}")

    runtime = Path(args.runtime).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    os.chmod(runtime, 0o700)
    target_file = runtime / "target.txt"
    target_file.write_text(TARGET + "\n", encoding="ascii")
    os.chmod(target_file, 0o600)

    state_file = runtime / f"state-w{args.worker_id}.json"
    status_file = runtime / f"status-w{args.worker_id}.json"
    event_log = runtime / f"worker-w{args.worker_id}.log"
    found_flag = runtime / "FOUND.flag"
    found_secret = runtime / "FOUND.secret"
    pid_file = runtime / f"worker-w{args.worker_id}.pid"
    pid_file.write_text(str(os.getpid()) + "\n", encoding="ascii")

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, on_signal)

    counter = load_counter(state_file)
    append_log(event_log, f"START puzzle={PUZZLE_ID} worker={args.worker_id}/{args.workers} counter={counter}")

    while not STOP:
        if found_flag.exists():
            append_log(event_log, "STOP found-flag-present")
            break

        logical_n = args.worker_id + counter * args.workers
        if logical_n >= SHARD_COUNT:
            append_log(event_log, "DONE assigned-keyspace-exhausted")
            atomic_json(status_file, {"state": "DONE", "puzzle": PUZZLE_ID, "updated_at": utc_now()})
            return 0

        shard_idx = (PERM_A * logical_n + PERM_B) % SHARD_COUNT
        start = RANGE_START + shard_idx * SHARD_SIZE
        end = min(start + SHARD_SIZE - 1, RANGE_END)
        start_hex = f"{start:x}"
        end_hex = f"{end:x}"

        atomic_json(status_file, {
            "state": "SCANNING",
            "puzzle": PUZZLE_ID,
            "target": TARGET,
            "published_range": [f"{RANGE_START:x}", f"{RANGE_END:x}"],
            "worker_id": args.worker_id,
            "workers": args.workers,
            "threads": args.threads,
            "counter": counter,
            "shard_index": shard_idx,
            "shard_range": [start_hex, end_hex],
            "shard_keys": end - start + 1,
            "updated_at": utc_now(),
        })
        append_log(event_log, f"SCAN counter={counter} shard={shard_idx} range={start_hex}:{end_hex}")

        fd, raw_name = tempfile.mkstemp(prefix="p71-", suffix=".raw", dir=str(runtime))
        os.close(fd)
        raw_path = Path(raw_name)
        os.chmod(raw_path, 0o600)
        cmd = [
            str(engine), "-m", "address", "-f", str(target_file),
            "-r", f"{start_hex}:{end_hex}", "-l", "compress",
            "-t", "1", "-q", "-s", "15",
        ]

        global CURRENT_CHILD
        with raw_path.open("w", encoding="utf-8", errors="replace") as raw:
            CURRENT_CHILD = subprocess.Popen(
                cmd, stdout=raw, stderr=subprocess.STDOUT, text=True,
                cwd=str(engine.parent), start_new_session=True,
            )
            rc = CURRENT_CHILD.wait()
        CURRENT_CHILD = None

        raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
        hit = "Hit! Private Key:" in raw_text
        if hit:
            # Keep all sensitive hit material only on the VPS, mode 0600. Never echo it.
            os.replace(raw_path, found_secret)
            os.chmod(found_secret, 0o600)
            found_flag.write_text(f"FOUND puzzle={PUZZLE_ID} at={utc_now()}\n", encoding="ascii")
            os.chmod(found_flag, 0o600)
            atomic_json(status_file, {
                "state": "FOUND_REDACTED",
                "puzzle": PUZZLE_ID,
                "worker_id": args.worker_id,
                "counter": counter,
                "shard_index": shard_idx,
                "updated_at": utc_now(),
                "secret_path": str(found_secret),
            })
            append_log(event_log, "FOUND_REDACTED worker-stopped secret-kept-local")
            return 0

        raw_path.unlink(missing_ok=True)
        if STOP:
            append_log(event_log, f"INTERRUPTED counter={counter}; shard will be retried")
            break
        if rc != 0:
            append_log(event_log, f"ENGINE_ERROR rc={rc} counter={counter}; retry-in-30s")
            atomic_json(status_file, {
                "state": "ENGINE_ERROR", "puzzle": PUZZLE_ID,
                "counter": counter, "return_code": rc, "updated_at": utc_now(),
            })
            time.sleep(30)
            continue

        counter += 1
        atomic_json(state_file, {
            "puzzle": PUZZLE_ID,
            "worker_id": args.worker_id,
            "workers": args.workers,
            "next_counter": counter,
            "last_completed_shard": shard_idx,
            "last_completed_range": [start_hex, end_hex],
            "updated_at": utc_now(),
        })
        append_log(event_log, f"COMPLETE shard={shard_idx} next_counter={counter}")

    atomic_json(status_file, {
        "state": "STOPPED", "puzzle": PUZZLE_ID,
        "worker_id": args.worker_id, "counter": counter, "updated_at": utc_now(),
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
