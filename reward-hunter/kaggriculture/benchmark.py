from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from kaggle_environments import make

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("reward_agent", HERE / "main.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def final_money(env, player):
    try:
        obs = env.steps[-1][player].observation
        farms = obs["farms"] if isinstance(obs, dict) else obs.farms
        farm = farms[player]
        return float(farm["money"] if isinstance(farm, dict) else farm.money)
    except Exception:
        try:
            state = env.state[player]
            obs = state.observation
            farms = obs["farms"] if isinstance(obs, dict) else obs.farms
            farm = farms[player]
            return float(farm["money"] if isinstance(farm, dict) else farm.money)
        except Exception:
            return 0.0


def play(agent0, agent1, seed, episode_steps=720):
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": int(episode_steps), "seed": int(seed)},
        debug=False,
    )
    env.run([agent0, agent1])
    m0, m1 = final_money(env, 0), final_money(env, 1)
    s0, s1 = env.steps[-1][0].status, env.steps[-1][1].status
    return {
        "seed": int(seed),
        "money0": m0,
        "money1": m1,
        "margin0": m0 - m1,
        "status0": str(s0),
        "status1": str(s1),
        "valid": str(s0) == "DONE" and str(s1) == "DONE",
    }


def evaluate(params=None, seeds=(20260805, 20260811, 20260829), opponents=("starter",), episode_steps=720):
    candidate = MOD.make_agent(params or MOD.DEFAULT_PARAMS)
    rows = []
    for opponent in opponents:
        for seed in seeds:
            a = play(candidate, opponent, seed, episode_steps)
            a.update({"opponent": opponent, "seat": 0, "candidate_money": a["money0"], "opponent_money": a["money1"], "candidate_margin": a["margin0"]})
            rows.append(a)
            b = play(opponent, candidate, seed, episode_steps)
            b.update({"opponent": opponent, "seat": 1, "candidate_money": b["money1"], "opponent_money": b["money0"], "candidate_margin": -b["margin0"]})
            rows.append(b)
    valid = [r for r in rows if r["valid"]]
    wins = sum(r["candidate_margin"] > 0 for r in valid)
    ties = sum(r["candidate_margin"] == 0 for r in valid)
    mean_margin = sum(r["candidate_margin"] for r in valid) / max(1, len(valid))
    mean_money = sum(r["candidate_money"] for r in valid) / max(1, len(valid))
    score = (wins + ties * 0.5) / max(1, len(valid)) * 1000.0 + mean_margin / 1000.0 + mean_money / 100000.0
    return {
        "games": len(rows),
        "valid_games": len(valid),
        "wins": wins,
        "ties": ties,
        "win_rate": wins / max(1, len(valid)),
        "mean_margin": mean_margin,
        "mean_money": mean_money,
        "objective": score,
        "rows": rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="20260805,20260811,20260829")
    ap.add_argument("--opponents", default="starter")
    ap.add_argument("--steps", type=int, default=720)
    ap.add_argument("--params")
    ap.add_argument("--output")
    args = ap.parse_args()
    params = MOD.DEFAULT_PARAMS
    if args.params:
        data = json.loads(Path(args.params).read_text())
        params = data.get("params", data)
    result = evaluate(
        params=params,
        seeds=tuple(int(x) for x in args.seeds.split(",") if x.strip()),
        opponents=tuple(x.strip() for x in args.opponents.split(",") if x.strip()),
        episode_steps=args.steps,
    )
    text = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text)
    print(text)
    if result["valid_games"] != result["games"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
