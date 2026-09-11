"""V5.9 live cash-gap defense coordinator.

The base controller still owns routing and legality.  This layer is tuned for the canonical
Kaggle live lane and uses only live/public episode state plus our own inventory.  It deliberately
optimizes *realized cash* when the opponent opens a money lead: optional capex is frozen early,
inventory is monetized progressively, and the controller is prevented from mistaking a comeback
for a reason to hold inventory indefinitely.  No simulator-only signal is required at runtime.
"""
from __future__ import annotations

from incumbent import SEED_COST
from features import features
from policy import V3_DEFAULT, validate_params, decide
from economic_reasoning import (
    CROP_PRODUCT,
    MARKET_PARAMS,
    animal_portfolio_score,
    best_crop,
    crop_portfolio_score,
    economic_snapshot,
    sell_decision,
)

ANIMAL_COST={'GOOSE':300,'COW':400,'SHEEP':500}
LAND_COSTS=(1000,2000,4000)
FAST_CASH_CROPS=('WHEAT','CARROT')
PREMIUM_CROPS=('TOMATO','STRAWBERRY','MELON')
FAST_CASH_PRODUCTS=('WHEAT','CARROT','TOMATO','EGG','FERTILIZER')


def _player_money(obs):
    try:
        return float(obs['farms'][int(obs.get('player',0))].get('money',0) or 0)
    except Exception:
        return 0.0


def _cash_defense_tier(f):
    """Severity tier for the observable live money deficit.

    Early small deficits are tolerated because productive setup has value.  Large deficits or
    deficits that persist deeper into the episode escalate much faster.
    """
    gap=float(f.get('gap',0) or 0)
    day=int(f.get('day',0) or 0)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    if gap<=-4500 or (gap<=-3000 and day>=5):return 3
    if gap<=-2500 or (gap<=-1600 and day>=7) or (gap<=-1200 and remaining<240):return 2
    if gap<=-900 or (gap<=-500 and day>=9):return 1
    return 0


