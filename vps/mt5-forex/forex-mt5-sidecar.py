#!/usr/bin/env python3
import glob
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

APP_HOME = pathlib.Path('/var/lib/trading/mt5-forex')
INSTALL_DIR = pathlib.Path(os.environ.get('MT5_INSTALL_DIR', str(APP_HOME / 'wine/drive_c/MT5Forex')))
BRIDGE_DIR = INSTALL_DIR / 'MQL5' / 'Files' / 'FOREX_BRIDGE'
HEALTH_FILE = APP_HOME / 'bridge-health.json'
HUB = (os.environ.get('MT5_HUB_URL') or 'https://trading-v77-scanner.hanlinh227.workers.dev').rstrip('/')
TOKEN = os.environ.get('MT5_BRIDGE_TOKEN', '')
PULSE = BRIDGE_DIR / 'pulse.json'
DECISION = BRIDGE_DIR / 'decision.json'


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def atomic_write(path: pathlib.Path, payload: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(payload, encoding='utf-8')
    os.replace(tmp, path)


def write_health(**extra):
    base = {
        'ok': extra.get('ok', False),
        'updatedAt': now_iso(),
        'hub': HUB,
        'bridgeDir': str(BRIDGE_DIR),
        'tokenConfigured': bool(TOKEN),
    }
    base.update(extra)
    atomic_write(HEALTH_FILE, json.dumps(base, separators=(',', ':')))


def post(path: str, body: bytes):
    req = urllib.request.Request(
        HUB + path,
        data=body,
        method='POST',
        headers={
            'Authorization': 'Bearer ' + TOKEN,
            'Content-Type': 'application/json',
            'User-Agent': 'trading-mt5-sidecar/1.0',
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
        return resp.status, data


def valid_json_bytes(path: pathlib.Path):
    raw = path.read_bytes()
    json.loads(raw.decode('utf-8'))
    return raw


def main():
    if not TOKEN:
        write_health(ok=False, error='MT5_BRIDGE_TOKEN_MISSING')
        return 12
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    last_pulse_sig = None
    last_success = None
    last_error = None
    write_health(ok=True, state='STARTED')

    while True:
        did_work = False
        try:
            if PULSE.exists():
                st = PULSE.stat()
                sig = (st.st_mtime_ns, st.st_size)
                if sig != last_pulse_sig:
                    body = valid_json_bytes(PULSE)
                    code, response = post('/forex/mt5/pulse', body)
                    if 200 <= code < 300:
                        json.loads(response.decode('utf-8'))
                        atomic_write(DECISION, response.decode('utf-8'))
                        last_pulse_sig = sig
                        last_success = now_iso()
                        last_error = None
                        did_work = True
                        write_health(ok=True, state='PULSE_FORWARDED', lastPulseAt=last_success, lastHttpStatus=code)

            for ack_name in sorted(glob.glob(str(BRIDGE_DIR / 'ack_*.json'))):
                ack = pathlib.Path(ack_name)
                try:
                    body = valid_json_bytes(ack)
                    code, _ = post('/forex/mt5/ack', body)
                    if 200 <= code < 300:
                        ack.unlink(missing_ok=True)
                        last_success = now_iso()
                        last_error = None
                        did_work = True
                        write_health(ok=True, state='ACK_FORWARDED', lastSuccessAt=last_success, lastHttpStatus=code)
                except Exception as exc:
                    last_error = f'ACK:{type(exc).__name__}:{exc}'[:500]
                    write_health(ok=False, state='ACK_ERROR', error=last_error, lastSuccessAt=last_success)
                    break
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            last_error = f'{type(exc).__name__}:{exc}'[:500]
            write_health(ok=False, state='RETRYING', error=last_error, lastSuccessAt=last_success)
        except Exception as exc:
            last_error = f'UNEXPECTED:{type(exc).__name__}:{exc}'[:500]
            write_health(ok=False, state='RETRYING', error=last_error, lastSuccessAt=last_success)

        time.sleep(0.5 if did_work else 1.0)


if __name__ == '__main__':
    sys.exit(main())
