#!/usr/bin/env python3
"""V74 live-analysis playbook layered on the frozen V73 backtest prior.

This module does NOT optimize parameters and does NOT place orders.
It converts each V73 symbol method into a live decision workflow with:
- exact-symbol / freshness gates,
- symbol-specific macro or project/news context,
- D1/H4/H1 bias,
- M15/M5 confirmation,
- structure-first stop placement,
- RR 1:1 default and conditional 1:2 promotion,
- independent rules for trade #2/#3.

V73 remains frozen as the statistical development prior.
"""
import argparse
import json

from scripts.nocut_intraday_method_v73 import load_config, get_symbol, choose_action

VERSION = "LIVE_SYMBOL_ANALYSIS_V74"
CLASSIFICATION = "LIVE OPERATIONAL PLAYBOOK LAYER; V73 PRIOR IS EXPOSED DEVELOPMENT, NOT UNTOUCHED OOS"

FX_CCY = {
    "USD": {
        "name": "US dollar",
        "drivers": ["Fed/FOMC path", "US CPI/PCE and labor data", "US Treasury yields + DXY", "global USD liquidity/risk"],
    },
    "EUR": {
        "name": "euro",
        "drivers": ["ECB path", "Eurozone CPI/PMI", "Germany growth/industrial data", "EU fiscal/political risk"],
    },
    "GBP": {
        "name": "British pound",
        "drivers": ["BoE path", "UK CPI/wages/jobs", "UK GDP/retail sales", "UK gilt/fiscal risk"],
    },
    "JPY": {
        "name": "Japanese yen",
        "drivers": ["BoJ path", "MoF intervention risk", "Japan/Tokyo CPI and wages", "JGB yields + global risk"],
    },
    "CHF": {
        "name": "Swiss franc",
        "drivers": ["SNB path", "Swiss CPI", "safe-haven flows", "European risk sentiment"],
    },
    "CAD": {
        "name": "Canadian dollar",
        "drivers": ["BoC path", "Canada CPI/jobs/GDP", "WTI crude oil", "US-Canada rate/growth differential"],
    },
    "AUD": {
        "name": "Australian dollar",
        "drivers": ["RBA path", "Australia CPI/jobs", "China PMIs/growth", "iron ore + global risk sentiment"],
    },
    "NZD": {
        "name": "New Zealand dollar",
        "drivers": ["RBNZ path", "New Zealand CPI/jobs", "China growth", "dairy/commodity + global risk sentiment"],
    },
}

