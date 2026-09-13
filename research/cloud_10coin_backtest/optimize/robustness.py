def catastrophic_collapse(validation_wr: float, holdout_wr: float, min_segment_wr: float = 0.60) -> bool:
    return validation_wr < min_segment_wr or holdout_wr < min_segment_wr
