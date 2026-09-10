"""Fail-closed ladder promotion gate for V5.4 rank-climb research.

Unlike the full-farm campaign gate, this lane allows either three or four quadrants.
The final field must earn its keep in simulation; acreage is not a cosmetic requirement.
"""
import math
from benchmark_v5 import summary
from opponents import SUITE


def gate(train, duel, holdout, final, baseline_holdout, baseline_final, runtime):
    reasons=[]; groups=[train,duel,holdout,final,baseline_holdout,baseline_final]
    for i,r in enumerate(groups):
        try:
            expected={(fam,s,seat) for fam in r['families'] for s in r['seeds'] for seat in (0,1)}
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

    target=int(train['params'].get('land_target_quadrants',4))
    if target not in (3,4): reasons.append('invalid_land_target')
    for r,b,label in ((holdout,baseline_holdout,'holdout'),(final,baseline_final,'final')):
        m,bm=summary(r['rows']),summary(b['rows'])
        if len(r['seeds'])<4 or r['seeds']!=b['seeds']: reasons.append(label+'_seed_pairing')
        if m['mean_margin']<bm['mean_margin']+1000: reasons.append(label+'_mean_edge_too_small')
        if m['mean_money']<bm['mean_money']+1500: reasons.append(label+'_money_edge_too_small')
        if m['p20_margin']<bm['p20_margin']-800: reasons.append(label+'_p20_regression')
        if m['worst_margin']<bm['worst_margin']-1800: reasons.append(label+'_tail_regression')
        if m['catastrophic_rate']>.03125: reasons.append(label+'_catastrophic')
        if m['noop_rate']>0: reasons.append(label+'_unit_noops')
        if m['movement_idle_rate']>.68: reasons.append(label+'_action_waste')
        if m['mean_terminal_unsold_units']>15: reasons.append(label+'_terminal_waste')
        if any(int(x.get('final_unlocked_quadrants',0))<target for x in r['rows']): reasons.append(label+'_land_target_missed')
        success=0
        for fam in SUITE:
            fm=summary([x for x in r['rows'] if x['opponent']==fam])
            if fm['win_rate']>=.5 and fm['mean_margin']>0: success+=1
            if fam=='starter' and fm['win_rate']<.875: reasons.append(label+'_starter')
            if fam=='incumbent' and (fm['win_rate']<.75 or fm['mean_margin']<=0): reasons.append(label+'_incumbent')
        if success<6: reasons.append(label+'_family_weakness')
        for seat in (0,1):
            if summary([x for x in r['rows'] if x['seat']==seat])['win_rate']<.625: reasons.append(label+'_seat')
    dm=summary(duel['rows'])
    if set(duel['families'])!={'incumbent'} or len(duel['seeds'])<4 or dm['win_rate']<.75 or dm['mean_margin']<=1500:
        reasons.append('direct_duel')
    if runtime.get('raw_exec')!='PASS' or runtime.get('official_loader')!='PASS' or runtime.get('episode_equivalence')!='PASS': reasons.append('runtime')
    return dict(
        pass_gate=not reasons,reasons=reasons,threshold_revision='v5.4-rank-livestock-1',submission_performed=False,
        requirements={
            'engine':'1.32.7','land_target':'candidate 3Q/4Q must be reached','direct_v1_win_rate_min':.75,
            'movement_idle_max':.68,'terminal_unsold_mean_max':15,'auto_submit':False,
        },
    )
