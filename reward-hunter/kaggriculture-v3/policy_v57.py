"""V6.2 production-first live cash-defense coordinator.

The proven V5.7 production controller remains the operating base. V6.0 reacted too aggressively
to small cash deficits and could starve the farm of productive capacity. This version keeps the
strong production/price logic intact and adds only staged, evidence-based defense when a live money
deficit is material. No simulator-only signal is required at runtime.
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
FAST_CASH_CROPS=('WHEAT','CARROT','TOMATO')
FAST_CASH_PRODUCTS=('WHEAT','CARROT','TOMATO','EGG','FERTILIZER')
PREMIUM_CROPS=('STRAWBERRY','MELON')


def _player_money(obs):
    try:
        return float(obs['farms'][int(obs.get('player',0))].get('money',0) or 0)
    except Exception:
        return 0.0


def _cash_defense_tier(f):
    """Escalate only after the live deficit is material; never punish normal early investment."""
    gap=float(f.get('gap',0) or 0)
    day=int(f.get('day',0) or 0)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    if gap<=-4500 or (gap<=-3200 and day>=8) or (gap<=-2600 and remaining<150):
        return 3
    if gap<=-2500 or (gap<=-1800 and day>=10) or (gap<=-1500 and remaining<240):
        return 2
    if gap<=-1200 or (gap<=-800 and remaining<180):
        return 1
    return 0


def _capital_floor(f,p):
    """Preserve enough cash for production without freezing the farm's growth engine."""
    base=max(180.0,float(p.get('land_buffer',80) or 80)*1.25)
    livestock=float(p.get('livestock_cash_buffer',350) or 350)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    gap=float(f.get('gap',0) or 0)
    tier=_cash_defense_tier(f)

    if gap<0:
        base=max(base,350.0+min(650.0,abs(gap)*.12))
    if tier>=1:base=max(base,700.0)
    if tier>=2:base=max(base,1050.0)
    if tier>=3:base=max(base,1550.0)
    if remaining<240:
        base=max(base,min(max(livestock,550.0),1200.0))
    elif remaining<420:
        base=max(base,min(livestock,700.0))
    if float(f.get('productive_utilization',0) or 0)<.42:
        base=max(base,450.0)
    return base


