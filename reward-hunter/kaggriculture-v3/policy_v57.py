"""V6.0 live anti-snowball cash-gap coordinator.

The base controller still owns routing and legality. This layer is for the canonical Kaggle live
lane only. It reacts earlier to a negative live money gap, blocks optional capex before a deficit
snowballs, monetizes inventory sooner, and protects a recovered lead from being recycled into late
speculative spending. No simulator-only signal is required at runtime.
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
    """Escalate early enough that a small live deficit cannot compound into a blowout."""
    gap=float(f.get('gap',0) or 0)
    day=int(f.get('day',0) or 0)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    if gap<=-3000 or (gap<=-2200 and day>=4) or (gap<=-1600 and remaining<160):return 3
    if gap<=-1400 or (gap<=-900 and day>=6) or (gap<=-700 and remaining<300):return 2
    if gap<=-450 or (gap<=-250 and day>=8):return 1
    return 0


def _runtime_params(p,f):
    """Convert capital-heavy defaults into early opponent-aware live cash defense."""
    q=dict(p)
    gap=float(f.get('gap',0) or 0)
    tier=_cash_defense_tier(f)
    opp_hands=int(f.get('opponent_hands',0) or 0)

    # Safer live baseline: scale has to be earned by a clear cash lead.
    q['target_hands']=min(int(q.get('target_hands',8) or 8),7)
    q['expansion_mode']='balanced'
    q['land_buffer']=max(float(q.get('land_buffer',0) or 0),1250.0)
    q['land_target_quadrants']=3
    q['fill_target']=min(float(q.get('fill_target',.66) or .66),.66)
    q['seed_scale']=min(float(q.get('seed_scale',.92) or .92),.92)
    q['cow_max']=min(int(q.get('cow_max',2) or 0),2)
    q['sheep_max']=0
    q['goose_max']=0
    q['livestock_start_day']=max(int(q.get('livestock_start_day',6) or 0),6)
    q['livestock_cash_buffer']=max(float(q.get('livestock_cash_buffer',0) or 0),1800.0)
    q['animal_roi_floor']=max(float(q.get('animal_roi_floor',0) or 0),1.25)
    q['feed_carry']=min(int(q.get('feed_carry',4) or 4),4)
    q['sell_batch']=max(int(q.get('sell_batch',10) or 10),10)

    # Never buy labor just to imitate a cash-leading opponent.
    if gap<1200 and opp_hands>0:
        q['target_hands']=min(q['target_hands'],max(5,opp_hands))

    if tier>=1:
        q['target_hands']=min(q['target_hands'],6)
        q['land_buffer']=1600.0
        q['fill_target']=min(q['fill_target'],.58)
        q['seed_scale']=min(q['seed_scale'],.78)
        q['herd_mode']='none'
        q['cow_max']=0
        q['sheep_max']=0
        q['goose_max']=0
        q['livestock_start_day']=max(q['livestock_start_day'],9)
        q['livestock_cash_buffer']=max(q['livestock_cash_buffer'],2200.0)
        q['animal_roi_floor']=max(q['animal_roi_floor'],1.60)
        q['sell_batch']=max(q['sell_batch'],16)

    if tier>=2:
        q['target_hands']=min(q['target_hands'],5)
        q['seed_scale']=min(q['seed_scale'],.58)
        q['fill_target']=min(q['fill_target'],.48)
        q['crop_mode']='grains'
        q['land_buffer']=1600.0
        q['sell_batch']=max(q['sell_batch'],24)

    if tier>=3:
        q['target_hands']=min(q['target_hands'],5)
        q['seed_scale']=min(q['seed_scale'],.42)
        q['fill_target']=min(q['fill_target'],.40)
        q['crop_mode']='grains'
        q['sell_batch']=max(q['sell_batch'],32)

    if gap>2500:
        # A lead is an asset: do not throw it away with late recurring costs.
        q['land_buffer']=max(q['land_buffer'],1500.0)
        q['livestock_cash_buffer']=max(q['livestock_cash_buffer'],2100.0)
        q['animal_roi_floor']=max(q['animal_roi_floor'],1.45)
        q['target_hands']=min(q['target_hands'],7)

    q['land_target_quadrants']=4 if int(q.get('land_target_quadrants',3) or 3)>=4 else 3
    q['land_buffer']=min(1600.0,max(0.0,float(q.get('land_buffer',0) or 0)))
    return validate_params(q)


def validate_live_runtime_contracts():
    """Pure contract probes only; no local match or simulator is executed."""
    base=validate_params(None)
    probes=(
        {'gap':0,'day':1,'remaining_turns':720,'opponent_hands':5},
        {'gap':-500,'day':3,'remaining_turns':620,'opponent_hands':6},
        {'gap':-1000,'day':6,'remaining_turns':420,'opponent_hands':7},
        {'gap':-1800,'day':5,'remaining_turns':300,'opponent_hands':8},
        {'gap':-3200,'day':7,'remaining_turns':160,'opponent_hands':9},
        {'gap':3200,'day':8,'remaining_turns':360,'opponent_hands':8},
    )
    for f in probes:
        _runtime_params(base,f)
    return True


def _capital_floor(f,p):
    """Cash reserve rises immediately with a negative live money gap."""
    base=max(700.0,float(p.get('land_buffer',1250) or 1250)*1.05)
    livestock=float(p.get('livestock_cash_buffer',1800) or 1800)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    gap=float(f.get('gap',0) or 0)
    tier=_cash_defense_tier(f)

    if gap<0:
        base=max(base,1400.0+min(2600.0,abs(gap)*.35))
    if tier>=1:base=max(base,1800.0)
    if tier>=2:base=max(base,2600.0)
    if tier>=3:base=max(base,3600.0)
    if remaining<240:
        base=max(base,livestock,1600.0)
    elif remaining<420:
        base=max(base,min(livestock,1700.0))
    if float(f.get('productive_utilization',0) or 0)<.42:
        base=max(base,1100.0)
    return base


def _capital_guard(order,obs,f,p):
    """Fail closed on optional spend as soon as the live cash race turns against us."""
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
        if tier>=1 and crop in PREMIUM_CROPS:return None
        if tier>=2 and crop not in FAST_CASH_CROPS:return None
        affordable=max(0,int((money-reserve)//unit))
        qty=min(qty,affordable)
        if tier==1:qty=min(qty,4 if crop in FAST_CASH_CROPS else 2)
        elif tier==2:qty=min(qty,3 if crop in FAST_CASH_CROPS else 1)
        elif tier>=3:qty=min(qty,2 if crop in FAST_CASH_CROPS else 1)
        elif gap<0:qty=min(qty,5 if crop in FAST_CASH_CROPS else 2)
        else:qty=min(qty,7)
        return ['BUY_SEED',crop,qty] if qty>0 else None

    if op=='BUY_ANIMAL' and len(order)>=3:
        animal=order[1];cost=float(ANIMAL_COST.get(animal,0) or 0)
        if gap<2500 or tier>0:return None
        if remaining<520 or money-cost<max(reserve,float(p.get('livestock_cash_buffer',1800) or 1800)):
            return None
        return [op,animal,1]

    if op=='BUY_LAND':
        unlocked=max(1,int(f.get('unlocked_quadrants',1) or 1))
        idx=min(len(LAND_COSTS)-1,max(0,unlocked-1));cost=float(LAND_COSTS[idx])
        if unlocked>=2:return None
        if tier>0 or gap<1800:return None
        if unlocked>=max(2,opp_quadrants) and gap<2500:return None
        if util<.60:return None
        if remaining<560 or money-cost<reserve:return None
        return order

    if op=='HIRE':
        if tier>=1 and hands>=5:return None
        if gap<=0 and hands>=5:return None
        if gap<1200 and opp_hands>0 and hands>=max(5,opp_hands):return None
        if gap<2500 and hands>=6:return None
        if gap>=2500 and hands>=7:return None
        if remaining<420 or money<reserve*1.35:return None
        return order

    if op=='BUY_PRODUCT' and len(order)>=3:
        item=order[1]
        if item=='FERTILIZER' and gap<2500:return None
        if tier>=1 and item!='WHEAT':return None
        if tier>=2 and item!='WHEAT':return None
        if money<reserve and item!='WHEAT':return None
        return order

    return order


def _crop_live_score(crop,obs,f,game,p):
    s=crop_portfolio_score(crop,obs,f,game,p)
    tier=_cash_defense_tier(f)
    if tier>=1:
        if crop=='WHEAT':s*=1.70
        elif crop=='CARROT':s*=1.55
        elif crop=='TOMATO':s*=.58
        elif crop=='STRAWBERRY':s*=.24
        elif crop=='MELON':s*=.12
    if tier>=2:
        if crop in FAST_CASH_CROPS:s*=1.55
        else:s*=.18
    if tier>=3:
        if crop=='WHEAT':s*=1.35
        elif crop=='CARROT':s*=1.20
        else:s*=.10
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
    crop=chosen if int(available.get(original,0) or 0)<=0 or chosen_score>original_score*1.02 else original
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
    crop=chosen if best_score>original_score*1.02 else original
    tier=_cash_defense_tier(f)
    if tier>=2 and crop not in FAST_CASH_CROPS:
        crop='WHEAT' if _crop_live_score('WHEAT',obs,f,game,p)>=_crop_live_score('CARROT',obs,f,game,p) else 'CARROT'
    if crop in ('STRAWBERRY','MELON'):qty=min(qty,2)
    elif crop=='TOMATO':qty=min(qty,3)
    else:qty=min(qty,7 if tier==0 else (4 if tier==1 else 3))
    return ['BUY_SEED',crop,qty]


def _market_priority(order,obs,f,game,p):
    if not isinstance(order,list) or not order:return -1e12
    op=order[0]
    if op=='SELL' and len(order)>=3:
        item=order[1];current=float(f.get('prices',{}).get(item,1) or 1)
        return 100000.+current
    if op=='BUY_SEED':return 50000.
    if op=='HIRE':return 40000.
    if op=='BUY_PRODUCT':return 30000.
    if op=='BUY_ANIMAL' and len(order)>=2:return 20000.+1000.*animal_portfolio_score(order[1],obs,f,game,p)
    if op=='BUY_LAND':return 10000.
    return 0.


def _sell_view(f):
    out=dict(f)
    tier=_cash_defense_tier(f)
    if tier>0:
        out['regime']='comeback'
    elif f.get('regime')=='expansion':
        out['regime']='production'
    return out


def _recovery_sell_batch(item,units,batch,f):
    """Realize cash earlier when the live gap starts widening."""
    units=max(0,int(units or 0));batch=max(0,int(batch or 0))
    if units<=0:return 0
    tier=_cash_defense_tier(f)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    gap=float(f.get('gap',0) or 0)
    if remaining<=120:return units
    if tier<=0:
        if gap<0 and item in FAST_CASH_PRODUCTS:return min(units,max(batch,(units+3)//4))
        return min(units,batch)

    if tier==1:
        target=max(batch,(2*units+4)//5)          # about 40%
    elif tier==2:
        target=max(batch,(3*units+3)//4)          # about 75%
    else:
        target=units if item in FAST_CASH_PRODUCTS else max(batch,(5*units+5)//6)

    if item in ('STRAWBERRY','MELON','MILK','WOOL') and tier==1 and remaining>180:
        target=min(target,max(batch,(units+2)//3))
    return min(units,max(1,target))


def _rewrite_market(base_orders,obs,f,game,p):
    rewritten=[];seen_sell=set();shed=dict(obs.get('private',{}).get('shed',{}) or {})
    sf=_sell_view(f);tier=_cash_defense_tier(f)
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

    # A deficit should immediately expose inventory to the sell controller, not wait for base regime.
    for item,n in shed.items():
        if item in seen_sell or item not in MARKET_PARAMS or int(n or 0)<=0:continue
        should,batch,_,_=sell_decision(item,int(n),obs,sf,game,p)
        if should and batch>0:
            batch=_recovery_sell_batch(item,int(n),batch,f)
            rewritten.append(['SELL',item,batch]);seen_sell.add(item)

    # In deep recovery, market bandwidth belongs to cash realization and essential fast-cycle seed only.
    if tier>=2:
        rewritten=[o for o in rewritten if o and (o[0]=='SELL' or (o[0]=='BUY_SEED' and len(o)>1 and o[1] in FAST_CASH_CROPS))]

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