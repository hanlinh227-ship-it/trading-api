"""Build one stdlib-only file; packaging does not authorize submission."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from policy import validate_params
HERE=Path(__file__).resolve().parent


def build(params=None,path=None):
    params=validate_params(params)
    pieces=['# Generated V3 research candidate. NOT SUBMITTED.\n']
    for name in ('incumbent.py','features.py','policy.py'):
        tree=ast.parse((HERE/name).read_text())
        body=[]
        for node in tree.body:
            if isinstance(node,ast.ImportFrom) and node.module in ('__future__','incumbent','features'):continue
            if name=='incumbent.py' and isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('agent','SUBMISSION_PARAMS') for t in node.targets):continue
            body.append(node)
        tree.body=body;pieces.append(ast.unparse(tree))
    pieces.append('EMBEDDED_PARAMS = '+repr(params)+'\n\ndef agent(observation, configuration=None):\n    return decide(observation, configuration or {}, EMBEDDED_PARAMS)\n')
    code='\n\n'.join(pieces)+'\n'
    compile(code,'main.py','exec')
    target=Path(path or HERE/'main.py');target.parent.mkdir(parents=True,exist_ok=True);target.write_text(code)
    return dict(path=str(target),sha256=hashlib.sha256(code.encode()).hexdigest(),params=params,
                submission_performed=False,promotion_status='NOT_AUTHORIZED_BY_PACKAGING')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--params');ap.add_argument('--output',default=str(HERE/'main.py'));a=ap.parse_args()
    params=json.loads(Path(a.params).read_text()) if a.params else None
    if params and 'params' in params:params=params['params']
    print(json.dumps(build(params,a.output),indent=2))
