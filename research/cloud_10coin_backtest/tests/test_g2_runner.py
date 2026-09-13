from run import build_parser


def test_runner_defaults_to_g2_generation():
    args = build_parser().parse_args([])
    assert args.generation == "g2"


def test_runner_accepts_g1_for_reproducibility():
    args = build_parser().parse_args(["--generation", "g1"])
    assert args.generation == "g1"
