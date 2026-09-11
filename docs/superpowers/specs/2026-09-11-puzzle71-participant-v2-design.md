# Puzzle71 Participant V2 Design

## Scope
Build a bounded participant system for the public Bitcoin Puzzle #71 challenge only.

Hard scope is immutable:
- Target address: `1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU`
- Allowed private-key interval: `0x400000000000000000` through `0x7FFFFFFFFFFFFFFFFF`
- Compressed public keys only
- Never accept arbitrary wallet targets or arbitrary key ranges
- Never commit or print a discovered private key to GitHub logs

## Goals
1. Run continuously on the existing VPS/self-hosted GitHub runner.
2. Use all safe compute available on the VPS without duplicating searched work.
3. Prefer a verified NVIDIA/CUDA path when available; otherwise run CPU fallback.
4. Persist deterministic progress so restarts do not intentionally rescan completed chunks.
5. Verify any candidate private key locally by deriving the expected address before declaring FOUND.
6. Expose only non-sensitive runtime status through GitHub.

## Architecture
`public challenge authority -> hardware detector -> deterministic chunk allocator -> worker engine -> checkpoint registry -> candidate verifier -> FOUND stop gate -> offline claim handoff`

### Authority
Challenge constants are duplicated only in a dedicated immutable configuration file and validated before launch. Any mismatch aborts the participant.

### Chunk allocator
The keyspace is partitioned into deterministic non-overlapping chunks. Workers lease one chunk at a time. A chunk has states `pending`, `running`, `complete`, or `found`. The registry is local to the VPS and survives service restarts. A stale `running` lease may be reclaimed after the worker is confirmed dead.

### Engines
- NVIDIA + CUDA: use pinned BitCrack-compatible worker if the build and a smoke test pass.
- CPU fallback: use pinned KeyHunt-compatible worker.
- Worker count is derived from actual hardware. CPU default is all logical CPUs minus one reserve thread when more than two CPUs exist; it must never silently fall back to one thread on a multi-core host.

### Candidate verification
Any engine hit must be parsed into a candidate key, normalized, checked against the Puzzle #71 interval, used to derive a compressed public key/address locally, and compared exactly with the fixed target address. Only then may state become `FOUND`.

### Secret handling
A verified result is stored only in the VPS state directory with mode `0600`. GitHub workflow output and `runtime-status.txt` show only `FOUND=true/false` and never the key.

### Control
Existing `control.txt` semantics remain: `start`, `restart`, `stop`, `status`. GitHub Actions on the self-hosted `trading-vps` runner perform deployment/control operations.

### Runtime status
Status must report at minimum:
- participant version
- service state
- engine
- CPU thread count
- GPU count
- active chunk identifier/range fingerprint
- completed chunk count
- estimated searched-key count
- current search rate
- last heartbeat UTC
- `result=SEARCHING|FOUND|STOPPED|ERROR`

## Failure handling
- Build failure on CUDA falls back to CPU.
- Invalid challenge constants abort startup.
- Corrupt checkpoint registry is quarantined and the participant stops instead of guessing.
- Candidate verification failure is logged without revealing the candidate key and search continues.
- FOUND stops all workers before status publication.

## Testing
Tests must cover challenge-constant immutability, non-overlapping chunk allocation, restart/resume behavior, stale lease reclaim, candidate verification with known synthetic fixtures, secret redaction, CPU-thread selection, and status serialization.

## Deployment acceptance
Participant V2 is considered active only after:
1. tests/CI pass;
2. deployment workflow on the self-hosted runner succeeds;
3. `runtime-status.txt` produced after deployment reports the V2 version, `service=active`, a concrete engine, heartbeat freshness, and `result=SEARCHING` or `FOUND`.

## Non-goals
- No generic wallet scanning.
- No arbitrary target input.
- No automatic reward-spend transaction.
- No production trading changes.