PROFILE_DRIVERS = {
    "MARKET_CORE": ["spot ETF/treasury demand", "miner/on-chain flows", "macro liquidity/rates", "BTC dominance and derivatives positioning"],
    "ETH_ECOSYSTEM": ["ETH ETF/staking flows", "Ethereum upgrades", "L2/DeFi activity and fees", "ETH/BTC relative strength"],
    "SOL_ECOSYSTEM": ["Solana network/DEX activity", "ecosystem launches", "validator/staking flows", "SOL/BTC and SOL/ETH relative strength"],
    "PERP_DEX": ["perp DEX volume/OI/fees", "protocol incentives/buybacks", "token unlock/supply", "leverage/funding regime"],
    "ALT_LARGE": ["network usage", "staking/supply changes", "major ecosystem or regulatory catalysts", "relative strength vs BTC"],
    "PAYMENTS_LEGAL": ["payments/XRPL adoption", "legal/regulatory developments", "institutional partnerships", "exchange/liquidity flows"],
    "DEFI_LENDING": ["TVL/borrowing utilization", "stablecoin/GHO activity", "governance and risk parameters", "ETH/DeFi liquidity"],
    "L1_ALT": ["chain upgrades/adoption", "staking/validator flows", "ecosystem TVL/activity", "relative strength vs BTC"],
    "L2": ["rollup activity/fees", "token unlocks", "Ethereum roadmap", "L2 sector relative strength"],
    "MEME": ["social-attention velocity", "whale/exchange flows", "meme-sector breadth", "listing/delisting catalysts"],
    "DEFI": ["protocol TVL/fees", "governance/upgrades", "incentives/unlocks", "DeFi sector breadth"],
    "MEME_LARGE": ["meme-sector breadth", "social/whale activity", "payments/adoption catalysts", "BTC risk regime"],
    "INTEROP": ["interoperability activity", "ecosystem upgrades", "staking/unlocks", "L1 sector breadth"],
    "STORAGE": ["storage demand/network usage", "protocol upgrades", "token unlocks", "AI/data narrative"],
    "ENTERPRISE_L1": ["enterprise/government adoption", "Hedera network usage/fees", "Council/ecosystem changes", "stablecoin/RWA activity"],
    "AI_INFOFI": ["AI/InfoFi product growth", "attention/data demand", "unlocks/listings", "AI-sector breadth"],
    "ORACLE": ["oracle integrations", "CCIP/RWA/DeFi adoption", "token economics/staking", "ETH/DeFi regime"],
    "L1_AI": ["chain usage and chain-abstraction adoption", "AI ecosystem integrations", "staking/unlocks", "L1/AI relative strength"],
    "RWA": ["RWA adoption/partnerships", "regulation and Treasury-rate backdrop", "token unlocks", "RWA sector flows"],
    "BITCOIN_BRC20": ["Bitcoin fees/activity", "Ordinals/BRC-20 demand", "BTC trend/dominance", "exchange liquidity"],
    "AI_COMPUTE": ["AI/compute demand", "network usage/revenue", "token unlocks", "AI-sector breadth"],
    "L1_REBRAND": ["Sonic chain TVL/DEX activity", "FTM-to-S migration effects", "validator/staking changes", "L1 relative strength"],
    "BTC_L2": ["sBTC/Stacks adoption", "Bitcoin L2 activity", "protocol upgrades", "BTC trend/dominance"],
    "L1_HIGHBETA": ["chain activity/TVL", "ecosystem launches", "token unlocks", "high-beta relative strength vs BTC"],
    "AI_SUBNET": ["Bittensor subnet activity", "TAO emissions/staking", "dTAO/subnet changes", "AI-sector breadth"],
    "MODULAR": ["data-availability adoption", "ecosystem integrations", "token unlocks", "L1/L2 breadth"],
    "MESSAGING_L1": ["Telegram/TON ecosystem growth", "chain/stablecoin usage", "token unlocks/listings", "BTC regime"],
    "POLITICAL_MEME": ["political/news catalyst intensity", "social/whale flows", "unlock/supply events", "meme-sector risk appetite"],
    "AI_IDENTITY": ["World ID adoption/regulation", "World Chain activity", "WLD unlock/distribution changes", "AI/identity sector flows"],
    "AI_AGENT": ["AI-agent adoption", "ecosystem integrations", "unlocks/listings", "AI-sector breadth"],
    "AI_DATA": ["AI-data demand", "network usage/rewards", "unlocks/listings", "AI-sector breadth"],
    "IP_RWA": ["IP licensing/adoption", "Story ecosystem activity", "token unlocks", "RWA/IP sector flows"],
    "MEME_PLATFORM": ["Pump.fun platform volume/revenue", "Solana meme issuance/activity", "token unlock/buyback mechanics", "SOL/meme regime"],
    "STABLECOIN_L1": ["stablecoin supply/transfer volume", "Plasma TVL/liquidity", "XPL validator/supply changes", "stablecoin/payment regulation"],
    "PRIVACY": ["privacy regulation", "network adoption", "exchange access/liquidity", "BTC regime"],
    "IDENTITY": ["identity/adoption integrations", "network activity", "unlocks/listings", "sector flows"],
}