def _runtime_params(p,f):
    """Convert capital-heavy defaults into opponent-aware live cash defense.

    Runtime parameters must stay inside the base controller contract.  Deeper reserves that exceed
    the public ``land_buffer`` range are enforced by ``_capital_floor`` instead of leaking invalid
    values into ``validate_params``.
    """
    q=dict(p)
    gap=float(f.get('gap',0) or 0)
    tier=_cash_defense_tier(f)
    opp_hands=int(f.get('opponent_hands',0) or 0)

    # Conservative live baseline.  Three quadrants is the minimum legal target in the base policy;
    # actual expansion is still blocked by _capital_guard whenever the cash race is weak.
    q['target_hands']=min(int(q.get('target_hands',9) or 9),8)
    q['expansion_mode']='balanced'
    q['land_buffer']=max(float(q.get('land_buffer',0) or 0),1050.0)
    q['land_target_quadrants']=3
    q['fill_target']=min(float(q.get('fill_target',.72) or .72),.72)
    q['seed_scale']=min(float(q.get('seed_scale',1.05) or 1.05),1.05)
    q['cow_max']=min(int(q.get('cow_max',3) or 0),3)
    q['sheep_max']=min(int(q.get('sheep_max',1) or 0),1)
    q['goose_max']=0
    q['livestock_start_day']=max(int(q.get('livestock_start_day',4) or 0),4)
    q['livestock_cash_buffer']=max(float(q.get('livestock_cash_buffer',0) or 0),1400.0)
    q['animal_roi_floor']=max(float(q.get('animal_roi_floor',0) or 0),1.00)
    q['feed_carry']=min(int(q.get('feed_carry',4) or 4),4)
    q['sell_batch']=max(int(q.get('sell_batch',8) or 8),8)

    # Do not out-hire a cash-leading opponent.  A single extra hand is enough until the cash race
    # is recovered; recurring labor should not deepen an already negative money gap.
    if gap<800 and opp_hands>0:
        q['target_hands']=min(q['target_hands'],max(5,opp_hands+1))

    if tier>=1:
        q['target_hands']=min(q['target_hands'],7)
        q['land_target_quadrants']=3
        q['land_buffer']=max(q['land_buffer'],1500.0)
        q['fill_target']=min(q['fill_target'],.64)
        q['seed_scale']=min(q['seed_scale'],.90)
        q['cow_max']=min(q['cow_max'],1)
        q['sheep_max']=0
        q['livestock_start_day']=max(q['livestock_start_day'],7)
        q['livestock_cash_buffer']=max(q['livestock_cash_buffer'],1900.0)
        q['animal_roi_floor']=max(q['animal_roi_floor'],1.35)
        q['sell_batch']=max(q['sell_batch'],12)

    if tier>=2:
        q['herd_mode']='none'
        q['cow_max']=0
        q['sheep_max']=0
        q['goose_max']=0
        q['target_hands']=min(q['target_hands'],6)
        q['seed_scale']=min(q['seed_scale'],.74)
        q['fill_target']=min(q['fill_target'],.56)
        q['crop_mode']='grains'
        q['land_buffer']=1600.0
        q['sell_batch']=max(q['sell_batch'],16)

    if tier>=3:
        # Deep-deficit recovery: no speculative scale.  Use existing productive assets and maximize
        # realized cash; the >$3k reserve is enforced by _capital_floor while this public parameter
        # remains within the base controller's validated 0..1600 range.
        q['target_hands']=min(q['target_hands'],5)
        q['seed_scale']=min(q['seed_scale'],.58)
        q['fill_target']=min(q['fill_target'],.48)
        q['land_buffer']=1600.0
        q['sell_batch']=max(q['sell_batch'],24)

    if gap>2500:
        # Protect a live lead rather than recycling it into late speculative capex.
        q['land_buffer']=max(q['land_buffer'],1500.0)
        q['livestock_cash_buffer']=max(q['livestock_cash_buffer'],1700.0)
        q['animal_roi_floor']=max(q['animal_roi_floor'],1.15)
        q['target_hands']=min(q['target_hands'],8)

    # Fail closed at the boundary even if future edits change a tier.  This is deliberately narrow:
    # it normalizes only the two fields that caused the first V5.9 live runtime failure.
    q['land_target_quadrants']=4 if int(q.get('land_target_quadrants',3) or 3)>=4 else 3
    q['land_buffer']=min(1600.0,max(0.0,float(q.get('land_buffer',0) or 0)))
    return validate_params(q)


def validate_live_runtime_contracts():
    """Pure parameter-contract probes used by CI; no simulator or local match is executed."""
    base=validate_params(None)
    probes=(
        {'gap':0,'day':1,'remaining_turns':720,'opponent_hands':5},
        {'gap':-1000,'day':10,'remaining_turns':420,'opponent_hands':7},
        {'gap':-2600,'day':8,'remaining_turns':220,'opponent_hands':8},
        {'gap':-5000,'day':12,'remaining_turns':120,'opponent_hands':9},
        {'gap':3200,'day':8,'remaining_turns':360,'opponent_hands':8},
    )
    for f in probes:
        _runtime_params(base,f)
    return True


def _capital_floor(f,p):
    """Dynamic reserve for optional spend, strengthened by a negative live money gap."""
    base=max(550.0,float(p.get('land_buffer',1050) or 1050)*1.05)
    livestock=float(p.get('livestock_cash_buffer',1400) or 1400)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    gap=float(f.get('gap',0) or 0)
    tier=_cash_defense_tier(f)

    if gap<0:
        base=max(base,1050.0+min(2200.0,abs(gap)*.26))
    if tier>=2:base=max(base,2200.0)
    if tier>=3:base=max(base,3000.0)
    if remaining<240:
        base=max(base,livestock,1000.0)
    elif remaining<420:
        base=max(base,min(livestock,1300.0))
    if float(f.get('productive_utilization',0) or 0)<.42:
        base=max(base,850.0)
    return base


