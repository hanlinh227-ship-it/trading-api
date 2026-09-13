def directional_flow_ok(taker_buy_ratio: float, side: str, threshold: float) -> bool:
    return taker_buy_ratio >= threshold if side == "LONG" else taker_buy_ratio <= 1.0 - threshold
