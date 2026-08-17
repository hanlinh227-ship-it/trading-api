#!/usr/bin/env python3
"""Canonical market routing and identity validation for the Trading repo.

This module is intentionally small and deterministic. It prevents ambiguous
provider tickers from being treated as the requested instrument.
"""
from __future__ import annotations

import math

FOREX_CCY = {
    "USD","EUR","GBP","JPY","CHF","CAD","AUD","NZD",
    "SGD","HKD","NOK","SEK","DKK","PLN","CZK","HUF",
    "MXN","ZAR","TRY","CNH","CNY",
}
CRYPTO_QUOTES = ("FDUSD","USDT","USDC","USD","BTC","ETH","BNB","EUR")

# Canonical aliases. min/max are deliberately broad sanity rails, not trading
# assumptions. They exist only to catch obvious identity collisions such as
# NAS100 resolving to an unrelated $19 security.
EXPLICIT = {
    # Spot metals. Keep these distinct from exact GC/SI futures.
    "XAUUSD": {"market_type": "metal", "provider_symbol": "XAU/USD", "min": 500, "max": 10000},
    "GOLD":   {"market_type": "metal", "provider_symbol": "XAU/USD", "min": 500, "max": 10000},
    "XAGUSD": {"market_type": "metal", "provider_symbol": "XAG/USD", "min": 5, "max": 500},
    "SILVER": {"market_type": "metal", "provider_symbol": "XAG/USD", "min": 5, "max": 500},
    "XPTUSD": {"market_type": "metal", "provider_symbol": "XPT/USD", "min": 100, "max": 10000},
    "XPDUSD": {"market_type": "metal", "provider_symbol": "XPD/USD", "min": 100, "max": 10000},

    # Cash indices. Provider must prove index identity; no futures proxy allowed.
    "NAS100": {"market_type": "index", "provider_symbol": "NDX", "min": 1000, "max": 100000},
    "NASDAQ100": {"market_type": "index", "provider_symbol": "NDX", "min": 1000, "max": 100000},
    "USTEC": {"market_type": "index", "provider_symbol": "NDX", "min": 1000, "max": 100000},
    "NDX": {"market_type": "index", "provider_symbol": "NDX", "min": 1000, "max": 100000},
    "SPX": {"market_type": "index", "provider_symbol": "SPX", "min": 500, "max": 20000},
    "SP500": {"market_type": "index", "provider_symbol": "SPX", "min": 500, "max": 20000},
    "US500": {"market_type": "index", "provider_symbol": "SPX", "min": 500, "max": 20000},
    "SPX500": {"market_type": "index", "provider_symbol": "SPX", "min": 500, "max": 20000},
    "IXIC": {"market_type": "index", "provider_symbol": "IXIC", "min": 1000, "max": 100000},
    "NASDAQ": {"market_type": "index", "provider_symbol": "IXIC", "min": 1000, "max": 100000},
    "DJI": {"market_type": "index", "provider_symbol": "DJI", "min": 5000, "max": 100000},
    "US30": {"market_type": "index", "provider_symbol": "DJI", "min": 5000, "max": 100000},
    "DOW": {"market_type": "index", "provider_symbol": "DJI", "min": 5000, "max": 100000},
    "N225": {"market_type": "index", "provider_symbol": "N225", "min": 5000, "max": 100000},
    "JP225": {"market_type": "index", "provider_symbol": "N225", "min": 5000, "max": 100000},
    "NIKKEI": {"market_type": "index", "provider_symbol": "N225", "min": 5000, "max": 100000},
    "NIKKEI225": {"market_type": "index", "provider_symbol": "N225", "min": 5000, "max": 100000},
    "DAX": {"market_type": "index", "provider_symbol": "DAX", "min": 5000, "max": 50000},
    "DEX": {"market_type": "index", "provider_symbol": "DAX", "min": 5000, "max": 50000},
    "DE40": {"market_type": "index", "provider_symbol": "DAX", "min": 5000, "max": 50000},
    "GER40": {"market_type": "index", "provider_symbol": "DAX", "min": 5000, "max": 50000},
    "FTSE": {"market_type": "index", "provider_symbol": "FTSE", "min": 3000, "max": 20000},
    "UK100": {"market_type": "index", "provider_symbol": "FTSE", "min": 3000, "max": 20000},
    "CAC": {"market_type": "index", "provider_symbol": "CAC", "min": 2000, "max": 15000},
    "FR40": {"market_type": "index", "provider_symbol": "CAC", "min": 2000, "max": 15000},
    "HSI": {"market_type": "index", "provider_symbol": "HSI", "min": 5000, "max": 50000},
    "VIX": {"market_type": "index", "provider_symbol": "VIX", "min": 5, "max": 200},
    "RUT": {"market_type": "index", "provider_symbol": "RUT", "min": 500, "max": 10000},

    # Exact futures are NOT interchangeable with Twelve commodity aggregates.
    # These rows make the requested identity explicit. If the provider cannot
    # return marketType=futures and the exact contract identity, it is blocked.
    "NQ":  {"market_type": "futures", "provider_symbol": "NQ",  "min": 1000, "max": 100000},
    "MNQ": {"market_type": "futures", "provider_symbol": "MNQ", "min": 1000, "max": 100000},
    "ES":  {"market_type": "futures", "provider_symbol": "ES",  "min": 500, "max": 20000},
    "MES": {"market_type": "futures", "provider_symbol": "MES", "min": 500, "max": 20000},
    "GC":  {"market_type": "futures", "provider_symbol": "GC",  "min": 500, "max": 10000},
    "SI":  {"market_type": "futures", "provider_symbol": "SI",  "min": 5, "max": 500},
    "CL":  {"market_type": "futures", "provider_symbol": "CL",  "min": 10, "max": 500},
}