CRYPTO_IDENTITY = {
    "BTC": ("Bitcoin", "MARKET_CORE"),
    "ETH": ("Ethereum", "ETH_ECOSYSTEM"),
    "SOL": ("Solana", "SOL_ECOSYSTEM"),
    "HYPE": ("Hyperliquid", "PERP_DEX"),
    "SHIB": ("Shiba Inu", "ALT_LARGE"),
    "TRX": ("TRON", "ALT_LARGE"),
    "XRP": ("XRP / XRP Ledger", "PAYMENTS_LEGAL"),
    "AAVE": ("Aave", "DEFI_LENDING"),
    "ADA": ("Cardano", "L1_ALT"),
    "ALGO": ("Algorand", "L1_ALT"),
    "APT": ("Aptos", "L1_ALT"),
    "ARB": ("Arbitrum", "L2"),
    "ATOM": ("Cosmos Hub", "L1_ALT"),
    "AVAX": ("Avalanche", "L1_ALT"),
    "BCH": ("Bitcoin Cash", "L1_ALT"),
    "BONK": ("Bonk", "MEME"),
    "CRV": ("Curve", "DEFI"),
    "DOGE": ("Dogecoin", "MEME_LARGE"),
    "DOT": ("Polkadot", "INTEROP"),
    "ETC": ("Ethereum Classic", "L1_ALT"),
    "FIL": ("Filecoin", "STORAGE"),
    "FLOKI": ("Floki", "MEME"),
    "HBAR": ("Hedera", "ENTERPRISE_L1"),
    "INJ": ("Injective", "DEFI"),
    "JTO": ("Jito", "DEFI"),
    "JUP": ("Jupiter", "DEFI"),
    "KAITO": ("Kaito", "AI_INFOFI"),
    "LDO": ("Lido", "DEFI"),
    "LINK": ("Chainlink", "ORACLE"),
    "LTC": ("Litecoin", "L1_ALT"),
    "MOODENG": ("Moo Deng", "MEME"),
    "NEAR": ("NEAR Protocol", "L1_AI"),
    "ONDO": ("Ondo Finance", "RWA"),
    "OP": ("Optimism", "L2"),
    "ORDI": ("ORDI / BRC-20", "BITCOIN_BRC20"),
    "PENGU": ("Pudgy Penguins / PENGU", "MEME"),
    "PEPE": ("Pepe", "MEME"),
    "PNUT": ("Peanut the Squirrel", "MEME"),
    "POL": ("Polygon Ecosystem Token", "L2"),
    "POPCAT": ("Popcat", "MEME"),
    "RENDER": ("Render Network", "AI_COMPUTE"),
    "S": ("Sonic", "L1_REBRAND"),
    "STX": ("Stacks", "BTC_L2"),
    "SUI": ("Sui", "L1_HIGHBETA"),
    "TAO": ("Bittensor", "AI_SUBNET"),
    "TIA": ("Celestia", "MODULAR"),
    "TON": ("The Open Network", "MESSAGING_L1"),
    "TRUMP": ("Official Trump", "POLITICAL_MEME"),
    "UNI": ("Uniswap", "DEFI"),
    "WIF": ("dogwifhat", "MEME"),
    "WLD": ("World / Worldcoin", "AI_IDENTITY"),
    "AIXBT": ("aixbt", "AI_AGENT"),
    "ASTER": ("Aster", "PERP_DEX"),
    "FARTCOIN": ("Fartcoin", "MEME"),
    "GRASS": ("Grass", "AI_DATA"),
    "IP": ("Story", "IP_RWA"),
    "LIT": ("Lighter", "PERP_DEX"),
    "PUMP": ("Pump.fun", "MEME_PLATFORM"),
    "VIRTUAL": ("Virtuals Protocol", "AI_AGENT"),
    "XPL": ("Plasma", "STABLECOIN_L1"),
    "ZEC": ("Zcash", "PRIVACY"),
}

SPECIAL_IDENTITY_NOTES = {
    "LIT": "LIT is Lighter Infrastructure Token / Lighter, not legacy Litentry. Verify the exact exchange instrument before every live read.",
    "S": "S is the native Sonic token after the Fantom-to-Sonic migration; do not analyze it as legacy FTM.",
    "XPL": "XPL is Plasma's native token; its dominant fundamental context is stablecoin/payment-network activity.",
    "ASTER": "ASTER is the Aster perp-DEX ecosystem token; prioritize perp volume/OI, incentives and token supply.",
}

def _router_features(node, out=None):
    out = out or set()
    if not isinstance(node, dict):
        return out
    if node.get("feature"):
        out.add(node["feature"])
    for key in ("lo", "hi"):
        if isinstance(node.get(key), dict):
            _router_features(node[key], out)
    return out

def _family(action):
    if not action:
        return "ROUTER_PENDING"
    return str(action.get("family") or action.get("mode") or action.get("model") or "V73_CUSTOM").upper()

