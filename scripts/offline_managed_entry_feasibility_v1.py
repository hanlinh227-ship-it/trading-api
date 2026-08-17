#!/usr/bin/env python3
import json, math
from pathlib import Path

TARGET_WR = 0.80

# Canonical counts are taken from committed checkpoints/results. This audit does NOT
# reconstruct missing hourly snapshots and does not claim CUT decisions were observable.
markets = {
    "FOREX_F8_20D": {
        "wins": 248,
        "losses": 241,
        "resolved": 489,
        "avg_rr": 1.421,  # representative later F8 block; combined RR is around this range
        "rr_note": "F8 block RR evidence is approximately 1.42-1.45, inside target 1.0-1.5.",
        "source": "MASTER_TRADING_STATE.md / FOREX_STATE.md"
    },
    "CRYPTO_RECOVERED_12D": {
        "wins": 229,
        "losses": 411,
        "resolved": 640,
        "avg_rr": 1.639,
        "rr_note": "Recovered Crypto average RR 1.639 is above the requested 1.0-1.5 band; cannot retroactively re-score lower TP without preserved future paths.",
        "source": "CROSSMARKET_80WR_OFFLINE_AUDIT.md"
    }
}

for name, m in markets.items():
    w, l = m["wins"], m["losses"]
    # Need W/(W + L - C) >= target, assuming oracle-perfect CUT removes losses only.
    min_cut = max(0, math.ceil(w + l - (w / TARGET_WR)))
    min_cut = min(min_cut, l)
    remain_l = l - min_cut
    wr_after = w / (w + remain_l) if (w + remain_l) else 0
    m.update({
        "baseline_wr_pct": round(100*w/(w+l), 2),
        "oracle_min_loss_cuts_for_80": min_cut,
        "oracle_pct_of_losses_that_must_be_cut": round(100*min_cut/l, 2) if l else 0,
        "tp_sl_after_oracle_cut": {"tp": w, "sl": remain_l},
        "oracle_displayed_wr_pct": round(100*wr_after, 2),
        "integrity": "DIAGNOSTIC UPPER BOUND ONLY — assumes hindsight-perfect CUT of losers and zero accidental cuts of winners. NOT validation."
    })

result = {
    "version": "MANAGED ENTRY FEASIBILITY V1",
    "providerCreditsUsed": 0,
    "target": {"winRatePct": 80, "rrBand": [1.0, 1.5]},
    "markets": markets,
    "conclusion": {
        "FOREX": "NOT_VALIDATED",
        "CRYPTO": "NOT_VALIDATED",
        "reason": "Old committed result sets do not contain complete hourly observable price/indicator/news/calendar snapshots. An honest hourly HOLD/CUT blind test cannot be reconstructed without missing data. Oracle CUT burden is reported only to quantify difficulty."
    }
}

Path("data/managed_entry_feasibility_v1.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
