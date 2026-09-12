#!/usr/bin/env python3
import importlib.util
import json
import os
import pathlib
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

os.environ['BYBIT_PUBLIC_BRIDGE_SECRET'] = 'public-test-secret'
os.environ['BRIDGE_SOURCE_REVISION'] = 'test-revision'

MODULE_PATH = pathlib.Path(__file__).with_name('bybit_public_daemon.py')
spec = importlib.util.spec_from_file_location('bybit_public_daemon_under_test', MODULE_PATH)
daemon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(daemon)


class PublicDaemonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = daemon.create_server('127.0.0.1', 0)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get(self, path, authorized=False):
        headers = {'accept': 'application/json'}
        if authorized:
            headers['authorization'] = 'Bearer public-test-secret'
        req = urllib.request.Request(f'http://127.0.0.1:{self.port}{path}', headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=2) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode())

    def test_health_is_local_readiness_only_and_reports_exact_revision(self):
        status, body = self.get('/health')
        self.assertEqual(status, 200)
        self.assertTrue(body['ok'])
        self.assertEqual(body['service'], 'BYBIT_PUBLIC_RESEARCH_BRIDGE')
        self.assertEqual(body['sourceRevision'], 'test-revision')
        self.assertTrue(body['publicProxy'])
        self.assertFalse(body['privateProxy'])
        self.assertFalse(body['eventDriver'])

    def test_meta_requires_dedicated_public_secret(self):
        status, body = self.get('/bybit/public/meta')
        self.assertEqual(status, 401)
        self.assertEqual(body['error'], 'UNAUTHORIZED')
        status, body = self.get('/bybit/public/meta', authorized=True)
        self.assertEqual(status, 200)
        self.assertEqual(body['sourceRevision'], 'test-revision')
        self.assertEqual(body['transport'], 'USER_CRON_WATCHDOG')

    def test_non_market_surface_is_rejected(self):
        status, body = self.get('/bybit/public/v5/order/realtime', authorized=True)
        self.assertEqual(status, 403)
        self.assertEqual(body['error'], 'BYBIT_PUBLIC_PATH_NOT_ALLOWED')

    def test_market_surface_delegates_to_unsigned_public_proxy(self):
        payload = {'retCode': 0, 'time': 123, 'result': {'list': []}}
        with patch.object(daemon, 'bybit_public_proxy', return_value=(200, payload)) as proxy:
            status, body = self.get('/bybit/public/v5/market/tickers?category=linear&symbol=BTCUSDT', authorized=True)
        self.assertEqual(status, 200)
        self.assertEqual(body, payload)
        proxy.assert_called_once_with('/v5/market/tickers', 'category=linear&symbol=BTCUSDT')


if __name__ == '__main__':
    unittest.main()