def _entry_mode(action):
    if not action:
        return "ROUTER_PENDING"
    return str(action.get("entryMode") or action.get("entry") or "V73_CUSTOM").upper()

def _anchor(action):
    if not action:
        return None
    h = action.get("signalHourUTC")
    if h is None:
        return None
    h = int(h) % 24
    bangkok = (h + 7) % 24
    return {"utcHour": h, "bangkokHour": bangkok, "meaning": "preferred observation/decision anchor, NOT an automatic blind entry"}

def _setup_archetype(action):
    fam = _family(action)
    mode = _entry_mode(action)
    if "MEAN" in fam or "REVERT" in fam or "FADE" in mode:
        return "liquidity-sweep reversal / mean-reversion with confirmation"
    if "MOM" in fam or "TREND" in fam or "BTCALIGN" in fam or "RELATIVE" in fam:
        return "trend/relative-strength continuation after pullback or breakout-retest"
    if "BREADTH" in fam or "HYBRID" in fam:
        return "regime-confirmed continuation/reversal chosen by the frozen router"
    return "V73 symbol-specific geometry, executed only after live structure confirmation"

def _sessions_fx(sym):
    a, b = sym[:3], sym[3:]
    asia = {"JPY", "AUD", "NZD"}
    london = {"EUR", "GBP", "CHF"}
    ny = {"USD", "CAD"}
    scores = {"ASIA": int(a in asia) + int(b in asia), "LONDON": int(a in london) + int(b in london), "NEW_YORK": int(a in ny) + int(b in ny)}
    order = sorted(scores, key=lambda x: (scores[x], {"ASIA": 0, "LONDON": 1, "NEW_YORK": 2}[x]), reverse=True)
    if "USD" in (a, b) and "LONDON" in order:
        secondary = "LONDON_NY_OVERLAP"
    else:
        secondary = order[1]
    return [order[0], secondary, order[2]]

def _timeframes(market, entry):
    if market == "forex":
        return {
            "macro": "calendar + yields/rates + base-vs-quote currency score",
            "bias": ["D1", "H4", "H1"],
            "trigger": ["M15", "M5"],
            "execution": "M5",
        }
    prior_tf = entry.get("timeframe", "H1")
    return {
        "macro": "BTC/market regime + symbol-specific project/on-chain/derivatives context",
        "bias": ["D1", "H4", "H1"] if prior_tf == "H1" else ["D1", "H4", "H1 refinement"],
        "trigger": ["M15", "M5"],
        "execution": "M5",
        "v73PriorTimeframe": prior_tf,
    }

def _live_gates(market):
    base = {
        "exactSymbolRequired": True,
        "symbolVerifiedRequired": True,
        "freshTimestampRequired": True,
        "stalePriceForbidden": True,
        "spreadAndSlippageEstimateRequired": True,
        "estimatedRoundTripCostMaxR": 0.10,
        "sameBarAmbiguity": "never infer a favorable fill/order from an OHLC bar when the live tick/order sequence is unavailable",
    }
    if market == "forex":
        base.update({"maxQuoteAgeSeconds": 30, "marketOpenRequired": True, "highImpactEventHandling": "do not enter immediately before a top-tier event; re-score after the event and wait for the first confirmed M5 structure/retest"})
    else:
        base.update({"maxQuoteAgeSeconds": 10, "marketOpenRequired": True, "highImpactEventHandling": "event/news changes regime and direction score; if price already displaced >1 ATR, wait for pullback/retest instead of chasing"})
    return base

def _confirmation_rules(action):
    mode = _entry_mode(action)
    rules = [
        "D1/H4 define draw-on-liquidity and premium/discount or trend state.",
        "H1 must agree with, or clearly transition toward, the selected V73 action; record sweep, displacement and structural break.",
        "M15 must show a tradable location: liquidity sweep, breakout-retest, FVG/imbalance retest, or clean support/resistance reclaim.",
        "M5 is the execution trigger: close-confirmed MSS/displacement plus retest; do not enter solely because the V73 clock arrived.",
    ]
    if "DUAL_FADE" in mode:
        rules.append("DUAL_FADE is geometry only: never place both sides blindly. Activate only the side confirmed by live bias + M15/M5 trigger.")
    return rules

