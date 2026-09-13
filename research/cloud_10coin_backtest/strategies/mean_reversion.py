from itertools import product

from strategies.common import make_candidates

family_name = "mean_reversion"


def parameter_grid():
    for side, z, rejection in product(("LONG", "SHORT"), (1.5, 2.0, 2.5), (0.65, 0.75)):
        yield {"side": side, "z_min": z, "rejection": rejection}


def generate_candidates(f, params):
    side = params["side"]
    if side == "LONG":
        mask = (f.z_ema20 <= -params["z_min"]) & (f.close_loc >= params["rejection"]) & (f.taker_buy_ratio >= 0.50)
        entry = f.close
        stop = f.low - 0.10 * f.atr14
    else:
        mask = (f.z_ema20 >= params["z_min"]) & (f.close_loc <= 1.0 - params["rejection"]) & (f.taker_buy_ratio <= 0.50)
        entry = f.close
        stop = f.high + 0.10 * f.atr14
    return make_candidates(f, mask, side, entry, stop, max_fill_bars=1, max_hold_bars=96)
