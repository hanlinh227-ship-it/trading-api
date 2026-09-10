"""Official episodes, paired seeds/seats, with V4 expansion/utilization telemetry."""
import argparse
import contextlib
import hashlib
import importlib
import io
import json
import math
import os
import statistics
import subprocess
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from policy import make_v3, validate_params
from opponents import opponent, SUITE

HERE = Path(__file__).resolve().parent
PINNED_SIMULATOR_HASH = '9741c0470a8db98a70644491d5121ae6295413343d1a08ef9fcee35e0b76f2c5'


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def provenance(params):
    import kaggle_environments
    engine = importlib.import_module('kaggle_environments.envs.kaggriculture.kaggriculture')
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.glob('*.py'))}
    return dict(
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        code_hash=digest(files),
        source_files=files,
        parameter_hash=digest(params),
        source_worktree_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=HERE, text=True).strip()),
        simulator_version=kaggle_environments.__version__,
        simulator_hash=hashlib.sha256(Path(engine.__file__).read_bytes()).hexdigest(),
    )


def cpu_limit(requested=0):
    count = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else os.cpu_count() or 1
    try:
        quota, period = Path('/sys/fs/cgroup/cpu.max').read_text().split()
        if quota != 'max':
            count = min(count, max(1, math.floor(int(quota) / int(period))))
    except (OSError, ValueError):
        pass
    return max(1, min(requested or 4, count, 8))


def _tracking_agent(base_agent, tracker):
    def wrapped(obs, configuration=None):
        me = obs['farms'][obs['player']]
        unlocked = len(me.get('unlocked_quadrants', ['NW']))
        owned = sum(t != 'LOCKED' for row in me['tiles'] for t in row)
        planted = sum(isinstance(t, dict) and t.get('kind') == 'PLANT' for row in me['tiles'] for t in row)
        util = planted / max(1, owned)
        tracker['max_unlocked'] = max(tracker['max_unlocked'], unlocked)
        tracker['peak_utilization'] = max(tracker['peak_utilization'], util)
        if unlocked >= 4:
            if tracker['full_unlock_step'] is None:
                tracker['full_unlock_step'] = int(obs.get('step', 0))
            tracker['full_farm_peak_utilization'] = max(tracker['full_farm_peak_utilization'], util)
        try:
            return base_agent(obs, configuration)
        except TypeError:
            return base_agent(obs)
    return wrapped


