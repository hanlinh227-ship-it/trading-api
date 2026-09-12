#!/usr/bin/env python3
import importlib.util
import json
import pathlib
import unittest
from unittest.mock import patch

MODULE_PATH = pathlib.Path(__file__).with_name('bybit_public_proxy.py')
spec = importlib.util.spec_from_file_location('bybit_public_proxy_under_test', MODULE_PATH)
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, _limit=-1):
        return json.dumps(self.payload).encode()


class PublicBybitProxyTests(unittest.TestCase):
    def test_allows_unsigned_market_get_on_fixed_bybit_host(self):
        seen = {}
        def fake_urlopen(req, timeout=0):
            seen['url'] = req.full_url
            seen['headers'] = {k.lower(): v for k, v in req.headers.items()}
            seen['method'] = req.get_method()
            return FakeResponse({'retCode': 0, 'time': 123, 'result': {'list': []}})
        with patch.object(proxy.urllib.request, 'urlopen', fake_urlopen):
            status, payload = proxy.bybit_public_proxy('/v5/market/tickers', 'category=linear&symbol=BTCUSDT')
        self.assertEqual(status, 200)
        self.assertEqual(payload['retCode'], 0)
        self.assertEqual(seen['method'], 'GET')
        self.assertTrue(seen['url'].startswith('https://api.bybit.com/v5/market/tickers?'))
        self.assertNotIn('x-bapi-api-key', seen['headers'])
        self.assertNotIn('x-bapi-sign', seen['headers'])

    def test_rejects_non_market_paths(self):
        for path in ['/v5/order/realtime', '/v5/position/list', '/v5/account/wallet-balance']:
            status, payload = proxy.bybit_public_proxy(path, 'category=linear')
            self.assertEqual(status, 403)
            self.assertEqual(payload['error'], 'BYBIT_PUBLIC_PATH_NOT_ALLOWED')

    def test_rejects_arbitrary_url_or_host(self):
        status, payload = proxy.bybit_public_proxy('https://evil.example/v5/market/tickers', 'category=linear')
        self.assertEqual(status, 403)
        self.assertEqual(payload['error'], 'BYBIT_PUBLIC_PATH_NOT_ALLOWED')

    def test_rejects_malformed_or_ambiguous_query(self):
        bad_queries = [
            'symbol=BTCUSDT%0d%0aX-Evil%3A1',
            'symbol=BTCUSDT&symbol=ETHUSDT',
            'category=linear&bad%20key=x',
        ]
        for query in bad_queries:
            status, payload = proxy.bybit_public_proxy('/v5/market/tickers', query)
            self.assertEqual(status, 400)
            self.assertEqual(payload['error'], 'BYBIT_PUBLIC_QUERY_INVALID')


if __name__ == '__main__':
    unittest.main()
