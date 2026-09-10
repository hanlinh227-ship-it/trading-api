from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import random
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE_DIR = HERE.parent / "kaggriculture"

SPEC_M = importlib.util.spec_from_file_location("reward_agent_v2_tune", HERE / "main.py")
MOD = importlib.util.module_from_spec(SPEC_M)
SPEC_M.loader.exec_module(MOD)
SPEC_B = importlib.util.spec_from_file_location("reward_bench_v2_tune", HERE / "benchmark.py")
BENCH = importlib.util.module_from_spec(SPEC_B)
SPEC_B.loader.exec_module(BENCH)
SPEC_BASE = importlib.util.spec_from_file_location("reward_agent_v1_baseline", BASE_DIR / "main.py")
BASE_MOD = importlib.util.module_from_spec(SPEC_BASE)
SPEC_BASE.loader.exec_module(BASE_MOD)

BOUNDS = {
    "target_hands": (9, 15, "int"),
    "late_hands": (2, 8, "int"),
    "late_hire_stop_day": (24, 29, "int"),
    "first_land_threshold": (2800, 7000, "float"),
    "first_land_deadline": (6, 16, "int"),
    "max_quadrants": (1, 3, "int"),
    "sell_floor_ratio": (0.55, 0.92, "float"),
    "ahead_sell_floor_ratio": (0.65, 1.05, "float"),
    "behind_sell_floor_ratio": (0.42, 0.82, "float"),
    "cash_gap_trigger": (800, 5000, "float"),
    "sell_batch_limit": (2, 12, "int"),
    "late_liquidation_day": (25, 29, "int"),
    "seed_budget_ratio": (0.20, 0.50, "float"),
    "seed_buffer_per_unit": (0.8, 2.6, "float"),
    "max_seed_stock": (20, 60, "int"),
    "distance_penalty": (5.0, 22.0, "float"),
    "phase_early_end": (3, 8, "int"),
    "phase_mid_end": (12, 19, "int"),
    "phase_late_end": (19, 25, "int"),
}
PHASES = ("weights_early", "weights_mid", "weights_late", "weights_end")
CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")


def load_json_params(path, fallback):
    if path.exists():
        data = json.loads(path.read_text())
        return copy.deepcopy(data.get("params", data))
    return copy.deepcopy(fallback)


def clamp(k, v):
    lo, hi, kind = BOUNDS[k]
    v = min(hi, max(lo, v))
    return int(round(v)) if kind == "int" else round(float(v), 5)


def normalize_weights(w):
    out = {c: max(0.0, float(w.get(c, 0.0))) for c in CROPS}
    s = sum(out.values())
    if s <= 1e-9:
        out["WHEAT"] = 1.0
        s = 1.0
    return {c: round(out[c] / s, 5) for c in CROPS}


def legacy_to_v2(base):
    p = copy.deepcopy(MOD.DEFAULT_PARAMS)
    for k, v in base.items():
        if k in p:
            p[k] = copy.deepcopy(v)
    # Reproduce V1 behavior as closely as possible for an honest reference.
    p.update({
        "max_quadrants": 4,
        "sell_batch_limit": 100,
        "distance_penalty": 7.0,
        "phase_early_end": 4,
        "phase_mid_end": 16,
        "phase_late_end": 22,
        "cash_gap_trigger": 2000,
        "ahead_sell_floor_ratio": float(p.get("sell_floor_ratio", 0.76)),
    })
    return p


def strategic_seed(base):
    p = legacy_to_v2(base)
    p.update({
        "target_hands": 11,
        "max_quadrants": 2,
        "sell_batch_limit": 5,
        "distance_penalty": 11.0,
        "cash_gap_trigger": 2200,
        "ahead_sell_floor_ratio": 0.86,
        "weights_early": {"WHEAT": 0.38, "CARROT": 0.00, "TOMATO": 0.02, "STRAWBERRY": 0.60, "MELON": 0.00},
        "weights_mid": {"WHEAT": 0.35, "CARROT": 0.00, "TOMATO": 0.02, "STRAWBERRY": 0.63, "MELON": 0.00},
        "weights_late": {"WHEAT": 0.65, "CARROT": 0.10, "TOMATO": 0.00, "STRAWBERRY": 0.25, "MELON": 0.00},
        "weights_end": {"WHEAT": 0.72, "CARROT": 0.28, "TOMATO": 0.00, "STRAWBERRY": 0.00, "MELON": 0.00},
    })
    return p


def mutate(parent, rng, temperature=1.0):
    child = copy.deepcopy(parent)
    keys = list(BOUNDS)
    rng.shuffle(keys)
    n = rng.randint(2, min(7, len(keys)))
    for k in keys[:n]:
        lo, hi, _ = BOUNDS[k]
        sigma = (hi - lo) * 0.13 * temperature
        child[k] = clamp(k, float(child[k]) + rng.gauss(0, sigma))

    if rng.random() < 0.72:
        phase = rng.choice(PHASES)
        w = normalize_weights(child[phase])
        a, b = rng.sample(CROPS, 2)
        delta = abs(rng.gauss(0, 0.09 * temperature))
        delta = min(delta, w[a])
        w[a] -= delta
        w[b] += delta
        child[phase] = normalize_weights(w)

    child["behind_sell_floor_ratio"] = min(float(child["behind_sell_floor_ratio"]), float(child["sell_floor_ratio"]) - 0.02)
    child["ahead_sell_floor_ratio"] = max(float(child["ahead_sell_floor_ratio"]), float(child["sell_floor_ratio"]))
    child["phase_mid_end"] = max(int(child["phase_mid_end"]), int(child["phase_early_end"]) + 4)
    child["phase_late_end"] = max(int(child["phase_late_end"]), int(child["phase_mid_end"]) + 3)
    child["phase_late_end"] = min(25, child["phase_late_end"])
    return child


