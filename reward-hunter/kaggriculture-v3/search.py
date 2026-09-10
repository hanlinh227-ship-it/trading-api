"""V4 staged search: cheap screens first, full canonical promotion only at the end."""
import argparse
import json
import random
from pathlib import Path
from benchmark import evaluate, save, digest
from policy import V3_DEFAULT
from opponents import SUITE
from package_submission import build
from raw_exec_test import check
from promotion import gate


def candidates(n, seed):
    rng = random.Random(seed)
    base = dict(V3_DEFAULT)
    pool = [base]
    presets = [
        {'expansion_mode': 'max', 'land_buffer': 80, 'fill_target': .92, 'fill_priority': 96., 'crop_mode': 'fast_cash'},
        {'expansion_mode': 'fast', 'land_buffer': 120, 'fill_target': .94, 'fill_priority': 102., 'target_hands': 13},
        {'expansion_mode': 'fast', 'land_buffer': 260, 'fill_target': .88, 'fill_priority': 82., 'crop_mode': 'demand'},
        {'expansion_mode': 'balanced', 'land_buffer': 220, 'fill_target': .90, 'fill_priority': 90., 'crop_mode': 'balanced'},
        {'crop_mode': 'fast_cash', 'seed_scale': 1.8, 'target_hands': 13},
        {'crop_mode': 'demand', 'seed_scale': 1.6, 'distance_cost': 7.0},
        {'crop_mode': 'grains', 'expansion_mode': 'max', 'land_buffer': 50, 'fill_priority': 100.},
        {'distance_cost': 6.0, 'fill_priority': 94., 'target_hands': 14},
        {'distance_cost': 13.0, 'fill_target': .86, 'seed_scale': 1.25},
        {'fill_target': .96, 'fill_priority': 108., 'seed_scale': 1.9, 'target_hands': 14},
        {'harvest_wait': True, 'expansion_mode': 'fast', 'crop_mode': 'demand'},
    ]
    for patch in presets:
        p = dict(base)
        p.update(patch)
        if p not in pool:
            pool.append(p)
        if len(pool) >= n:
            return pool[:n]

    mutable = ('distance_cost', 'target_hands', 'crop_mode', 'expansion_mode', 'land_buffer', 'fill_target', 'fill_priority', 'seed_scale')
    while len(pool) < n:
        p = dict(rng.choice(pool))
        key = rng.choice(mutable)
        if key == 'distance_cost':
            p[key] = rng.choice((5., 7., 9., 12., 16.))
        elif key == 'target_hands':
            p[key] = rng.choice((9, 11, 12, 13, 14))
        elif key == 'crop_mode':
            p[key] = rng.choice(('balanced', 'fast_cash', 'demand', 'grains'))
        elif key == 'expansion_mode':
            p[key] = rng.choice(('balanced', 'fast', 'max'))
        elif key == 'land_buffer':
            p[key] = rng.choice((50, 100, 180, 260, 400))
        elif key == 'fill_target':
            p[key] = rng.choice((.80, .86, .90, .94, .97))
        elif key == 'fill_priority':
            p[key] = rng.choice((70., 82., 90., 100., 112.))
        elif key == 'seed_scale':
            p[key] = rng.choice((1.0, 1.25, 1.5, 1.8, 2.1))
        if p not in pool:
            pool.append(p)
    return pool


