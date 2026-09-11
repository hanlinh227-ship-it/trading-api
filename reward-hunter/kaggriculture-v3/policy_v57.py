"""V5.8 live money-defense coordinator.

The base controller still owns routing and legality.  This layer is deliberately tuned for the
canonical Kaggle live lane: it reacts to the observable money gap inside the live episode instead
of blindly repeating a capital-heavy plan.  No simulator-only signal is required at runtime.
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


def _player_money(obs):
    try:
        return float(obs['farms'][int(obs.get('player',0))].get('money',0) or 0)
    except Exception:
        return 0.0


def _runtime_params(p,f):
    """Convert the old capital-heavy defaults into a live cash-first policy.

    The observable money gap is the strongest control signal.  Negative gap progressively removes
    optional capex, while a lead is protected instead of being recycled into unnecessary growth.
    Existing animals/crops are still serviced by the routing layer; only *new* commitments shrink.
    """
    q=dict(p)

    # Live baseline: three quadrants, moderate labor and a small herd are enough until live evidence
    # proves that more capex is paying back.  This directly addresses repeated money-gap regression.
    q['target_hands']=min(int(q.get('target_hands',9) or 9),9)
    q['expansion_mode']='balanced'
    q['land_buffer']=max(float(q.get('land_buffer',0) or 0),900.0)
    q['land_target_quadrants']=3
    q['fill_target']=min(float(q.get('fill_target',.74) or .74),.74)
    q['seed_scale']=min(float(q.get('seed_scale',1.10) or 1.10),1.10)
    q['cow_max']=min(int(q.get('cow_max',4) or 0),4)
    q['sheep_max']=min(int(q.get('sheep_max',2) or 0),2)
    q['goose_max']=0
    q['livestock_start_day']=max(int(q.get('livestock_start_day',3) or 0),3)
    q['livestock_cash_buffer']=max(float(q.get('livestock_cash_buffer',0) or 0),1200.0)
    q['animal_roi_floor']=max(float(q.get('animal_roi_floor',0) or 0),.80)
    q['feed_carry']=min(int(q.get('feed_carry',4) or 4),4)
    q['sell_batch']=max(int(q.get('sell_batch',8) or 8),8)

    gap=float(f.get('gap',0) or 0)
    if gap < -1000:
        q['target_hands']=min(q['target_hands'],8)
        q['land_buffer']=max(q['land_buffer'],1300.0)
        q['fill_target']=min(q['fill_target'],.68)
        q['seed_scale']=min(q['seed_scale'],.95)
        q['cow_max']=min(q['cow_max'],2)
        q['sheep_max']=min(q['sheep_max'],1)
        q['livestock_start_day']=max(q['livestock_start_day'],5)
        q['livestock_cash_buffer']=max(q['livestock_cash_buffer'],1600.0)
        q['animal_roi_floor']=max(q['animal_roi_floor'],1.20)

    if gap < -3000:
        # Emergency recovery: stop opening new livestock exposure and make the farm cash-cycle first.
        # Existing livestock is still fed/cared/harvested by the base task planner.
        q['herd_mode']='none'
        q['cow_max']=0
        q['sheep_max']=0
        q['goose_max']=0
        q['target_hands']=min(q['target_hands'],7)
        q['seed_scale']=min(q['seed_scale'],.82)
        q['fill_target']=min(q['fill_target'],.62)
        q['crop_mode']='grains'
        q['land_buffer']=max(q['land_buffer'],1800.0)
        q['sell_batch']=max(q['sell_batch'],10)

    if gap > 2500:
        # Protect a live lead.  Do not convert a winning cash position into late speculative capex.
        q['land_buffer']=max(q['land_buffer'],1400.0)
        q['livestock_cash_buffer']=max(q['livestock_cash_buffer'],1500.0)
        q['animal_roi_floor']=max(q['animal_roi_floor'],1.00)
        q['target_hands']=min(q['target_hands'],8)

    return validate_params(q)


def _capital_floor(f,p):
    """Dynamic reserve for optional spend, strengthened by a negative live money gap."""
    base=max(450.0,float(p.get('land_buffer',900) or 900)*1.05)
    livestock=float(p.get('livestock_cash_buffer',1200) or 1200)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    gap=float(f.get('gap',0) or 0)

    if gap<0:
        base=max(base,900.0+min(1500.0,abs(gap)*.20))
    if gap<-3000:
        base=max(base,1800.0)
    if remaining < 240:
        base=max(base,livestock,800.0)
    elif remaining < 420:
        base=max(base,min(livestock,1100.0))
    if float(f.get('productive_utilization',0) or 0)<.42:
        base=max(base,700.0)
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

    if op=='BUY_SEED' and len(order)>=3:
        crop=order[1];qty=max(0,int(order[2] or 0));unit=float(SEED_COST.get(crop,0) or 0)
        if qty<=0 or unit<=0:return None
        if gap<-1500 and crop in ('STRAWBERRY','MELON'):
            return None
        if gap<-3000 and crop not in FAST_CASH_CROPS:
            return None
        affordable=max(0,int((money-reserve)//unit))
        qty=min(qty,affordable)
        if gap<0:
            qty=min(qty,8 if crop in FAST_CASH_CROPS else 4)
        return ['BUY_SEED',crop,qty] if qty>0 else None

    if op=='BUY_ANIMAL' and len(order)>=3:
        animal=order[1];cost=float(ANIMAL_COST.get(animal,0) or 0)
        # Do not add livestock while losing the observable cash race.
        if gap<0:
            return None
        if remaining<360 or money-cost<max(reserve,float(p.get('livestock_cash_buffer',1200) or 1200)):
            return None
        return [op,animal,1]

    if op=='BUY_LAND':
        unlocked=max(1,int(f.get('unlocked_quadrants',1) or 1))
        idx=min(len(LAND_COSTS)-1,max(0,unlocked-1));cost=float(LAND_COSTS[idx])
        # Never buy the fourth quadrant in this live revision.  When behind, buy no optional land.
        if unlocked>=3 or gap<0:
            return None
        if util<.48 and unlocked>=2:
            return None
        if remaining<420 or money-cost<reserve:
            return None
        return order

    if op=='HIRE':
        # Labor is a recurring opportunity cost.  Freeze headcount quickly when the gap deteriorates.
        if gap<-3000 and hands>=6:return None
        if gap<0 and hands>=7:return None
        if gap>2500 and hands>=8:return None
        if remaining<300 or money<reserve*1.20:return None
        return order

    if op=='BUY_PRODUCT' and len(order)>=3:
        item=order[1]
        # Existing animals may still need wheat rescue, but do not buy discretionary fertilizer
        # while the cash gap is negative.
        if item=='FERTILIZER' and gap<1000:
            return None
        if money<reserve and item!='WHEAT':
            return None
        return order

    return order


def _crop_live_score(crop,obs,f,game,p):
    s=crop_portfolio_score(crop,obs,f,game,p)
    gap=float(f.get('gap',0) or 0)
    if gap<-1000:
        if crop=='WHEAT':s*=1.38
        elif crop=='CARROT':s*=1.30
        elif crop=='TOMATO':s*=.78
        elif crop=='STRAWBERRY':s*=.48
        elif crop=='MELON':s*=.30
    if gap<-3000:
        if crop in FAST_CASH_CROPS:s*=1.35
        else:s*=.35
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
    if chosen is None:
        return action
    original_score=_crop_live_score(original,obs,f,game,p) if original in CROP_PRODUCT else -1e12
    chosen_score=_crop_live_score(chosen,obs,f,game,p)
    if int(available.get(original,0) or 0)<=0 or chosen_score>original_score*1.04:
        crop=chosen
    else:
        crop=original
    if crop in available and available[crop]>0:
        seeds[crop]-=1
        return ['PLANT',crop]
    return action


def _rewrite_unit_actions(base,obs,f,game,p):
    seeds=dict(obs.get('private',{}).get('seeds',{}) or {})
    farmer=_plant_rewrite(base.get('farmer',['PASS']),seeds,obs,f,game,p)
    hands=[]
    for a in base.get('hands',[]) or []:
        hands.append(_plant_rewrite(a,seeds,obs,f,game,p))
    return farmer,hands


def _seed_rewrite(order,obs,f,game,p):
    if not (isinstance(order,list) and len(order)>=3 and order[0]=='BUY_SEED'):
        return order
    original=order[1];qty=max(1,int(order[2] or 1))
    scored=[]
    for crop in CROP_PRODUCT:
        scored.append((_crop_live_score(crop,obs,f,game,p),-SEED_COST[crop],crop))
    scored.sort(reverse=True)
    if not scored:return order
    best_score,_,chosen=scored[0]
    original_score=_crop_live_score(original,obs,f,game,p) if original in CROP_PRODUCT else -1e12
    if best_score>original_score*1.04:crop=chosen
    else:crop=original
    gap=float(f.get('gap',0) or 0)
    if gap<-3000 and crop not in FAST_CASH_CROPS:
        crop='WHEAT' if _crop_live_score('WHEAT',obs,f,game,p)>=_crop_live_score('CARROT',obs,f,game,p) else 'CARROT'
    if crop in ('STRAWBERRY','MELON'):qty=min(qty,4)
    elif crop=='TOMATO':qty=min(qty,6)
    else:qty=min(qty,10)
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
    if op=='BUY_ANIMAL' and len(order)>=2:
        return 50000.+1000.*animal_portfolio_score(order[1],obs,f,game,p)
    if op=='BUY_SEED':return 40000.
    return 0.


def _sell_view(f):
    """Prevent comeback from being interpreted as permission to panic-sell premium inventory."""
    if float(f.get('gap',0) or 0)<0 and f.get('regime') in ('comeback','expansion'):
        out=dict(f);out['regime']='production';return out
    return f


def _rewrite_market(base_orders,obs,f,game,p):
    rewritten=[];seen_sell=set();shed=dict(obs.get('private',{}).get('shed',{}) or {})
    sf=_sell_view(f)
    for order in base_orders or []:
        if not isinstance(order,list) or not order:continue
        op=order[0]
        candidate=None
        if op=='SELL' and len(order)>=3:
            item=order[1];qty=max(0,int(order[2] or 0));decision=sell_decision(item,qty,obs,sf,game,p)
            should,batch,_,_=decision
            if should and batch>0:
                candidate=['SELL',item,min(qty,batch) if f.get('regime') not in ('endgame','market_liquidation') else qty];seen_sell.add(item)
        elif op=='BUY_SEED':
            candidate=_seed_rewrite(order,obs,f,game,p)
        elif op=='BUY_ANIMAL' and len(order)>=3:
            animal=order[1]
            if animal_portfolio_score(animal,obs,f,game,p)>0:
                candidate=[op,animal,1]
        elif op=='BUY_LAND':
            candidate=order
        else:
            candidate=order

        candidate=_capital_guard(candidate,obs,f,p)
        if candidate is not None:
            rewritten.append(candidate)

    for item,n in shed.items():
        if item in seen_sell or item not in MARKET_PARAMS or int(n or 0)<=0:continue
        should,batch,_,_=sell_decision(item,int(n),obs,sf,game,p)
        if should and batch>0:rewritten.append(['SELL',item,batch]);seen_sell.add(item)

    decorated=[(_market_priority(o,obs,f,game,p),i,o) for i,o in enumerate(rewritten)]
    decorated.sort(key=lambda x:(x[0],-x[1]),reverse=True)
    return [o for _,_,o in decorated[:10]]


def decide_v57(obs,game,p):
    p=validate_params(p)
    # Read the live state first, then shrink/expand risk for this exact turn.
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
    snap['runtime_params']=rp
    return snap