def _eval_worker(payload):
    params, seeds, steps = payload
    return BENCH.evaluate(params=params, seeds=tuple(seeds), opponents=("starter",), episode_steps=steps)


def parallel_eval(params_list, seeds, steps, workers):
    if workers <= 1:
        return [BENCH.evaluate(params=p, seeds=seeds, opponents=("starter",), episode_steps=steps) for p in params_list]
    out = [None] * len(params_list)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_eval_worker, (p, tuple(seeds), steps)): i for i, p in enumerate(params_list)}
        for fut in as_completed(futs):
            out[futs[fut]] = fut.result()
    return out


def compact(ev):
    return {k: ev[k] for k in ("objective", "win_rate", "mean_margin", "p20_margin", "worst_margin", "mean_money", "games", "valid_games")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=int, default=64)
    ap.add_argument("--shortlist", type=int, default=10)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--fast-seeds", default="20260805")
    ap.add_argument("--seeds", default="20260805,20260811,20260829")
    ap.add_argument("--holdout-seeds", default="20260901,20260903,20260907,20260911")
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--rng-seed", type=int, default=20260910)
    ap.add_argument("--baseline", default=str(BASE_DIR / "champion.json"))
    ap.add_argument("--champion", default=str(HERE / "champion.json"))
    ap.add_argument("--report", default=str(HERE / "artifacts" / "tuning-report.json"))
    args = ap.parse_args()

    workers = args.workers if args.workers > 0 else max(1, min(8, os.cpu_count() or 2))
    fast_seeds = tuple(int(x) for x in args.fast_seeds.split(",") if x.strip())
    train_seeds = tuple(int(x) for x in args.seeds.split(",") if x.strip())
    holdout = tuple(int(x) for x in args.holdout_seeds.split(",") if x.strip())
    baseline_raw = load_json_params(Path(args.baseline), BASE_MOD.DEFAULT_PARAMS)
    baseline_agent = BASE_MOD.make_agent(baseline_raw)
    legacy = legacy_to_v2(baseline_raw)
    seed = strategic_seed(baseline_raw)
    champion_path = Path(args.champion)
    previous_v2 = load_json_params(champion_path, seed)
    rng = random.Random(args.rng_seed)

    pool = [legacy, seed, previous_v2]
    parents = [seed, legacy, previous_v2]
    target = max(8, int(args.candidates))
    for i in range(len(pool), target):
        parent = parents[i % len(parents)] if rng.random() < 0.55 else rng.choice(pool[max(0, len(pool)-12):])
        temp = max(0.35, 1.05 - i / max(1, target) * 0.65)
        pool.append(mutate(parent, rng, temp))

    fast_evals = parallel_eval(pool, fast_seeds, args.steps, workers)
    ranked_fast = sorted(range(len(pool)), key=lambda i: fast_evals[i]["objective"], reverse=True)
    shortlist_n = max(3, min(int(args.shortlist), len(pool)))
    selected_idx = ranked_fast[:shortlist_n]
    selected = [pool[i] for i in selected_idx]
    full_evals = parallel_eval(selected, train_seeds, args.steps, workers)
    best_j = max(range(len(selected)), key=lambda j: full_evals[j]["objective"])
    best = selected[best_j]
    best_eval = full_evals[best_j]

    baseline_hold = BENCH.evaluate_agent(baseline_agent, seeds=holdout, opponents=("starter",), episode_steps=args.steps)
    best_hold = BENCH.evaluate(best, seeds=holdout, opponents=("starter",), episode_steps=args.steps)
    duel = BENCH.duel(MOD.make_agent(best), baseline_agent, holdout, episode_steps=args.steps)

    improved = (
        best_hold["valid_games"] == best_hold["games"]
        and duel["valid_games"] == duel["games"]
        and best_hold["objective"] >= baseline_hold["objective"]
        and best_hold["mean_margin"] >= baseline_hold["mean_margin"]
        and best_hold["p20_margin"] >= baseline_hold["p20_margin"] - 1000
        and duel["win_rate"] >= 0.50
        and duel["mean_margin"] >= 0
    )

    chosen = best if improved else previous_v2
    result = {
        "schema": "KAGGRICULTURE_V2_FAST_SEARCH",
        "improved_vs_v1": improved,
        "workers": workers,
        "candidate_count": len(pool),
        "shortlist": shortlist_n,
        "fast_top": [
            {"rank": r + 1, "pool_index": i, "metrics": compact(fast_evals[i])}
            for r, i in enumerate(ranked_fast[:min(10, len(ranked_fast))])
        ],
        "train_best": compact(best_eval),
        "holdout_v1": compact(baseline_hold),
        "holdout_candidate": compact(best_hold),
        "duel_vs_v1": compact(duel),
        "best_params": best,
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2, sort_keys=True))
    if improved:
        champion_path.write_text(json.dumps({
            "schema": "KAGGRICULTURE_CHAMPION_V2_FAST",
            "params": best,
            "validation": {
                "train": compact(best_eval),
                "holdout": compact(best_hold),
                "baseline_v1": compact(baseline_hold),
                "duel_vs_v1": compact(duel),
            },
        }, indent=2, sort_keys=True))
    elif not champion_path.exists():
        champion_path.write_text(json.dumps({"schema": "KAGGRICULTURE_CHAMPION_V2_FAST_SEED", "params": chosen}, indent=2, sort_keys=True))

    print(json.dumps({
        "improved_vs_v1": improved,
        "workers": workers,
        "train_best": compact(best_eval),
        "holdout_v1": compact(baseline_hold),
        "holdout_candidate": compact(best_hold),
        "duel_vs_v1": compact(duel),
    }, indent=2))


if __name__ == "__main__":
    main()
