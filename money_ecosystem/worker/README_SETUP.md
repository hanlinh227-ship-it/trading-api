# Curious Beyond Windows Worker — One-Time Setup

This worker is optional local media execution for the AI Money Ecosystem. It does not replace GitHub Brain authority and it does not accept arbitrary shell commands.

## Security model

- Allowed job types only: `IMAGE_RENDER`, `VIDEO_RENDER`, `VOICE_RENDER`, `FINAL_RENDER`, `MEDIA_PROBE`.
- Every job must carry a valid `HMAC-SHA256` signature.
- Job arguments containing arbitrary shell fields are rejected.
- File paths must stay under the worker workspace.
- Render job types remain fail-closed until their dedicated adapters are separately verified.
- Paid APIs, cloud GPU, auto-purchase, and credit spending are not enabled by this worker.
- The local pairing secret is stored outside the Git repository and must never be pasted into ChatGPT or committed.

## One-time Windows pairing

Prerequisites already expected on the machine:

- Git
- Python 3.11 virtual environment at `C:\AI\CuriousBeyond\venv`
- FFmpeg
- Whisper
- Kokoro
- ComfyUI Desktop

Run the setup script from the feature branch. It clones the repository to `C:\AI\CuriousBeyond\repo`, creates a random local pairing secret at `C:\AI\CuriousBeyond\worker_secret.txt`, and writes `C:\AI\CuriousBeyond\start_worker.ps1`.

After setup, create the GitHub Actions repository secret named exactly:

`CURIOUS_WORKER_HMAC_KEY`

Its value must be the exact contents of `C:\AI\CuriousBeyond\worker_secret.txt`.

Do not place that value in source code, issues, chat, screenshots, or commits.

## Queue flow

1. ChatGPT/GitHub creates `worker_jobs/requests/current.json` on the approved feature branch.
2. GitHub Actions validates the request and signs it using `CURIOUS_WORKER_HMAC_KEY`.
3. The signed envelope is written to `worker_jobs/signed/current.json`.
4. The Windows worker pulls the branch, verifies the signature locally, and executes only an allowlisted job.
5. The worker writes `worker_jobs/results/<job_id>.json` and pushes only the results directory.
6. ChatGPT can then read the result through the GitHub connector.

This is outbound-only from the Windows machine. No inbound port, remote desktop service, arbitrary command endpoint, or exposed local web server is required.

## Start the worker

```powershell
powershell -ExecutionPolicy Bypass -File "C:\AI\CuriousBeyond\start_worker.ps1"
```

A healthy startup prints:

```text
Curious Beyond Worker ONLINE
Repo: C:\AI\CuriousBeyond\repo
Branch: ai-money-ecosystem-autopilot-v1
```

The first production-safe job should be `MEDIA_PROBE`. Render jobs remain blocked until their individual adapters pass tests and verification.
