# Curious Beyond Worker Queue

This directory is transport state for the optional Windows media worker.

- `requests/current.json`: current unsigned request created through approved GitHub writes.
- `signed/current.json`: GitHub Actions validated + HMAC-signed envelope.
- `results/<job_id>.json`: result returned by the paired Windows worker.

Never commit pairing secrets, credentials, OAuth tokens, arbitrary shell commands, or unrestricted executable payloads here.
