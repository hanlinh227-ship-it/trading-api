from itertools import product

from strategies.common import flow_mask, make_candidates, trend_mask

family_name = "sweep_mss"


def parameter_grid():
    for side, r, flow in product(("LONG", "SHORT"), (0.618, 0.79, 0.90), (0.50, 0.56)):
        yield {"side": side, "r": r, "flow_min": flow}


def generate_candidates(f, params):
    side = params["side"]
    rng = f.high - f.low
    if side == "LONG":
        mask = trend_mask(f, side) & (f.recent_sweep_low_3 > 0) & (f.close > f.prior_high_3) & flow_mask(f, side, params["flow_min"])
        entry = f.high - params["r"] * rng
        stop = f.low - 0.05 * f.atr14
    else:
        mask = trend_mask(f, side) & (f.recent_sweep_high_3 > 0) & (f.close < f.prior_low_3) & flow_mask(f, side, params["flow_min"])
        entry = f.low + params["r"] * rng
        stop = f.high + 0.05 * f.atr14
    return make_candidates(f, mask, side, entry, stop, max_fill_bars=6, max_hold_bars=144)