def _capital_guard(order,obs,f,p):
    """Block speculative capex under a real deficit while keeping the production cycle funded."""
    if not isinstance(order,list) or not order:
        return order
    op=order[0]
    money=_player_money(obs)
    reserve=_capital_floor(f,p)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    util=float(f.get('productive_utilization',0) or 0)
    tier=_cash_defense_tier(f)
    hands=int(f.get('hands',0) or 0)

    if op=='BUY_SEED' and len(order)>=3:
        crop=order[1];qty=max(0,int(order[2] or 0));unit=float(SEED_COST.get(crop,0) or 0)
        if qty<=0 or unit<=0:return None
        affordable=max(0,int((money-reserve)//unit))
        qty=min(qty,affordable)
        if tier==1 and crop in PREMIUM_CROPS:
            qty=min(qty,3)
        elif tier==2:
            if crop in PREMIUM_CROPS:return None
            qty=min(qty,8 if crop in FAST_CASH_CROPS else 4)
        elif tier>=3:
            if crop not in FAST_CASH_CROPS:return None
            qty=min(qty,6)
        return ['BUY_SEED',crop,qty] if qty>0 else None

    if op=='BUY_ANIMAL' and len(order)>=3:
        animal=order[1];cost=float(ANIMAL_COST.get(animal,0) or 0)
        if tier>=1:return None
        if remaining<300 or money-cost<max(reserve,float(p.get('livestock_cash_buffer',350) or 350)):
            return None
        return [op,animal,1]

    if op=='BUY_LAND':
        unlocked=max(1,int(f.get('unlocked_quadrants',1) or 1))
        idx=min(len(LAND_COSTS)-1,max(0,unlocked-1));cost=float(LAND_COSTS[idx])
        if tier>=1:return None
        if unlocked>=3 and util<.62:return None
        if remaining<300 or money-cost<reserve:return None
        return order

    if op=='HIRE':
        if tier>=3 and hands>=5:return None
        if tier>=2 and hands>=7:return None
        if remaining<240 or money<reserve*1.35:return None
        return order

    return order


def _plant_rewrite(action,seeds,obs,f,game,p):
    if not (isinstance(action,list) and action and action[0]=='PLANT'):
        return action
    original=action[1] if len(action)>1 else None
    available={c:int(seeds.get(c,0) or 0) for c in CROP_PRODUCT}
    chosen=best_crop(available,obs,f,game,p)
    if chosen is None:return action
    original_score=crop_portfolio_score(original,obs,f,game,p) if original in CROP_PRODUCT else -1e12
    chosen_score=crop_portfolio_score(chosen,obs,f,game,p)
    crop=chosen if int(available.get(original,0) or 0)<=0 or chosen_score>original_score*1.06 else original
    if crop in available and available[crop]>0:
        seeds[crop]-=1
        return ['PLANT',crop]
    return action


def _rewrite_unit_actions(base,obs,f,game,p):
    seeds=dict(obs.get('private',{}).get('seeds',{}) or {})
    farmer=_plant_rewrite(base.get('farmer',['PASS']),seeds,obs,f,game,p)
    hands=[_plant_rewrite(a,seeds,obs,f,game,p) for a in (base.get('hands',[]) or [])]
    return farmer,hands


def _crop_score(crop,obs,f,game,p):
    score=crop_portfolio_score(crop,obs,f,game,p)
    tier=_cash_defense_tier(f)
    if tier>=2:
        if crop=='WHEAT':score*=1.16
        elif crop=='CARROT':score*=1.12
        elif crop=='TOMATO':score*=1.05
        elif crop in PREMIUM_CROPS:score*=.82
    if tier>=3:
        if crop in FAST_CASH_CROPS:score*=1.12
        elif crop in PREMIUM_CROPS:score*=.70
    return score


def _seed_rewrite(order,obs,f,game,p):
    if not (isinstance(order,list) and len(order)>=3 and order[0]=='BUY_SEED'):
        return order
    original=order[1];qty=max(1,int(order[2] or 1))
    scored=[(_crop_score(crop,obs,f,game,p),-SEED_COST[crop],crop) for crop in CROP_PRODUCT]
    scored.sort(reverse=True)
    if not scored:return order
    best_score,_,chosen=scored[0]
    original_score=_crop_score(original,obs,f,game,p) if original in CROP_PRODUCT else -1e12
    crop=chosen if best_score>original_score*1.08 else original
    if crop in PREMIUM_CROPS:qty=min(qty,6)
    elif crop in ('TOMATO','CARROT'):qty=min(qty,10)
    else:qty=min(qty,14)
    return ['BUY_SEED',crop,qty]


def _market_priority(order,obs,f,game,p):
    if not isinstance(order,list) or not order:return -1e12
    op=order[0]
    if op=='SELL' and len(order)>=3:
        item=order[1];current=float(f.get('prices',{}).get(item,1) or 1)
        return 100000.+current
    # Keep the production cycle funded before optional expansion.
    if op=='BUY_SEED':return 85000.
    if op=='HIRE':return 75000.
    if op=='BUY_PRODUCT':return 65000.
    if op=='BUY_ANIMAL' and len(order)>=2:return 55000.+1000.*animal_portfolio_score(order[1],obs,f,game,p)
    if op=='BUY_LAND':return 45000.
    return 0.


def _sell_view(f):
    out=dict(f)
    if _cash_defense_tier(f)>0:
        out['regime']='comeback'
    elif f.get('regime')=='expansion':
        out['regime']='production'
    return out


def _recovery_sell_batch(item,units,batch,f):
    units=max(0,int(units or 0));batch=max(0,int(batch or 0))
    if units<=0:return 0
    tier=_cash_defense_tier(f)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    if remaining<=72:return units
    if tier<=0:return min(units,batch)
    if tier==1:
        target=max(batch,(units+2)//3)
    elif tier==2:
        target=max(batch,(units+1)//2)
    else:
        target=units if item in FAST_CASH_PRODUCTS else max(batch,(2*units+2)//3)
    if item in ('STRAWBERRY','MELON','MILK','WOOL') and tier<3 and remaining>144:
        target=min(target,max(batch,(units+3)//4))
    return min(units,max(1,target))


def _rewrite_market(base_orders,obs,f,game,p):
    rewritten=[];seen_sell=set();shed=dict(obs.get('private',{}).get('shed',{}) or {})
    sell_f=_sell_view(f)
    for order in base_orders or []:
        if not isinstance(order,list) or not order:continue
        op=order[0];candidate=None
        if op=='SELL' and len(order)>=3:
            item=order[1];qty=max(0,int(order[2] or 0))
            should,batch,_,_=sell_decision(item,qty,obs,sell_f,game,p)
            if should and batch>0:
                batch=_recovery_sell_batch(item,qty,batch,f)
                candidate=['SELL',item,qty if f.get('regime') in ('endgame','market_liquidation') else min(qty,batch)]
                seen_sell.add(item)
        elif op=='BUY_SEED':candidate=_seed_rewrite(order,obs,f,game,p)
        elif op=='BUY_ANIMAL' and len(order)>=3:
            animal=order[1]
            if animal_portfolio_score(animal,obs,f,game,p)>0:candidate=[op,animal,1]
        elif op=='BUY_LAND':
            if not (int(f.get('unlocked_quadrants',1) or 1)>=3 and float(f.get('productive_utilization',0) or 0)<.62 and float(f.get('remaining_turns',0) or 0)<360):
                candidate=order
        else:candidate=order
        candidate=_capital_guard(candidate,obs,f,p)
        if candidate is not None:rewritten.append(candidate)

    for item,n in shed.items():
        if item in seen_sell or item not in MARKET_PARAMS or int(n or 0)<=0:continue
        should,batch,_,_=sell_decision(item,int(n),obs,sell_f,game,p)
        if should and batch>0:
            batch=_recovery_sell_batch(item,int(n),batch,f)
            rewritten.append(['SELL',item,batch]);seen_sell.add(item)

    decorated=[(_market_priority(o,obs,f,game,p),i,o) for i,o in enumerate(rewritten)]
    decorated.sort(key=lambda x:(x[0],-x[1]),reverse=True)
    return [o for _,_,o in decorated[:10]]


def validate_live_runtime_contracts():
    """Pure threshold sanity checks; no simulator or local match is executed."""
    probes=(
        ({'gap':0,'day':1,'remaining_turns':720},0),
        ({'gap':-900,'day':4,'remaining_turns':500},0),
        ({'gap':-1300,'day':5,'remaining_turns':500},1),
        ({'gap':-2600,'day':6,'remaining_turns':300},2),
        ({'gap':-4700,'day':8,'remaining_turns':160},3),
    )
    for f,expected in probes:
        if _cash_defense_tier(f)!=expected:
            raise AssertionError((f,_cash_defense_tier(f),expected))
    return True


def decide_v57(obs,game,p):
    p=validate_params(p)
    # Preserve the proven production baseline. Defense is applied only to last-mile market choices.
    base=decide(obs,game,p)
    f=features(obs,game)
    farmer,hands=_rewrite_unit_actions(base,obs,f,game,p)
    market=_rewrite_market(base.get('market',[]),obs,f,game,p)
    return {'farmer':farmer,'hands':hands,'market':market}


def make_v57(params=None):
    p=validate_params(params)
    def agent(obs,configuration=None):
        return decide_v57(obs,configuration or {},p)
    return agent


def inspect_economy(obs,configuration=None,params=None):
    """Inspection helper; canonical live execution does not require a simulator."""
    game=configuration or {};p=validate_params(params);f=features(obs,game)
    snap=economic_snapshot(obs,f,game,p)
    snap['live_gap']=float(f.get('gap',0) or 0)
    snap['cash_defense_tier']=_cash_defense_tier(f)
    snap['capital_floor']=_capital_floor(f,p)
    return snap
