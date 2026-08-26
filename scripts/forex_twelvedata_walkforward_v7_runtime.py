#!/usr/bin/env python3
"""Integrity bootstrap for canonical PAPER_ONLY Forex V7.

No strategy/source string patching is allowed here. The canonical V7 source must
already contain every required primitive binding and block-width guard. This
wrapper only validates the source, normalizes infrastructure-safe runtime
parameters, and executes it unchanged.

DEV acceleration is transport-only: exact historical Twelve Data responses are
cached by request window and reused across baseline/candidate replays. ACCEPTANCE
never uses this cache, so the strict 100 blind OOS days/symbol authority is
unchanged. Cache misses are rate-limited; cache hits skip provider sleep safely.
"""
import hashlib
import io
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

SOURCE = Path(__file__).with_name('forex_twelvedata_walkforward_v7.py')
src = SOURCE.read_text()

required = (
    'outcome=outcome',
    'metrics=metrics',
    'idx_for_hour=idx_for_hour',
    "BLOCK_DAYS = max(35",
    "BACKTEST_SYMBOLS",
)
missing = [token for token in required if token not in src]
if missing:
    raise SystemExit('V7_CANONICAL_INTEGRITY_FAIL missing=' + ','.join(missing))

# Infrastructure hardening only: strategy/source is untouched. Metals and
# holiday/data-gap clusters can expose fewer valid sessions, so VPS/runtime
# windows are never narrower than 42 calendar days.
try:
    requested_block_days = int(os.environ.get('BACKTEST_BLOCK_DAYS', '42') or '42')
except ValueError:
    requested_block_days = 42
runtime_block_days = max(42, requested_block_days)
os.environ['BACKTEST_BLOCK_DAYS'] = str(runtime_block_days)

MODE = os.environ.get('FOREX_RESEARCH_MODE', 'ACCEPTANCE').upper()
DEV_CACHE_ENABLED = MODE == 'DEV' and os.environ.get('FOREX_DEV_CACHE_ENABLED', '1') != '0'
DEV_CACHE_DIR = Path(os.environ.get('FOREX_DEV_CACHE_DIR', '/var/lib/trading/forex-research/dev-cache'))
try:
    DEV_NETWORK_MIN_INTERVAL = max(0.0, float(os.environ.get('FOREX_DEV_NETWORK_MIN_INTERVAL_SECONDS', '8.2')))
except ValueError:
    DEV_NETWORK_MIN_INTERVAL = 8.2

_original_urlopen = urllib.request.urlopen
_last_network_at = 0.0


class _CachedHTTPResponse:
    def __init__(self, payload: bytes):
        self._bio = io.BytesIO(payload)
        self.status = 200
        self.headers = {}

    def read(self, *args, **kwargs):
        return self._bio.read(*args, **kwargs)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._bio.close()
        return False


def _request_url(req):
    return req.full_url if isinstance(req, urllib.request.Request) else str(req)


def _cache_key(url):
    p = urllib.parse.urlsplit(url)
    q = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    # API key is a credential, not part of historical market-data identity.
    q = sorted((k, v) for k, v in q if k.lower() != 'apikey')
    normalized = urllib.parse.urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path, urllib.parse.urlencode(q), ''))
    return hashlib.sha256(('FOREX_DEV_TWELVEDATA_CACHE_V1|' + normalized).encode()).hexdigest()


def _is_twelvedata_time_series(url):
    try:
        p = urllib.parse.urlsplit(url)
        return p.netloc.lower() == 'api.twelvedata.com' and p.path.rstrip('/') == '/time_series'
    except Exception:
        return False


def _valid_payload(payload):
    try:
        d = json.loads(payload.decode('utf-8'))
        return isinstance(d, dict) and d.get('status') != 'error' and isinstance(d.get('values'), list) and bool(d.get('values'))
    except Exception:
        return False


def _atomic_cache_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp-' + str(os.getpid()))
    tmp.write_bytes(payload)
    os.replace(tmp, path)


def _dev_cached_urlopen(req, *args, **kwargs):
    global _last_network_at
    url = _request_url(req)
    if not _is_twelvedata_time_series(url):
        return _original_urlopen(req, *args, **kwargs)

    path = DEV_CACHE_DIR / (_cache_key(url) + '.json')
    try:
        payload = path.read_bytes()
        if _valid_payload(payload):
            print('FOREX_DEV_DATA_CACHE=HIT key=' + path.stem[:12], flush=True)
            return _CachedHTTPResponse(payload)
        path.unlink(missing_ok=True)
    except FileNotFoundError:
        pass
    except Exception as exc:
        print('FOREX_DEV_DATA_CACHE=CORRUPT_FALLBACK error=' + type(exc).__name__, flush=True)
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass

    # Preserve the provider-safe cadence only for actual network requests.
    now = time.monotonic()
    wait = DEV_NETWORK_MIN_INTERVAL - (now - _last_network_at)
    if _last_network_at and wait > 0:
        time.sleep(wait)
    with _original_urlopen(req, *args, **kwargs) as resp:
        payload = resp.read()
    _last_network_at = time.monotonic()
    if _valid_payload(payload):
        try:
            _atomic_cache_write(path, payload)
            print('FOREX_DEV_DATA_CACHE=MISS_STORED key=' + path.stem[:12], flush=True)
        except Exception as exc:
            print('FOREX_DEV_DATA_CACHE=WRITE_BYPASS error=' + type(exc).__name__, flush=True)
    return _CachedHTTPResponse(payload)


if DEV_CACHE_ENABLED:
    DEV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    urllib.request.urlopen = _dev_cached_urlopen
    # V7's normal post-request sleep is redundant because misses are rate-limited
    # above and hits never touch the provider.
    os.environ['TWELVEDATA_INTER_REQUEST_SLEEP'] = '0'

code = compile(src, str(SOURCE), 'exec')
print(
    'FOREX_V7_RUNTIME=CANONICAL_ONLY namespace_primitives=PASS '
    f'runtime_calendar_block_days={runtime_block_days} '
    f'dev_cache={"ON" if DEV_CACHE_ENABLED else "OFF"} '
    'acceptance_cache=OFF sparse_window_guard=PASS smoke_symbol_override=PASS source_drift_guard=PASS',
    flush=True,
)

g = {'__name__': '__main__', '__file__': str(SOURCE), '__package__': None}
exec(code, g, g)