def _rr_policy(action):
    prior_rr = float(action.get("rr", 1.0)) if action else 1.0
    return {
        "allowed": [1.0, 2.0],
        "default": 1.0,
        "v73PriorRR": prior_rr,
        "promoteTo2RWhen": [
            "clear structural/liquidity target remains at least 2.2R away after estimated costs",
            "D1/H4/H1 are aligned in the trade direction or H1 has a confirmed regime transition",
            "no major opposing liquidity/HTF level sits before 2R",
            "entry is not a late chase after an already extended impulse",
        ],
        "otherwise": "use 1:1; never reduce below 1:1 to manufacture win rate",
    }

def _sl_policy(action):
    risk_atr = action.get("riskATR") if action else None
    return {
        "primary": "structure-first invalidation beyond the sweep/swing/breaker that invalidates the thesis",
        "atrFloorFromV73": risk_atr,
        "rule": "ATR is a minimum volatility buffer, not a reason to widen a structurally invalid trade",
        "never": ["widen SL after entry", "move SL only to avoid realizing a loss"],
    }

def _trade_count_policy():
    return {
        "minimumEligibleDay": 1,
        "maximumPerDay": 3,
        "trade1": "best confirmed setup in the symbol's preferred active window",
        "trade2": "allowed only after trade1 is closed or risk is neutralized AND a new independent liquidity event/structure appears",
        "trade3": "allowed only in a later independent session/regime with A-grade confirmation; never as revenge or averaging",
        "afterTwoLosses": "do not force a third recovery trade; the daily minimum was already satisfied",
        "mandatoryDailyFallback": "if no A-grade setup has triggered by the final liquid window, use the frozen V73 directional/regime prior plus H1 close confirmation and an M5 pullback/retest at 0.5x normal risk; this fallback is a V74 live rule and is NOT part of the V73 backtest",
        "technicalBlock": "if exact symbol, fresh price, market-open status or executable spread cannot be verified, return DATA_BLOCK rather than fabricate a live trade; this is not a discretionary NO-TRADE signal",
    }

def _news_context(market, sym, entry):
    if market == "forex":
        a, b = sym[:3], sym[3:]
        return {
            "identity": f"{a}/{b}",
            "base": {"currency": a, **FX_CCY[a]},
            "quote": {"currency": b, **FX_CCY[b]},
            "decisionRule": "score base drivers versus quote drivers point-in-time; macro/news may strengthen, weaken or delay the V73 prior, but direction still needs price-structure confirmation",
            "sourcePriority": ["official central-bank/calendar release", "official statistics/treasury source", "reputable real-time market news", "fresh yields/DXY/commodity data"],
        }
    project, profile = CRYPTO_IDENTITY[sym]
    return {
        "identity": {"ticker": sym, "project": project, "profile": profile},
        "projectDrivers": PROFILE_DRIVERS[profile],
        "symbolSpecific": [
            f"{project} official announcements/upgrades",
            f"{sym} unlock/supply/staking/buyback changes where applicable",
            f"{sym} spot/perp volume, OI/funding, exchange and on-chain/whale flows",
            f"{sym}/BTC relative strength plus BTC dominance/breadth",
        ],
        "identityNote": SPECIAL_IDENTITY_NOTES.get(sym),
        "decisionRule": "project/news context routes or confirms the frozen symbol setup; price action must confirm. Do not chase a catalyst after an extended impulse.",
        "sourcePriority": ["official project/protocol docs and announcements", "official exchange listing/market notices", "fresh exchange derivatives/spot data", "on-chain data where relevant", "reputable real-time market news"],
    }

