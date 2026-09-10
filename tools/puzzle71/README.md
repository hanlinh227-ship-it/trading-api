# Bitcoin Puzzle #71 — isolated bounded worker

This directory is intentionally restricted to the public Bitcoin Puzzle #71 challenge.
It is not a general wallet scanner.

## Fixed challenge

- Puzzle: #71
- Address: `1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU`
- Published key range: `0x400000000000000000` .. `0x7fffffffffffffffff`
- Address type searched: compressed legacy P2PKH

The worker has no CLI option for changing the target or keyspace. That guardrail is deliberate.

## Architecture

1. `keyhunt` is pinned and built as the CPU search engine.
2. `worker.py` partitions the 2^70-key interval into 2^26-key shards.
3. Shards are visited using a bijective affine permutation over 2^44 shard IDs, so the worker gets broad coverage without internally repeating completed shards.
4. A checkpoint is written only after a complete shard. If the host dies mid-shard, at most that shard is repeated.
5. On a hit, raw engine output is moved to `$HOME/puzzle71/runtime/FOUND.secret` with mode 0600 and scanning stops. The key is never printed by the wrapper or uploaded to GitHub.

## VPS policy

The current self-hosted VPS has no CUDA GPU and also runs trading services. Deployment therefore caps the puzzle worker at **1 CPU thread** and launches it with `nice -n 19` so trading workloads retain priority.

## Runtime files on VPS

- `$HOME/puzzle71/runtime/state-w0.json` — completed-shard checkpoint
- `$HOME/puzzle71/runtime/status-w0.json` — current shard/status; no private key
- `$HOME/puzzle71/runtime/worker-w0.log` — sanitized lifecycle log
- `$HOME/puzzle71/runtime/FOUND.flag` — present only if a hit exists
- `$HOME/puzzle71/runtime/FOUND.secret` — sensitive recovered material, local only, mode 0600

## Claim boundary

The solver intentionally does **not** auto-broadcast a Bitcoin transaction. If a hit occurs, it stops and secures the result locally. Claiming should be performed from a controlled wallet environment because exposing a recovered key in logs, CI artifacts, or an online transaction-construction flow can lose the reward.
