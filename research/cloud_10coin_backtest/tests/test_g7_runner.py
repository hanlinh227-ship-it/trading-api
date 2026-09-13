import run


def test_runner_accepts_g7_generation():
    args = run.build_parser().parse_args(["--generation", "g7"])
    assert args.generation == "g7"


def test_runner_imports_g7_search_dispatch():
    assert run.search_coin_g7.__name__ == "search_coin_g7"
