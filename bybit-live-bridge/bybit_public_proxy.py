#!/usr/bin/env python3
"""Unsigned, read-only Bybit public-market proxy helpers.

This module cannot reach account, position, order, or any arbitrary host/path.
It forwards GET requests only to fixed Bybit public REST bases and never adds
Bybit authentication/signature headers.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_BASES = ('https://api.bybit.com', 'https://api.bytick.com')
ALLOWED_BASES = frozenset(DEFAULT_BASES)
PATH_RE = re.compile(r'^/v5/market/[A-Za-z0-9-]{1,64}$')
KEY_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]{0,39}$')
MAX_QUERY_PAIRS = 24
MAX_QUERY_VALUE = 256
MAX_RESPONSE_BYTES = 2_000_000
USER_AGENT = 'github-brain-zero-local-public-bridge/1.0'


def _safe_query(query: str):
    try:
        pairs = urllib.parse.parse_qsl(query, keep_blank_values=True, strict_parsing=True) if query else []
    except ValueError:
        return None
    if len(pairs) > MAX_QUERY_PAIRS:
        return None
    seen = set()
    clean = []
    for key, value in pairs:
        if key in seen or not KEY_RE.fullmatch(key) or len(value) > MAX_QUERY_VALUE:
            return None
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in key + value):
            return None
        seen.add(key)
        clean.append((key, value))
    return urllib.parse.urlencode(clean)


def _decode_payload(raw: bytes):
    try:
        return json.loads(raw.decode(errors='strict'))
    except Exception:
        return None


def bybit_public_proxy(path: str, query: str = '', bases=DEFAULT_BASES):
    path = str(path or '')
    if not PATH_RE.fullmatch(path):
        return 403, {'ok': False, 'error': 'BYBIT_PUBLIC_PATH_NOT_ALLOWED'}
    safe_query = _safe_query(str(query or ''))
    if safe_query is None:
        return 400, {'ok': False, 'error': 'BYBIT_PUBLIC_QUERY_INVALID'}

    requested_bases = tuple(str(x).rstrip('/') for x in bases)
    if not requested_bases or any(base not in ALLOWED_BASES for base in requested_bases):
        return 403, {'ok': False, 'error': 'BYBIT_PUBLIC_BASE_NOT_ALLOWED'}

    last_status = 502
    last_payload = {'ok': False, 'error': 'BYBIT_PUBLIC_UPSTREAM_UNAVAILABLE'}
    for base in requested_bases:
        url = base + path + (('?' + safe_query) if safe_query else '')
        req = urllib.request.Request(
            url,
            method='GET',
            headers={'accept': 'application/json', 'user-agent': USER_AGENT},
        )
        try:
            with urllib.request.urlopen(req, timeout=12) as response:
                status = int(getattr(response, 'status', 200))
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            raw = exc.read(MAX_RESPONSE_BYTES + 1)
        except Exception as exc:
            last_status = 502
            last_payload = {'ok': False, 'error': 'BYBIT_PUBLIC_UPSTREAM_FETCH_FAILED', 'detail': str(exc)[:160]}
            continue

        if len(raw) > MAX_RESPONSE_BYTES:
            return 502, {'ok': False, 'error': 'BYBIT_PUBLIC_RESPONSE_TOO_LARGE'}
        payload = _decode_payload(raw)
        if payload is None:
            return 502, {'ok': False, 'error': 'BYBIT_PUBLIC_INVALID_JSON'}
        last_status, last_payload = status, payload
        if status not in (403, 429):
            return status, payload

    return last_status, last_payload
