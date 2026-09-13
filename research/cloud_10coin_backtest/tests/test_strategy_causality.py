import importlib

FAMILIES = (
    "strategies.trend_ote",
    "strategies.sweep_mss",
    "strategies.break_retest",
    "strategies.compression",
    "strategies.mean_reversion",
)


def test_family_contract_and_grid_bounds():
    for name in FAMILIES:
        module = importlib.import_module(name)
        assert isinstance(module.family_name, str) and module.family_name
        grid = list(module.parameter_grid())
        assert 1 <= len(grid) <= 256
        assert callable(module.generate_candidates)


def test_family_grids_do_not_encode_specific_dates_or_trade_ids():
    forbidden = ("date", "timestamp", "trade_id", "index_id")
    for name in FAMILIES:
        module = importlib.import_module(name)
        for params in module.parameter_grid():
            keys = {str(k).lower() for k in params}
            assert not any(x in key for key in keys for x in forbidden)
