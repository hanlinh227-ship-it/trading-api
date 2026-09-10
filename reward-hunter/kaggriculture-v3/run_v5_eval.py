"""CLI wrapper for V5 benchmark_v5.evaluate."""
import argparse, json
from pathlib import Path
from benchmark_v5 import evaluate, save
from opponents import SUITE

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', default='101,103')
    ap.add_argument('--families', default=','.join(SUITE))
    ap.add_argument('--steps', type=int, default=720)
    ap.add_argument('--workers', type=int, default=0)
    ap.add_argument('--params')
    ap.add_argument('--agent-path')
    ap.add_argument('--kind', choices=('v3','incumbent'), default='v3')
    ap.add_argument('--output', required=True)
    a = ap.parse_args()
    p = json.loads(Path(a.params).read_text()) if a.params else None
    if p and 'params' in p:
        p = p['params']
    r = evaluate(
        p,
        tuple(int(x) for x in a.seeds.split(',') if x.strip()),
        tuple(x.strip() for x in a.families.split(',') if x.strip()),
        a.steps,
        a.workers,
        a.kind,
        a.agent_path,
    )
    save(a.output, r)
    print(json.dumps(r['metrics'], indent=2, sort_keys=True))
    if r['metrics']['valid_games'] != r['metrics']['games']:
        raise SystemExit(1)
