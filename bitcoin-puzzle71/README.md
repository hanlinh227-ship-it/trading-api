# Bitcoin Puzzle #71 Solver

This component is deliberately restricted to the public Bitcoin Puzzle #71 challenge.

- Target address: `1PWo3JeB9jrGwfHDNpdGK54CRas7fsVzXU`
- HASH160: `f6f5431d25bbf7b12e8add9af5e3475c44a0a5b8`
- Allowed key range: `0x400000000000000000` through `0x7FFFFFFFFFFFFFFFFF`
- Compression: compressed public keys only

## Safety boundary

The installer and runtime wrapper hard-code the public challenge target and range. It is not a generic wallet scanner. A discovered key is written only to `/var/lib/bitcoin-puzzle71/` on the VPS with restrictive local permissions. It is never committed to GitHub and the workflow status output never prints it.

## Engine selection

At deployment time the installer detects hardware:

1. NVIDIA GPU + working `nvcc`: attempt a pinned CUDA BitCrack build and use checkpointed GPU scanning.
2. Otherwise: build a pinned KeyHunt revision and run its address-mode CPU scanner across the 71-bit challenge range using all available CPU threads.
3. If CUDA compilation fails, deployment automatically falls back to the CPU engine instead of stopping the solver.

## Control through GitHub

`control.txt` accepts `start`, `restart`, `stop`, or `status`. A push to `main` that changes the control file triggers the self-hosted `trading-vps` runner.

Runtime status is written to `runtime-status.txt`. It contains only engine/service/hardware/search-rate information. It never includes the private key.

## Reward handling

The solver intentionally does **not** broadcast a Bitcoin transaction. If a valid key is found, workers stop and the result remains only on the VPS. Claiming the public puzzle reward should be performed separately from a trusted wallet/offline signing workflow after verifying that the derived address exactly matches the challenge target.