def play(job):
    params, family, seed, seat, steps, kind, agent_path = job
    from kaggle_environments import make
    engine = importlib.import_module('kaggle_environments.envs.kaggriculture.kaggriculture')
    original = engine._apply_unit_action
    counts = [dict(actions=0, moves=0, passes=0, noops=0), dict(actions=0, moves=0, passes=0, noops=0)]
    player = [-1]

    def audited(farm, private, idx, action, *args, **kwargs):
        if idx == 0:
            player[0] = (player[0] + 1) % 2
        c = counts[player[0]]
        c['actions'] += 1
        op = action[0] if isinstance(action, list) and action else 'INVALID'
        c['moves'] += op in ('NORTH', 'SOUTH', 'EAST', 'WEST')
        c['passes'] += op == 'PASS'
        x, y = engine._farmer_position(farm, idx)

        def snapshot():
            return repr((engine._farmer_position(farm, idx), farm['tiles'][y][x], private))

        before = snapshot() if op != 'PASS' else None
        result = original(farm, private, idx, action, *args, **kwargs)
        if op != 'PASS' and before == snapshot():
            c['noops'] += 1
        return result

    engine._apply_unit_action = audited
    tracker = dict(full_unlock_step=None, max_unlocked=1, peak_utilization=0.0, full_farm_peak_utilization=0.0)
    row = dict(
        seed=seed, seat=seat, opponent=family, steps=steps, kind=kind, valid=False,
        candidate_money=None, opponent_money=None, margin=None, error=None,
    )
    try:
        if agent_path:
            candidate = agent_path
        else:
            base = opponent('incumbent') if kind == 'incumbent' else make_v3(params)
            candidate = _tracking_agent(base, tracker)
        agents = [candidate, opponent(family)] if seat == 0 else [opponent(family), candidate]
        env = make('kaggriculture', configuration={'seed': int(seed), 'episodeSteps': steps}, debug=True)
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            env.run(agents)
        statuses = [str(s.status) for s in env.state]
        row['statuses'] = statuses
        row['valid'] = statuses == ['DONE', 'DONE']
        if not row['valid']:
            row['error'] = captured.getvalue()[-4000:]
        farms = env.state[0].observation.farms
        mine = farms[seat]
        row['candidate_money'] = float(mine['money'])
        row['opponent_money'] = float(farms[1 - seat]['money'])
        row['margin'] = row['candidate_money'] - row['opponent_money']
        row['rewards'] = [s.reward for s in env.state]
        for key in ('candidate_money', 'opponent_money', 'margin'):
            if not math.isfinite(row[key]):
                raise ValueError('nonfinite outcome')
        row['efficiency'] = counts[seat]
        row['opponent_efficiency'] = counts[1 - seat]
        private = env.state[seat].observation.private
        row['terminal_unsold_units'] = sum(private['shed'].values()) + sum(sum(i.values()) for i in private['inventories'])
        final_owned = sum(t != 'LOCKED' for r in mine['tiles'] for t in r)
        final_plants = sum(isinstance(t, dict) and t.get('kind') == 'PLANT' for r in mine['tiles'] for t in r)
        final_animals = sum(isinstance(t, dict) and 'animal' in t for r in mine['tiles'] for t in r)
        row['final_unlocked_quadrants'] = len(mine.get('unlocked_quadrants', ['NW']))
        row['final_owned_tiles'] = final_owned
        row['final_plants'] = final_plants
        row['final_animals'] = final_animals
        row['full_unlock_step'] = tracker['full_unlock_step']
        row['full_unlock_day'] = (tracker['full_unlock_step'] / 24.0) if tracker['full_unlock_step'] is not None else None
        row['peak_utilization'] = tracker['peak_utilization']
        row['full_farm_peak_utilization'] = tracker['full_farm_peak_utilization']
    except Exception as exc:
        row['valid'] = False
        row['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        engine._apply_unit_action = original
    return row


def summary(rows):
    n = len(rows)
    if not n:
        return dict(games=0, valid_games=0, win_rate=0, mean_margin=None, p20_margin=None, worst_margin=None, objective=-1e9)
    valid = [r for r in rows if r['valid']]
    margins = sorted(r['margin'] for r in valid)
    wins = sum(r['margin'] > 0 for r in valid)
    ties = sum(r['margin'] == 0 for r in valid)
    if not margins:
        return dict(games=n, valid_games=0, win_rate=0, mean_margin=None, p20_margin=None, worst_margin=None, objective=-1e9)
    mean = statistics.mean(margins)
    p20 = margins[int(.2 * (len(margins) - 1))]
    worst = margins[0]
    actions = sum(r['efficiency']['actions'] for r in valid)
    noop = sum(r['efficiency']['noops'] for r in valid) / max(1, actions)
    waste = sum(r['efficiency']['passes'] + r['efficiency']['moves'] for r in valid) / max(1, actions)
    tail = sum(m < -5000 for m in margins) / n
    full_unlock_rate = sum(r.get('final_unlocked_quadrants', 0) >= 4 for r in valid) / n
    unlock_days = [r.get('full_unlock_day') if r.get('full_unlock_day') is not None else (r['steps'] / 24.0 + 1) for r in valid]
    mean_full_unlock_day = statistics.mean(unlock_days) if unlock_days else None
    peak_util = statistics.mean(r.get('peak_utilization', 0.0) for r in valid)
    full_peak = statistics.mean(r.get('full_farm_peak_utilization', 0.0) for r in valid)
    expansion_bonus = 55 * full_unlock_rate + 24 * full_peak
    unlock_penalty = 0 if mean_full_unlock_day is None else min(35, 2.5 * mean_full_unlock_day)
    objective = (
        600 * (wins + .5 * ties) / n
        + 120 * math.tanh(mean / 5000)
        + 100 * math.tanh(p20 / 5000)
        + 40 * math.tanh(worst / 5000)
        - 2000 * (n - len(valid)) / n
        - 150 * noop
        - 20 * waste
        - 150 * tail
        + expansion_bonus
        - unlock_penalty
    )
    return dict(
        games=n, valid_games=len(valid), wins=wins, ties=ties, win_rate=wins / n,
        mean_margin=mean, median_margin=statistics.median(margins), p20_margin=p20, worst_margin=worst,
        mean_money=statistics.mean(r['candidate_money'] for r in valid), noop_rate=noop,
        movement_idle_rate=waste, catastrophic_rate=tail, objective=objective,
        full_unlock_rate=full_unlock_rate, mean_full_unlock_day=mean_full_unlock_day,
        mean_peak_utilization=peak_util, mean_full_farm_peak_utilization=full_peak,
    )


def evaluate(params=None, seeds=(101,), families=SUITE, steps=720, workers=0, kind='v3', agent_path=None):
    params = validate_params(params)
    actual = provenance(params)['simulator_hash']
    if actual != PINNED_SIMULATOR_HASH:
        raise ValueError('Simulator source mismatch: install pinned official wheel in a clean venv')
    seeds, families = tuple(seeds), tuple(families)
    if not seeds or len(set(seeds)) != len(seeds) or not families or len(set(families)) != len(families):
        raise ValueError('empty/duplicate evaluation axes')
    jobs = [(params, f, s, seat, steps, kind, str(agent_path) if agent_path else None) for f in families for s in seeds for seat in (0, 1)]
    count = cpu_limit(workers)
    if count == 1:
        rows = list(map(play, jobs))
    else:
        with ProcessPoolExecutor(max_workers=count) as pool:
            rows = list(pool.map(play, jobs))
    return dict(
        metrics=summary(rows),
        by_family={f: summary([r for r in rows if r['opponent'] == f]) for f in families},
        by_seat={str(s): summary([r for r in rows if r['seat'] == s]) for s in (0, 1)},
        rows=rows, seeds=list(seeds), families=list(families), steps=steps, workers=count,
        params=params, kind=kind, provenance=provenance(params),
        timestamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
    )


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + '\n')
    tmp.replace(path)


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='101,103')
    ap.add_argument('--families', default=','.join(SUITE))
    ap.add_argument('--steps', type=int, default=720)
    ap.add_argument('--workers', type=int, default=0)
    ap.add_argument('--params')
    ap.add_argument('--agent-path')
    ap.add_argument('--kind', choices=('v3', 'incumbent'), default='v3')
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    p = json.loads(Path(a.params).read_text()) if a.params else None
    if p and 'params' in p:
        p = p['params']
    r = evaluate(p, tuple(map(int, a.seeds.split(','))), tuple(a.families.split(',')), a.steps, a.workers, a.kind, a.agent_path)
    save(a.output, r)
    print(json.dumps(r['metrics'], indent=2))
    if r['metrics']['valid_games'] != r['metrics']['games']:
        raise SystemExit(1)
