from g9.research_lanes import aggregate_lane_payloads, build_lane_plan


SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "SOLUSDT",
    "TRXUSDT", "DOGEUSDT", "LINKUSDT", "ADAUSDT", "XLMUSDT",
]


def test_lane_plan_is_deterministic_isolated_and_never_starves_a_coin():
    priorities = {"SOLUSDT": 3.0, "BTCUSDT": 0.5}
    first = build_lane_plan(SYMBOLS, base_budget=4, priority_weights=priorities)
    second = build_lane_plan(SYMBOLS, base_budget=4, priority_weights=priorities)

    assert first == second
    assert len(first) == 10
    assert len({row.lane_id for row in first}) == 10
    assert all(row.candidate_budget >= 1 for row in first)
    sol = next(row for row in first if row.symbol == "SOLUSDT")
    btc = next(row for row in first if row.symbol == "BTCUSDT")
    assert sol.candidate_budget > btc.candidate_budget
    assert all(row.production_execution_authority is False for row in first)


def test_aggregate_preserves_previous_state_for_failed_or_missing_lanes():
    plan = build_lane_plan(["BTCUSDT", "SOLUSDT", "ETHUSDT"], base_budget=2)
    previous = {
        "BTCUSDT": {"champion": "btc-old"},
        "SOLUSDT": {"champion": "sol-old"},
        "ETHUSDT": {"champion": "eth-old"},
    }
    payloads = {
        "BTCUSDT": {"status": "SUCCESS", "state": {"champion": "btc-new"}},
        "SOLUSDT": {"status": "FAILED", "error": "provider-down"},
    }

    merged = aggregate_lane_payloads(plan, payloads, previous_symbols=previous)

    assert merged["symbols"]["BTCUSDT"]["champion"] == "btc-new"
    assert merged["symbols"]["SOLUSDT"]["champion"] == "sol-old"
    assert merged["symbols"]["ETHUSDT"]["champion"] == "eth-old"
    assert merged["lane_status"]["SOLUSDT"] == "FAILED_PRESERVED"
    assert merged["lane_status"]["ETHUSDT"] == "MISSING_PRESERVED"
    assert merged["research_only"] is True
    assert merged["production_execution_authority"] is False


def test_lane_outputs_are_single_writer_inputs_not_shared_state_writes():
    plan = build_lane_plan(["BTCUSDT", "ETHUSDT"], base_budget=3)
    assert [row.artifact_name for row in plan] == [
        "g9-lane-BTCUSDT",
        "g9-lane-ETHUSDT",
    ]
    assert all(row.state_write_authority is False for row in plan)
