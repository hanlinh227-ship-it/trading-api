"""Raw exec without __file__, no local reads/network/env; official callable discovery."""
import ast
import builtins
import hashlib
import json
from pathlib import Path
from unittest.mock import patch


def check(path):
    code=Path(path).read_text();tree=ast.parse(code)
    for n in ast.walk(tree):
        if isinstance(n,(ast.Import,ast.ImportFrom)):
            names=[x.name.split('.')[0] for x in n.names] if isinstance(n,ast.Import) else [n.module]
            if any(x not in ('copy','math') for x in names):raise AssertionError('non-whitelisted runtime import')
        if isinstance(n,ast.Name) and n.id in ('__file__','open','eval','exec','__import__'):raise AssertionError('runtime dependency')
    from kaggle_environments import make
    from kaggle_environments.agent import build_agent
    e=make('kaggriculture',configuration={'seed':771,'episodeSteps':720});e.reset(2)
    obs=e.state[0].observation
    def denied(*a,**k):raise AssertionError('runtime attempted file access')
    ns={}
    with patch.object(builtins,'open',denied):
        exec(compile(code,'main.py','exec'),ns)
        assert '__file__' not in ns
        expected=ns['agent'](obs,e.configuration)
    # Build via official source-string contract, not only our named entrypoint.
    official,_=build_agent(code,{},'kaggriculture')
    actual=official(obs,e.configuration)
    assert actual==expected, 'official callable discovery selected wrong function'
    assert set(actual)=={'farmer','hands','market'}
    return dict(raw_exec='PASS',official_loader='PASS',sha256=hashlib.sha256(code.encode()).hexdigest())

if __name__=='__main__':
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('path',nargs='?',default=str(Path(__file__).with_name('main.py')));a=ap.parse_args();print(json.dumps(check(a.path),indent=2))
