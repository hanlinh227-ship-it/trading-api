#!/usr/bin/env python3
import glob
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

# Cross-platform execution bridge. Linux/Wine may still be used for diagnostics,
# while LIVE The5ers execution is intended to run on a native Windows MT5 host.
APP_HOME = pathlib.Path(os.environ.get('MT5_APP_HOME') or ('C:/Trading/MT5Forex' if os.name == 'nt' else '/var/lib/trading/mt5-forex'))
_default_install = APP_HOME / ('terminal-data' if os.name == 'nt' else 'wine/drive_c/MT5Forex')
INSTALL_DIR = pathlib.Path(os.environ.get('MT5_INSTALL_DIR', str(_default_install)))
BRIDGE_DIR = pathlib.Path(os.environ.get('MT5_BRIDGE_DIR') or (INSTALL_DIR / 'MQL5' / 'Files' / 'FOREX_BRIDGE'))
HEALTH_FILE = pathlib.Path(os.environ.get('MT5_BRIDGE_HEALTH_FILE') or (APP_HOME / 'bridge-health.json'))
HUB = (os.environ.get('MT5_HUB_URL') or 'https://trading-v77-scanner.hanlinh227.workers.dev').rstrip('/')
TOKEN = os.environ.get('MT5_BRIDGE_TOKEN', '')
PULSE = BRIDGE_DIR / 'pulse.json'
DECISION = BRIDGE_DIR / 'decision.json'
PULSE_REFRESH_SECONDS = 5.0
AUTH_MARKER = pathlib.Path(os.environ.get('MT5_AUTH_MARKER') or (APP_HOME / 'broker-authenticated.marker'))


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
        'pulsePath': str(PULSE),
        'tokenConfigured': bool(TOKEN),
        'platform': 'WINDOWS_NATIVE' if os.name == 'nt' else 'LINUX_WINE',
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
            'User-Agent': 'trading-mt5-sidecar/2.0',
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = resp.read()
        return resp.status, data


def read_json_bytes(path: pathlib.Path):
    raw = path.read_bytes()
    if not raw:
        raise ValueError(f'{path.name} is empty')
    parsed = json.loads(raw.decode('utf-8'))
    return raw, parsed


def pulse_signature(path: pathlib.Path, raw: bytes):
    st = path.stat()
    return (st.st_mtime_ns, st.st_size, hashlib.sha256(raw).hexdigest())


def persist_auth_marker(pulse_obj):
    # Broker session persistence (fix 2026-08-27): previously nothing created
    # the auth marker until full end-to-end readiness verification, so every
    # service restart re-entered BOOTSTRAP_AUTH forever. The EA's pulse is
    # ground truth for a live broker session: once mt5.connected is true the
    # session exists inside the persistent Wine prefix and the next launch can
    # use PERSISTENT_SESSION mode. Marker is created once; never deleted here.
    try:
        if AUTH_MARKER.exists():
            return
        mt5 = pulse_obj.get('mt5') if isinstance(pulse_obj.get('mt5'), dict) else {}
        if mt5.get('connected') is True:
            AUTH_MARKER.parent.mkdir(parents=True, exist_ok=True)
            tid = str(pulse_obj.get('terminalId') or '')
            AUTH_MARKER.write_text(
                'source=sidecar-pulse\nterminalId=%s\nverified_at=%s\n' % (tid, now_iso()),
                encoding='utf-8')
            try:
                os.chmod(AUTH_MARKER, 0o600)
            except OSError:
                pass
    except OSError:
        pass


def main():
    if not TOKEN:
        write_health(ok=False, state='CONFIG_ERROR', error='MT5_BRIDGE_TOKEN_MISSING')
        return 12

    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    HEALTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    last_pulse_sig = None
    last_forward_monotonic = 0.0
    last_success = None
    last_error = None
    write_health(ok=True, state='WAITING_FOR_PULSE', pulseExists=PULSE.exists())

    while True:
        did_work = False
        try:
            if PULSE.exists():
                body, pulse_obj = read_json_bytes(PULSE)
                sig = pulse_signature(PULSE, body)
                now_mono = time.monotonic()
                refresh_due = (now_mono - last_forward_monotonic) >= PULSE_REFRESH_SECONDS
                if sig != last_pulse_sig or refresh_due:
                    write_health(ok=True, state='PULSE_SEEN', pulseExists=True,
                                 terminalId=str(pulse_obj.get('terminalId') or ''), lastSuccessAt=last_success)
                    code, response = post('/forex/mt5/pulse', body)
                    if not (200 <= code < 300):
                        raise RuntimeError(f'PULSE_HTTP_{code}')
                    decision_text = response.decode('utf-8')
                    json.loads(decision_text)
                    atomic_write(DECISION, decision_text)
                    persist_auth_marker(pulse_obj)
                    last_pulse_sig = sig
                    last_forward_monotonic = now_mono
                    last_success = now_iso()
                    last_error = None
                    did_work = True
                    write_health(ok=True, state='PULSE_FORWARDED', pulseExists=True,
                                 terminalId=str(pulse_obj.get('terminalId') or ''),
                                 lastPulseAt=last_success, lastSuccessAt=last_success, lastHttpStatus=code)
            else:
                write_health(ok=True, state='WAITING_FOR_PULSE', pulseExists=False,
                             lastSuccessAt=last_success, error=last_error)

            for ack_name in sorted(glob.glob(str(BRIDGE_DIR / 'ack_*.json'))):
                ack = pathlib.Path(ack_name)
                try:
                    body, _ = read_json_bytes(ack)
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

        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode('utf-8', 'replace')[:300]
            except Exception:
                detail = ''
            last_error = f'HTTPError:{exc.code}:{detail}'[:500]
            write_health(ok=False, state='RETRYING', pulseExists=PULSE.exists(), error=last_error, lastSuccessAt=last_success)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError, OSError, ValueError) as exc:
            last_error = f'{type(exc).__name__}:{exc}'[:500]
            write_health(ok=False, state='RETRYING', pulseExists=PULSE.exists(), error=last_error, lastSuccessAt=last_success)
        except Exception as exc:
            last_error = f'UNEXPECTED:{type(exc).__name__}:{exc}'[:500]
            write_health(ok=False, state='RETRYING', pulseExists=PULSE.exists(), error=last_error, lastSuccessAt=last_success)

        time.sleep(0.25 if did_work else 0.5)


if __name__ == '__main__':
    sys.exit(main())