def build_playbook(symbol, features=None, cfg=None):
    cfg = cfg or load_config()
    market, sym, entry = get_symbol(symbol, cfg)
    method = entry["method"]
    action = None
    if "router" in method:
        if features is not None:
            action = choose_action(entry, features)
    else:
        action = choose_action(entry, features)
    required = sorted(_router_features(method.get("router"))) if "router" in method else []
    sessions = _sessions_fx(sym) if market == "forex" else ["V73_SIGNAL_ANCHOR", "LONDON_LIQUIDITY_WINDOW", "NEW_YORK_LIQUIDITY_WINDOW"]
    playbook = {
        "version": VERSION,
        "classification": CLASSIFICATION,
        "market": market,
        "symbol": sym,
        "frozenV73": {
            "source": entry["source"],
            "priorTimeframe": entry["timeframe"],
            "methodStatus": method.get("status"),
            "routerRequired": "router" in method,
            "requiredRouterFeatures": required,
            "selectedAction": action,
            "warning": "V73 parameters are an exposed-development statistical prior; do not treat the historical WR as a live guarantee.",
        },
        "liveRoleOfV73": {
            "signalHour": "observation anchor only, never an automatic market order",
            "family": "setup archetype prior",
            "entryMode": "execution-geometry prior",
            "router": "point-in-time regime selector using only observable current/past features",
        },
        "newsAndContext": _news_context(market, sym, entry),
        "timeframeStack": _timeframes(market, entry),
        "preferredWindows": sessions,
        "setupArchetype": _setup_archetype(action),
        "liveGates": _live_gates(market),
        "confirmation": _confirmation_rules(action),
        "stopLoss": _sl_policy(action),
        "rr": _rr_policy(action),
        "tradeCount": _trade_count_policy(),
        "executionChecklist": [
            "1) Verify exact symbol, market venue, current price, bid/ask and timestamp.",
            "2) Refresh symbol-specific news/context and broad regime.",
            "3) Establish D1/H4 draw-on-liquidity and H1 structure.",
            "4) Select/inspect the frozen V73 action; never re-optimize it live.",
            "5) Wait for M15 location and M5 close-confirmed trigger.",
            "6) Place structural SL first, then calculate 1R; use 2R only if the RR2 promotion rules pass.",
            "7) Record entry reason, context, spread/slippage and outcome for forward validation.",
        ],
    }
    playbook["frozenV73"]["anchor"] = _anchor(action)
    return playbook

def validate():
    cfg = load_config()
    fx = set(cfg["forex"]["symbols"])
    cr = set(cfg["crypto"]["symbols"])
    errors = []
    if set(CRYPTO_IDENTITY) != cr:
        errors.append({"cryptoIdentityMissing": sorted(cr - set(CRYPTO_IDENTITY)), "cryptoIdentityExtra": sorted(set(CRYPTO_IDENTITY) - cr)})
    used_profiles = {p for _, p in CRYPTO_IDENTITY.values()}
    missing_profiles = sorted(used_profiles - set(PROFILE_DRIVERS))
    if missing_profiles:
        errors.append({"missingProfileDrivers": missing_profiles})
    for sym in sorted(fx | cr):
        try:
            pb = build_playbook(sym, cfg=cfg)
            if pb["rr"]["default"] not in (1.0, 2.0):
                errors.append({sym: "bad RR"})
            if pb["tradeCount"]["minimumEligibleDay"] != 1 or pb["tradeCount"]["maximumPerDay"] != 3:
                errors.append({sym: "bad trade-count policy"})
            if not pb["newsAndContext"]:
                errors.append({sym: "missing context"})
        except Exception as exc:
            errors.append({sym: repr(exc)})
    result = {
        "ok": not errors,
        "version": VERSION,
        "forex": len(fx),
        "crypto": len(cr),
        "total": len(fx) + len(cr),
        "cryptoProfiles": len(used_profiles),
        "profileDriverCoverage": len(used_profiles - set(missing_profiles)),
        "litIdentity": CRYPTO_IDENTITY["LIT"],
        "errors": errors,
    }
    return result

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol", nargs="?")
    ap.add_argument("features", nargs="?", help="JSON observable V73 router features")
    ap.add_argument("--validate", action="store_true")
    args = ap.parse_args()
    if args.validate:
        out = validate()
        print(json.dumps(out, indent=2, ensure_ascii=False))
        raise SystemExit(0 if out["ok"] else 1)
    if not args.symbol:
        raise SystemExit("usage: python scripts/live_symbol_analysis_v74.py SYMBOL [JSON_FEATURES] | --validate")
    features = json.loads(args.features) if args.features else None
    print(json.dumps(build_playbook(args.symbol, features), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