def _capital_guard(order,obs,f,p):
    """Fail-closed filter for new capital commitments in live play."""
    if not isinstance(order,list) or not order:
        return order
    op=order[0]
    money=_player_money(obs)
    reserve=_capital_floor(f,p)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    util=float(f.get('productive_utilization',0) or 0)
    gap=float(f.get('gap',0) or 0)
    hands=int(f.get('hands',0) or 0)
    tier=_cash_defense_tier(f)
    opp_hands=int(f.get('opponent_hands',0) or 0)
    opp_quadrants=int(f.get('opponent_unlocked_quadrants',1) or 1)

    if op=='BUY_SEED' and len(order)>=3:
        crop=order[1];qty=max(0,int(order[2] or 0));unit=float(SEED_COST.get(crop,0) or 0)
        if qty<=0 or unit<=0:return None
        if tier>=1 and crop in ('STRAWBERRY','MELON'):return None
        if tier>=2 and crop not in FAST_CASH_CROPS:return None
        affordable=max(0,int((money-reserve)//unit))
        qty=min(qty,affordable)
        if tier==1:qty=min(qty,6 if crop in FAST_CASH_CROPS else 3)
        elif tier==2:qty=min(qty,5 if crop in FAST_CASH_CROPS else 2)
        elif tier>=3:qty=min(qty,3 if crop in FAST_CASH_CROPS else 1)
        elif gap<0:qty=min(qty,8 if crop in FAST_CASH_CROPS else 4)
        return ['BUY_SEED',crop,qty] if qty>0 else None

    if op=='BUY_ANIMAL' and len(order)>=3:
        animal=order[1];cost=float(ANIMAL_COST.get(animal,0) or 0)
        # New livestock is only allowed from a meaningful cash lead.  Existing animals continue to
        # be serviced, so this does not abandon sunk capital.
        if gap<1200 or tier>0:return None
        if remaining<420 or money-cost<max(reserve,float(p.get('livestock_cash_buffer',1400) or 1400)):
            return None
        return [op,animal,1]

    if op=='BUY_LAND':
        unlocked=max(1,int(f.get('unlocked_quadrants',1) or 1))
        idx=min(len(LAND_COSTS)-1,max(0,unlocked-1));cost=float(LAND_COSTS[idx])
        if unlocked>=3 or tier>0:return None
        # While not leading cash, never scale beyond the opponent's proven footprint.
        if gap<1000 and unlocked>=max(2,opp_quadrants):return None
        if util<.52 and unlocked>=2:return None
        if remaining<480 or money-cost<reserve:return None
        return order

    if op=='HIRE':
        if tier>=3 and hands>=5:return None
        if tier>=2 and hands>=6:return None
        if tier>=1 and hands>=7:return None
        if gap<800 and opp_hands>0 and hands>=opp_hands+1:return None
        if gap>2500 and hands>=8:return None
        if remaining<360 or money<reserve*1.25:return None
        return order

    if op=='BUY_PRODUCT' and len(order)>=3:
        item=order[1]
        if item=='FERTILIZER' and gap<1500:return None
        if tier>=2 and item!='WHEAT':return None
        if money<reserve and item!='WHEAT':return None
        return order

    return order


def _crop_live_score(crop,obs,f,game,p):
    s=crop_portfolio_score(crop,obs,f,game,p)
    tier=_cash_defense_tier(f)
    if tier>=1:
        if crop=='WHEAT':s*=1.45
        elif crop=='CARROT':s*=1.34
        elif crop=='TOMATO':s*=.72
        elif crop=='STRAWBERRY':s*=.40
        elif crop=='MELON':s*=.24
    if tier>=2:
        if crop in FAST_CASH_CROPS:s*=1.40
        else:s*=.28
    if tier>=3:
        if crop=='WHEAT':s*=1.25
        elif crop=='CARROT':s*=1.15
        else:s*=.18
    return s


def _best_live_crop(available,obs,f,game,p):
    choices=[]
    for crop,n in available.items():
        if crop in CROP_PRODUCT and int(n or 0)>0:
            choices.append((_crop_live_score(crop,obs,f,game,p),-SEED_COST[crop],crop))
    if not choices:return None
    choices.sort(reverse=True)
    return choices[0][2] if choices[0][0]>-1e10 else None


def _plant_rewrite(action,seeds,obs,f,game,p):
    if not (isinstance(action,list) and action and action[0]=='PLANT'):
        return action
    original=action[1] if len(action)>1 else None
    available={c:int(seeds.get(c,0) or 0) for c in CROP_PRODUCT}
    chosen=_best_live_crop(available,obs,f,game,p)
    if chosen is None:return action
    original_score=_crop_live_score(original,obs,f,game,p) if original in CROP_PRODUCT else -1e12
    chosen_score=_crop_live_score(chosen,obs,f,game,p)
    crop=chosen if int(available.get(original,0) or 0)<=0 or chosen_score>original_score*1.04 else original
    if crop in available and available[crop]>0:
        seeds[crop]-=1
        return ['PLANT',crop]
    return action


def _rewrite_unit_actions(base,obs,f,game,p):
    seeds=dict(obs.get('private',{}).get('seeds',{}) or {})
    farmer=_plant_rewrite(base.get('farmer',['PASS']),seeds,obs,f,game,p)
    hands=[_plant_rewrite(a,seeds,obs,f,game,p) for a in (base.get('hands',[]) or [])]
    return farmer,hands


def _seed_rewrite(order,obs,f,game,p):
    if not (isinstance(order,list) and len(order)>=3 and order[0]=='BUY_SEED'):return order
    original=order[1];qty=max(1,int(order[2] or 1))
    scored=[(_crop_live_score(c,obs,f,game,p),-SEED_COST[c],c) for c in CROP_PRODUCT]
    scored.sort(reverse=True)
    if not scored:return order
    best_score,_,chosen=scored[0]
    original_score=_crop_live_score(original,obs,f,game,p) if original in CROP_PRODUCT else -1e12
    crop=chosen if best_score>original_score*1.04 else original
    tier=_cash_defense_tier(f)
    if tier>=2 and crop not in FAST_CASH_CROPS:
        crop='WHEAT' if _crop_live_score('WHEAT',obs,f,game,p)>=_crop_live_score('CARROT',obs,f,game,p) else 'CARROT'
    if crop in ('STRAWBERRY','MELON'):qty=min(qty,3)
    elif crop=='TOMATO':qty=min(qty,5)
    else:qty=min(qty,8 if tier==0 else 6)
    return ['BUY_SEED',crop,qty]


def _market_priority(order,obs,f,game,p):
    if not isinstance(order,list) or not order:return -1e12
    op=order[0]
    if op=='SELL' and len(order)>=3:
        item=order[1];current=float(f.get('prices',{}).get(item,1) or 1)
        return 100000.+current
    if op=='HIRE':return 80000.
    if op=='BUY_LAND':return 70000.
    if op=='BUY_PRODUCT':return 60000.
    if op=='BUY_ANIMAL' and len(order)>=2:return 50000.+1000.*animal_portfolio_score(order[1],obs,f,game,p)
    if op=='BUY_SEED':return 40000.
    return 0.


def _sell_view(f):
    """Preserve genuine comeback cash-pressure; neutralize only expansion-only pressure.

    V5.8 incorrectly changed a negative-gap comeback into ``production``.  That disabled the
    cash-pressure branch in ``sell_decision`` exactly when realized cash was needed most.
    """
    out=dict(f)
    tier=_cash_defense_tier(f)
    if tier>0:
        out['regime']='comeback'
    elif f.get('regime')=='expansion':
        out['regime']='production'
    return out


def _recovery_sell_batch(item,units,batch,f):
    """Increase realized cash progressively without blindly dumping premium goods."""
    units=max(0,int(units or 0));batch=max(0,int(batch or 0))
    if units<=0:return 0
    tier=_cash_defense_tier(f)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    if remaining<=72:return units
    if tier<=0:return min(units,batch)

    if tier==1:
        target=max(batch,(units+3)//4)          # about 25%
    elif tier==2:
        target=max(batch,(units+1)//2)          # about 50%
    else:
        target=units if item in FAST_CASH_PRODUCTS else max(batch,(2*units+2)//3)

    # Premium goods still get partial price protection unless the deficit is deep or time is short.
    if item in ('STRAWBERRY','MELON','MILK','WOOL') and tier<3 and remaining>144:
        target=min(target,max(batch,(units+3)//4))
    return min(units,max(1,target))


def _rewrite_market(base_orders,obs,f,game,p):
    rewritten=[];seen_sell=set();shed=dict(obs.get('private',{}).get('shed',{}) or {})
    sf=_sell_view(f)
    for order in base_orders or []:
        if not isinstance(order,list) or not order:continue
        op=order[0];candidate=None
        if op=='SELL' and len(order)>=3:
            item=order[1];qty=max(0,int(order[2] or 0));should,batch,_,_=sell_decision(item,qty,obs,sf,game,p)
            if should and batch>0:
                batch=_recovery_sell_batch(item,qty,batch,f)
                candidate=['SELL',item,qty if f.get('regime') in ('endgame','market_liquidation') else min(qty,batch)]
                seen_sell.add(item)
        elif op=='BUY_SEED':candidate=_seed_rewrite(order,obs,f,game,p)
        elif op=='BUY_ANIMAL' and len(order)>=3:
            animal=order[1]
            if animal_portfolio_score(animal,obs,f,game,p)>0:candidate=[op,animal,1]
        elif op=='BUY_LAND':candidate=order
        else:candidate=order

        candidate=_capital_guard(candidate,obs,f,p)
        if candidate is not None:rewritten.append(candidate)

    # Evaluate every shed line, not only lines already proposed by the base controller.  This lets a
    # live cash deficit turn inventory into money immediately instead of waiting for the base regime.
    for item,n in shed.items():
        if item in seen_sell or item not in MARKET_PARAMS or int(n or 0)<=0:continue
        should,batch,_,_=sell_decision(item,int(n),obs,sf,game,p)
        if should and batch>0:
            batch=_recovery_sell_batch(item,int(n),batch,f)
            rewritten.append(['SELL',item,batch]);seen_sell.add(item)

    decorated=[(_market_priority(o,obs,f,game,p),i,o) for i,o in enumerate(rewritten)]
    decorated.sort(key=lambda x:(x[0],-x[1]),reverse=True)
    return [o for _,_,o in decorated[:10]]


def decide_v57(obs,game,p):
    p=validate_params(p)
    f=features(obs,game)
    rp=_runtime_params(p,f)
    base=decide(obs,game,rp)
    farmer,hands=_rewrite_unit_actions(base,obs,f,game,rp)
    market=_rewrite_market(base.get('market',[]),obs,f,game,rp)
    return {'farmer':farmer,'hands':hands,'market':market}


def make_v57(params=None):
    p=validate_params(params)
    def agent(obs,configuration=None):
        return decide_v57(obs,configuration or {},p)
    return agent


def inspect_economy(obs,configuration=None,params=None):
    """Inspection helper; canonical live execution does not require a simulator."""
    game=configuration or {};p=validate_params(params);f=features(obs,game);rp=_runtime_params(p,f)
    snap=economic_snapshot(obs,f,game,rp)
    snap['live_gap']=float(f.get('gap',0) or 0)
    snap['cash_defense_tier']=_cash_defense_tier(f)
    snap['capital_floor']=_capital_floor(f,rp)
    snap['opponent_hands']=int(f.get('opponent_hands',0) or 0)
    snap['opponent_quadrants']=int(f.get('opponent_unlocked_quadrants',1) or 1)
    snap['runtime_params']=rp
    return snap