def run(out, n=16, workers=0, smoke=False, study_seed=4049):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    if (out / 'search.json').exists():
        raise ValueError('Use a new output directory/study; final holdout already consumed')

    train_seeds = [101, 103]
    duel_seeds = [211, 223, 227, 229]
    hold = [7001, 7003, 7007, 7013]
    final = [9001, 9007, 9011, 9013]
    if study_seed != 4049:
        blocks = random.Random(study_seed).sample(range(100000, 2000000000), 14)
        train_seeds, duel_seeds, hold, final = blocks[:2], blocks[2:6], blocks[6:10], blocks[10:14]

    pool = candidates(n, study_seed)
    history = []

    def ev(p, ss, fs, label, steps=720, kind='v3', path=None):
        r = evaluate(p, ss, fs, steps, workers, kind, path)
        save(out / (label + '.json'), r)
        print(label, json.dumps(r['metrics']), flush=True)
        return r

    if smoke:
        r = ev(pool[0], train_seeds[:1], ('starter', 'incumbent'), 'smoke', 120)
        result = dict(smoke=True, metrics=r['metrics'], submission_performed=False)
        save(out / 'search.json', result)
        return result

    # Successive-halving style funnel. A/B are intentionally cheap and never count as
    # promotion evidence. C is the first full-horizon train block and becomes frozen.
    stages = [
        ('A', train_seeds[:1], ('starter', 'incumbent'), 240, max(6, n // 2)),
        ('B', train_seeds, ('starter', 'incumbent', 'early_sell', 'expansion'), 480, max(3, n // 4)),
        ('C', train_seeds, SUITE, 720, 1),
    ]
    train = None
    for stage, ss, fs, steps, keep in stages:
        ranked = []
        for p in pool:
            r = ev(p, ss, fs, stage + '-' + digest(p)[:10], steps)
            ranked.append((r['metrics']['objective'], p, r))
        ranked.sort(key=lambda x: (x[0], digest(x[1])), reverse=True)
        history.append(dict(stage=stage, steps=steps, ranking=[dict(params=p, metrics=r['metrics']) for _, p, r in ranked]))
        pool = [p for _, p, _ in ranked[:keep]]
        if stage == 'C':
            train = ranked[0][2]

    best = pool[0]
    duel = ev(best, duel_seeds, ('incumbent',), 'D-duel')
    h = ev(best, hold, SUITE, 'E-holdout')
    bh = ev(best, hold, SUITE, 'E-baseline', kind='incumbent')
    f = ev(best, final, SUITE, 'F-final')
    bf = ev(best, final, SUITE, 'F-baseline', kind='incumbent')

    package = build(best, out / 'candidate-main.py')
    runtime = check(out / 'candidate-main.py')
    packaged = ev(best, [997], ('incumbent',), 'packaged', path=out / 'candidate-main.py')
    source = ev(best, [997], ('incumbent',), 'source')
    keys = ('margin', 'valid', 'statuses', 'efficiency', 'terminal_unsold_units')
    runtime['episode_equivalence'] = (
        'PASS'
        if all(all(a[k] == b[k] for k in keys) for a, b in zip(packaged['rows'], source['rows']))
        and all(r['valid'] for r in packaged['rows'])
        else 'FAIL'
    )
    decision = gate(train, duel, h, f, bh, bf, runtime)
    result = dict(
        best_params=best,
        stages=history,
        promotion=decision,
        runtime=runtime,
        package=package,
        duel=duel['metrics'],
        holdout=h['metrics'],
        final=f['metrics'],
        baseline_holdout=bh['metrics'],
        baseline_final=bf['metrics'],
        provenance=train['provenance'],
        study_seed=study_seed,
        study_seed_sets=dict(train=train_seeds, duel=duel_seeds, holdout=hold, final=final),
        full_farm_target=dict(all_games_unlock=True, mean_unlock_day_max=12.0, peak_utilization_min=.68),
        submission_performed=False,
    )
    save(out / 'search.json', result)
    if decision['pass_gate']:
        save(out / 'champion.json', dict(params=best, evidence=result))
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', required=True)
    ap.add_argument('--candidates', type=int, default=16)
    ap.add_argument('--workers', type=int, default=0)
    ap.add_argument('--smoke', action='store_true')
    ap.add_argument('--study-seed', type=int, default=4049)
    a = ap.parse_args()
    if not 2 <= a.candidates <= 64:
        ap.error('candidates must be 2..64')
    run(a.output, a.candidates, a.workers, a.smoke, a.study_seed)
