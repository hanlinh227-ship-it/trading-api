"""Fail-closed promotion; frozen thresholds are not tuned after holdout."""
import math
from benchmark import summary, digest
from opponents import SUITE


def gate(train,duel,holdout,final,baseline_holdout,baseline_final,runtime):
    reasons=[]
    groups=[train,duel,holdout,final,baseline_holdout,baseline_final]
    for i,r in enumerate(groups):
        try:
            rows=r['rows'];expected={(f,s,seat) for f in r['families'] for s in r['seeds'] for seat in (0,1)}
            got=[(x['opponent'],x['seed'],x['seat']) for x in rows]
            if not expected or len(got)!=len(set(got)) or set(got)!=expected:reasons.append(f'coverage_{i}')
            if r['steps']!=720 or any(x['steps']!=720 for x in rows):reasons.append(f'partial_horizon_{i}')
            if not all(x['valid'] and x['statuses']==['DONE','DONE'] and math.isfinite(x['margin']) for x in rows):reasons.append(f'invalid_{i}')
            if i<4 and (r['params']!=train['params'] or r['provenance']['code_hash']!=train['provenance']['code_hash']):reasons.append(f'candidate_identity_{i}')
            if r['provenance']['simulator_hash']!=train['provenance']['simulator_hash']:reasons.append(f'simulator_{i}')
            if i in (2,3,4,5) and set(r['families'])!=set(SUITE):reasons.append(f'meta_coverage_{i}')
            if r['kind'] != ('incumbent' if i >= 4 else 'v3'):reasons.append(f'policy_kind_{i}')
        except (KeyError,TypeError,ValueError):reasons.append(f'malformed_{i}')
    if reasons:return dict(pass_gate=False,reasons=reasons)
    if set(train['seeds']) & (set(holdout['seeds'])|set(final['seeds'])) or set(holdout['seeds']) & set(final['seeds']):reasons.append('seed_leakage')
    if set(duel['seeds']) & (set(holdout['seeds'])|set(final['seeds'])):reasons.append('duel_holdout_leakage')
    for r,b,label in ((holdout,baseline_holdout,'holdout'),(final,baseline_final,'final')):
        if len(r['seeds'])<4:reasons.append(label+'_too_few_seeds')
        if r['seeds']!=b['seeds']:reasons.append(label+'_unpaired_baseline')
        m=summary(r['rows']);bm=summary(b['rows'])
        if m['mean_margin']<bm['mean_margin'] or m['p20_margin']<bm['p20_margin']-1000 or m['worst_margin']<bm['worst_margin']-2000:reasons.append(label+'_regression')
        if m['noop_rate']>0:reasons.append(label+'_illegal_unit_actions')
        successful=0
        for f in SUITE:
            fm=summary([x for x in r['rows'] if x['opponent']==f])
            if fm['win_rate']>=.5 and fm['mean_margin']>0:successful+=1
            if f=='starter' and fm['win_rate']<.875:reasons.append(label+'_starter')
            if f=='incumbent' and (fm['win_rate']<.625 or fm['mean_margin']<=0):reasons.append(label+'_incumbent')
        if successful<6:reasons.append(label+'_family_weakness')
        for seat in (0,1):
            sm=summary([x for x in r['rows'] if x['seat']==seat])
            if sm['win_rate']<.5:reasons.append(label+'_seat')
    dm=summary(duel['rows'])
    if set(duel['families'])!={'incumbent'} or len(duel['seeds'])<4 or dm['win_rate']<.625 or dm['mean_margin']<=0:reasons.append('direct_duel')
    if runtime.get('raw_exec')!='PASS' or runtime.get('official_loader')!='PASS' or runtime.get('episode_equivalence')!='PASS':reasons.append('runtime')
    return dict(pass_gate=not reasons,reasons=reasons,threshold_revision='v3-fixed-1',submission_performed=False)
