#!/usr/bin/env python3
"""Rootless, public-only Bybit REST bridge for Cloudflare VPC research traffic."""
from __future__ import annotations

import json
import os
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bybit_public_proxy import bybit_public_proxy

SECRET = (os.environ.get('BYBIT_PUBLIC_BRIDGE_SECRET') or '').strip()
SOURCE_REVISION = (os.environ.get('BRIDGE_SOURCE_REVISION') or '').strip()
DEFAULT_HOST = os.environ.get('BYBIT_PUBLIC_BRIDGE_HOST', '127.0.0.1')
DEFAULT_PORT = int(os.environ.get('BYBIT_PUBLIC_BRIDGE_PORT', '8789'))
PUBLIC_PREFIX = '/bybit/public'


def status_payload():
    return {
        'ok': True,
        'service': 'BYBIT_PUBLIC_RESEARCH_BRIDGE',
        'sourceRevision': SOURCE_REVISION,
        'publicProxy': True,
        'privateProxy': False,
        'eventDriver': False,
        'transport': 'USER_CRON_WATCHDOG',
        'timestamp': int(time.time() * 1000),
    }


class Handler(BaseHTTPRequestHandler):
    def sendj(self, code, obj):
        body = json.dumps(obj, separators=(',', ':')).encode()
        self.send_response(code)
        self.send_header('content-type', 'application/json')
        self.send_header('cache-control', 'no-store')
        self.send_header('content-length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def authorized(self):
        return bool(SECRET) and self.headers.get('authorization', '') == 'Bearer ' + SECRET

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/health':
            return self.sendj(200, status_payload())
        if parsed.path == PUBLIC_PREFIX + '/meta':
            if not self.authorized():
                return self.sendj(401, {'ok': False, 'error': 'UNAUTHORIZED'})
            return self.sendj(200, status_payload())
        if parsed.path.startswith(PUBLIC_PREFIX):
            if not self.authorized():
                return self.sendj(401, {'ok': False, 'error': 'UNAUTHORIZED'})
            target_path = parsed.path[len(PUBLIC_PREFIX):]
            status, payload = bybit_public_proxy(target_path, parsed.query)
            return self.sendj(status, payload)
        return self.sendj(404, {'ok': False, 'error': 'NOT_FOUND'})

    def do_POST(self):
        return self.sendj(405, {'ok': False, 'error': 'METHOD_NOT_ALLOWED'})

    def log_message(self, *_):
        pass


def create_server(host=DEFAULT_HOST, port=DEFAULT_PORT):
    if not SECRET:
        raise RuntimeError('BYBIT_PUBLIC_BRIDGE_SECRET_REQUIRED')
    return ThreadingHTTPServer((host, int(port)), Handler)


def main():
    create_server().serve_forever()


if __name__ == '__main__':
    main()
