from itertools import product

from strategies.common import flow_mask, make_candidates, trend_mask

family_name = "break_retest"


def parameter_grid():
    for side, body_min, risk_atr, flow in product(("LONG", "SHORT"), (0.40, 0.70), (0.30, 0.50), (0.50, 0.56)):
        yield {"side": side, "body_min": body_min, "risk_atr": risk_atr, "flow_min": flow}


def generate_candidates(f, params):
    side = params["side"]
    if side == "LONG":
        mask = trend_mask(f, side) & (f.close > f.prior_high_24) & (f.body_atr >= params["body_min"]) & flow_mask(f, side, params["flow_min"])
        entry = f.prior_high_24
        stop = entry - params["risk_atr"] * f.atr14
    else:
        mask = trend_mask(f, side) & (f.close < f.prior_low_24) & (f.body_atr >= params["body_min"]) & flow_mask(f, side, params["flow_min"])
        entry = f.prior_low_24
        stop = entry + params["risk_atr"] * f.atr14
    return make_candidates(f, mask, side, entry, stop, max_fill_bars=12, max_hold_bars=144)