def clean_symbol(value: str) -> str:
    s = str(value).upper().strip()
    for ch in "/-_ :":
        s = s.replace(ch, "")
    return s


def classify(value: str) -> dict:
    symbol = clean_symbol(value)
    if symbol in EXPLICIT:
        row = dict(EXPLICIT[symbol])
        row.update({"requested_symbol": symbol, "is_crypto": False})
        return row

    if len(symbol) == 6 and symbol.isalpha():
        base, quote = symbol[:3], symbol[3:]
        if base in FOREX_CCY and quote in FOREX_CCY and base != quote:
            return {
                "requested_symbol": symbol,
                "market_type": "forex",
                "provider_symbol": f"{base}/{quote}",
                "min": 0.0001,
                "max": 1000.0,
                "is_crypto": False,
            }

    for quote in CRYPTO_QUOTES:
        if symbol.endswith(quote):
            base = symbol[:-len(quote)]
            if 2 <= len(base) <= 20 and base.isalnum() and base != quote:
                return {
                    "requested_symbol": symbol,
                    "market_type": "crypto",
                    "provider_symbol": f"{base}/{quote}",
                    "min": 0.0,
                    "max": float("inf"),
                    "is_crypto": True,
                }

    return {
        "requested_symbol": symbol,
        "market_type": "unknown",
        "provider_symbol": None,
        "min": None,
        "max": None,
        "is_crypto": False,
    }


def _norm_type(value) -> str:
    s = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    aliases = {
        "physical currency": "forex",
        "currency": "forex",
        "forex": "forex",
        "digital currency": "crypto",
        "crypto": "crypto",
        "cryptocurrency": "crypto",
        "commodity": "commodity",
        "metal": "metal",
        "index": "index",
        "indices": "index",
        "futures": "futures",
        "future": "futures",
    }
    return aliases.get(s, s)


def _norm_provider_symbol(value) -> str:
    return str(value or "").upper().replace(" ", "")


def validate_identity(requested: str, payload: dict, m5_close=None) -> list[str]:
    spec = classify(requested)
    errors: list[str] = []

    if spec["market_type"] == "unknown":
        return ["UNKNOWN_REQUESTED_INSTRUMENT"]

    returned = clean_symbol(payload.get("symbol") or requested)
    if returned != spec["requested_symbol"]:
        errors.append(f"REQUEST_SYMBOL_MISMATCH:{returned}")

    actual_type = _norm_type(payload.get("marketType"))
    if actual_type != spec["market_type"]:
        errors.append(f"MARKET_TYPE_MISMATCH:{actual_type or 'missing'}!= {spec['market_type']}")

    expected_provider = _norm_provider_symbol(spec.get("provider_symbol"))
    actual_provider = _norm_provider_symbol(payload.get("marketSymbol"))
    if expected_provider and actual_provider != expected_provider:
        errors.append(f"PROVIDER_SYMBOL_MISMATCH:{actual_provider or 'missing'}!= {expected_provider}")

    try:
        price = float(payload.get("currentPrice"))
    except Exception:
        price = math.nan
    if not math.isfinite(price) or price <= 0:
        errors.append("INVALID_CURRENT_PRICE")
    else:
        lo, hi = spec.get("min"), spec.get("max")
        if lo is not None and price < lo:
            errors.append(f"PRICE_BELOW_SANITY_RANGE:{price}<{lo}")
        if hi is not None and price > hi:
            errors.append(f"PRICE_ABOVE_SANITY_RANGE:{price}>{hi}")

        try:
            m5 = float(m5_close)
        except Exception:
            m5 = math.nan
        if math.isfinite(m5) and m5 > 0:
            drift = abs(price - m5) / m5
            # 10% is deliberately loose; this is only an identity/data-corruption rail.
            if drift > 0.10:
                errors.append(f"LATEST_VS_M5_DRIFT_TOO_LARGE:{drift:.4f}")

    return errors


def audit_symbols() -> list[str]:
    return [
        "EURUSD", "GBPUSD", "USDJPY",
        "BTCUSDT", "ETHUSDT", "SOLUSDT",
        "XAUUSD", "XAGUSD",
        "NAS100", "SPX", "N225",
        "NQ", "MNQ", "ES", "MES",
    ]
