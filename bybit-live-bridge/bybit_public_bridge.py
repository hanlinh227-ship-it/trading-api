#!/usr/bin/env python3
"""Entrypoint that extends the existing bridge with unsigned public market GETs."""
from __future__ import annotations

import urllib.parse

import bybit_live_bridge as bridge
from bybit_public_proxy import bybit_public_proxy

PUBLIC_PREFIX = '/bybit/public'
_ORIGINAL_GET = bridge.Handler.do_GET


def _public_get(self):
    parsed = urllib.parse.urlparse(self.path)
    if parsed.path.startswith(PUBLIC_PREFIX):
        if not self.authorized():
            return self.sendj(401, {'ok': False, 'error': 'UNAUTHORIZED'})
        target_path = parsed.path[len(PUBLIC_PREFIX):]
        status, payload = bybit_public_proxy(target_path, parsed.query)
        return self.sendj(status, payload)
    return _ORIGINAL_GET(self)


bridge.Handler.do_GET = _public_get


if __name__ == '__main__':
    bridge.main()
