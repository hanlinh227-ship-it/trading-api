def aligned_trend(row, side: str) -> bool:
    if side == "LONG":
        return row.h1_ma20 > row.h1_ma50 and row.h4_ma20 > row.h4_ma50
    return row.h1_ma20 < row.h1_ma50 and row.h4_ma20 < row.h4_ma50
