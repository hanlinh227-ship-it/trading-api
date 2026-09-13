from itertools import product

from strategies.common import flow_mask, make_candidates, trend_mask

family_name = "compression"


def parameter_grid():
    for side, comp, r, body_min in product(("LONG", "SHORT"), (0.70, 0.85), (0.75, 0.85, 0.90), (0.50, 0.80)):
        yield {"side": side, "compression_max": comp, "r": r, "body_min": body_min, "flow_min": 0.52}


def generate_candidates(f, params):
    side = params["side"]
    rng = f.high - f.low
    base = trend_mask(f, side) & (f.vol_regime <= params["compression_max"]) & (f.body_atr >= params["body_min"]) & flow_mask(f, side, params["flow_min"])
    if side == "LONG":
        mask = base & (f.close > f.prior_high_12)
        entry = f.high - params["r"] * rng
        stop = f.low - 0.05 * f.atr14
    else:
        mask = base & (f.close < f.prior_low_12)
        entry = f.low + params["r"] * rng
        stop = f.high + 0.05 * f.atr14
    return make_candidates(f, mask, side, entry, stop, max_fill_bars=12, max_hold_bars=144)
