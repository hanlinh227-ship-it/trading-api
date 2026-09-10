import sys,json
from pathlib import Path
sys.path.insert(0,str(Path('reward-hunter/kaggriculture-v3').resolve()))
from benchmark import evaluate,save
from opponents import SUITE
from package_submission import build
from raw_exec_test import check
from promotion import gate
root=Path('reward-hunter/kaggriculture-v3');out=root/'reports/pinned-study-002'
p=json.loads((root/'reports/study-001/search.json').read_text())['best_params']
def ev(label,seeds,families=SUITE,kind='v3',path=None):
 r=evaluate(p,seeds,families,720,4,kind,path);save(out/(label+'.json'),r);print(label,json.dumps(r['metrics']),flush=True);return r
train=ev('train',[50101,50103]);duel=ev('duel',[50211,50223,50227,50229],('incumbent',))
h=ev('holdout',[507001,507003,507007,507013]);bh=ev('baseline-holdout',[507001,507003,507007,507013],kind='incumbent')
f=ev('final',[509001,509007,509011,509013]);bf=ev('baseline-final',[509001,509007,509011,509013],kind='incumbent')
package=build(p,out/'candidate-main.py');runtime=check(out/'candidate-main.py')
packaged=ev('packaged',[50997],('incumbent',),path=str((out/'candidate-main.py').resolve()))
source=ev('source',[50997],('incumbent',))
keys=('margin','valid','statuses','efficiency','terminal_unsold_units')
runtime['episode_equivalence']='PASS' if all(all(a[k]==b[k] for k in keys) for a,b in zip(packaged['rows'],source['rows'])) and all(r['valid'] for r in packaged['rows']) else 'FAIL'
decision=gate(train,duel,h,f,bh,bf,runtime)
r=dict(best_params=p,promotion=decision,runtime=runtime,package=package,duel=duel['metrics'],holdout=h['metrics'],final=f['metrics'],baseline_holdout=bh['metrics'],baseline_final=bf['metrics'],provenance=train['provenance'],submission_performed=False,note='Frozen study-001 parameters; no candidate selection or retuning on these fresh canonical-wheel seeds. Only DROP destination legality made compatible with pinned wheel before testing.')
save(out/'validation.json',r)
if decision['pass_gate']:save(out/'champion.json',dict(params=p,evidence=r))
print(json.dumps(r,indent=2),flush=True)
