"""Fail-closed V5 promotion gate: economy, expansion, livestock/crop logistics and runtime safety."""
import math
from benchmark_v5 import summary
from opponents import SUITE


def gate(train,duel,holdout,final,baseline_holdout,baseline_final,runtime):
    reasons=[]; groups=[train,duel,holdout,final,baseline_holdout,baseline_final]
    for i,r in enumerate(groups):
        try:
            expected={(f,s,seat) for f in r['families'] for s in r['seeds'] for seat in (0,1)}
            got=[(x['opponent'],x['seed'],x['seat']) for x in r['rows']]
            if not expected or len(got)!=len(set(got)) or set(got)!=expected: reasons.append(f'coverage_{i}')
            if r['steps']!=720 or any(x['steps']!=720 for x in r['rows']): reasons.append(f'partial_horizon_{i}')
            if not all(x.get('valid') and x.get('statuses')==['DONE','DONE'] and math.isfinite(x['margin']) for x in r['rows']): reasons.append(f'invalid_{i}')
            if r['provenance']['simulator_version']!='1.32.7': reasons.append(f'engine_version_{i}')
            if r['provenance']['simulator_hash']!=train['provenance']['simulator_hash']: reasons.append(f'engine_hash_{i}')
            if i<4 and (r['params']!=train['params'] or r['provenance']['code_hash']!=train['provenance']['code_hash']): reasons.append(f'candidate_identity_{i}')
        except (KeyError,TypeError,ValueError): reasons.append(f'malformed_{i}')
    if reasons:return dict(pass_gate=False,reasons=reasons,submission_performed=False)
    if set(train['seeds']) & (set(holdout['seeds'])|set(final['seeds'])) or set(holdout['seeds']) & set(final['seeds']): reasons.append('seed_leakage')
    if set(duel['seeds']) & (set(holdout['seeds'])|set(final['seeds'])): reasons.append('duel_leakage')

    for r,b,label in ((holdout,baseline_holdout,'holdout'),(final,baseline_final,'final')):
        m,bm=summary(r['rows']),summary(b['rows'])
        if len(r['seeds'])<4 or r['seeds']!=b['seeds']: reasons.append(label+'_seed_pairing')
        if m['mean_margin']<bm['mean_margin']: reasons.append(label+'_mean_regression')
        if m['p20_margin']<bm['p20_margin']-1200: reasons.append(label+'_p20_regression')
        if m['worst_margin']<bm['worst_margin']-2500: reasons.append(label+'_tail_regression')
        if m['noop_rate']>0: reasons.append(label+'_unit_noops')
        if m['full_unlock_rate']<1.0: reasons.append(label+'_not_full_farm')
        if m['mean_full_unlock_day']>12.0: reasons.append(label+'_unlock_too_slow')
        if m['mean_full_farm_peak_productive_utilization']<.60: reasons.append(label+'_underutilized')
        if m['mean_terminal_unsold_units']>8: reasons.append(label+'_terminal_waste')
        success=0
        for f in SUITE:
            fm=summary([x for x in r['rows'] if x['opponent']==f])
            if fm['win_rate']>=.5 and fm['mean_margin']>0: success+=1
            if f=='starter' and fm['win_rate']<.875: reasons.append(label+'_starter')
            if f=='incumbent' and (fm['win_rate']<.625 or fm['mean_margin']<=0): reasons.append(label+'_incumbent')
        if success<6: reasons.append(label+'_family_weakness')
        for seat in (0,1):
            if summary([x for x in r['rows'] if x['seat']==seat])['win_rate']<.5: reasons.append(label+'_seat')
    dm=summary(duel['rows'])
    if set(duel['families'])!={'incumbent'} or len(duel['seeds'])<4 or dm['win_rate']<.625 or dm['mean_margin']<=0: reasons.append('direct_duel')
    if runtime.get('raw_exec')!='PASS' or runtime.get('official_loader')!='PASS' or runtime.get('episode_equivalence')!='PASS': reasons.append('runtime')
    return dict(pass_gate=not reasons,reasons=reasons,threshold_revision='v5-mixed-economy-1',submission_performed=False,
                requirements={'engine':'1.32.7','full_unlock_rate':1.0,'mean_unlock_day_max':12.0,'productive_utilization_min':.60,'terminal_unsold_mean_max':8})
