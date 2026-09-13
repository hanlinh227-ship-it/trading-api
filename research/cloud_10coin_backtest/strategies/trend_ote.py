from itertools import product

from strategies.common import flow_mask, make_candidates, trend_mask

family_name = "trend_ote"


def parameter_grid():
    for side, r, body_min, rv, flow in product(("LONG", "SHORT"), (0.618, 0.79, 0.90), (0.50, 0.80), (0.80, 1.20), (0.50, 0.56)):
        yield {"side": side, "r": r, "body_min": body_min, "rel_volume_min": rv, "flow_min": flow}


def generate_candidates(f, params):
    side = params["side"]
    rng = f.high - f.low
    mask = trend_mask(f, side) & (f.body_atr >= params["body_min"]) & (f.rel_volume >= params["rel_volume_min"]) & flow_mask(f, side, params["flow_min"])
    if side == "LONG":
        mask &= f.close_loc >= 0.70
        entry = f.high - params["r"] * rng
        stop = f.low - 0.05 * f.atr14
    else:
        mask &= f.close_loc <= 0.30
        entry = f.low + params["r"] * rng
        stop = f.high + 0.05 * f.atr14
    return make_candidates(f, mask, side, entry, stop)
