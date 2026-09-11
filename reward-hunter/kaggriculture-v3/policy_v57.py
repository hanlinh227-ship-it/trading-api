"""V5.7 runtime production/price coordinator.

The proven V5.x controller remains the operational base.  This layer does not replace its
routing or safety logic; it improves the *economic choice* at the last responsible moment using
current public town/market state.  That makes the farm capable of changing crop choice and sale
timing when the shop draw or shared market changes instead of replaying one profitable-looking
configuration forever.
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


def _player_money(obs):
    try:
        return float(obs['farms'][int(obs.get('player',0))].get('money',0) or 0)
    except Exception:
        return 0.0


def _capital_floor(f,p):
    """Dynamic reserve used only for discretionary spend, never for selling/harvesting.

    The floor grows when the controller is already under cash pressure or late in the game.
    This prevents a locally attractive expansion purchase from creating a capital regression.
    """
    base=max(180.0,float(p.get('land_buffer',80) or 80)*1.25)
    livestock=float(p.get('livestock_cash_buffer',350) or 350)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    if remaining < 240:
        base=max(base,livestock,500.0)
    elif remaining < 420:
        base=max(base,min(livestock,650.0))
    if float(f.get('productive_utilization',0) or 0)<.42:
        base=max(base,450.0)
    return base


def _capital_guard(order,obs,f,p):
    """Fail-closed filter for optional capital deployment.

    It deliberately leaves SELL and operational market actions untouched.  For seed purchases it
    reduces quantity rather than blindly cancelling, so production can continue while preserving
    enough cash to avoid high-water regression.
    """
    if not isinstance(order,list) or not order:
        return order
    op=order[0]
    money=_player_money(obs)
    reserve=_capital_floor(f,p)
    remaining=float(f.get('remaining_turns',9999) or 9999)
    util=float(f.get('productive_utilization',0) or 0)

    if op=='BUY_SEED' and len(order)>=3:
        crop=order[1];qty=max(0,int(order[2] or 0));unit=float(SEED_COST.get(crop,0) or 0)
        if qty<=0 or unit<=0:return None
        affordable=max(0,int((money-reserve)//unit))
        qty=min(qty,affordable)
        return ['BUY_SEED',crop,qty] if qty>0 else None

    if op=='BUY_ANIMAL' and len(order)>=3:
        animal=order[1];cost=float(ANIMAL_COST.get(animal,0) or 0)
        # Late animals rarely recover their capital. Require both runway and a post-buy reserve.
        if remaining<300 or money-cost<max(reserve,float(p.get('livestock_cash_buffer',350) or 350)):
            return None
        return [op,animal,1]

    if op=='BUY_LAND':
        unlocked=max(1,int(f.get('unlocked_quadrants',1) or 1))
        idx=min(len(LAND_COSTS)-1,max(0,unlocked-1));cost=float(LAND_COSTS[idx])
        # A fourth quadrant is optional unless existing acreage is being used efficiently.
        if unlocked>=3 and util<.62:
            return None
        if remaining<300 or money-cost<reserve:
            return None
        return order

    if op=='HIRE':
        # The base policy already controls hand targets; only suppress very late hires or hires made
        # while the farm is cash-starved.  This avoids converting a temporary money lead into a loss.
        if remaining<240 or money<reserve*1.35:
            return None
        return order

    return order


def _plant_rewrite(action,seeds,obs,f,game,p):
    if not (isinstance(action,list) and action and action[0]=='PLANT'):
        return action
    original=action[1] if len(action)>1 else None
    available={c:int(seeds.get(c,0) or 0) for c in CROP_PRODUCT}
    chosen=best_crop(available,obs,f,game,p)
    if chosen is None:
        return action
    original_score=crop_portfolio_score(original,obs,f,game,p) if original in CROP_PRODUCT else -1e12
    chosen_score=crop_portfolio_score(chosen,obs,f,game,p)
    if int(available.get(original,0) or 0)<=0 or chosen_score>original_score*1.06:
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
        scored.append((crop_portfolio_score(crop,obs,f,game,p),-SEED_COST[crop],crop))
    scored.sort(reverse=True)
    if not scored:return order
    best_score,_,chosen=scored[0]
    original_score=crop_portfolio_score(original,obs,f,game,p) if original in CROP_PRODUCT else -1e12
    if best_score>original_score*1.08:crop=chosen
    else:crop=original
    if crop in ('STRAWBERRY','MELON'):qty=min(qty,6)
    elif crop in ('TOMATO','CARROT'):qty=min(qty,10)
    else:qty=min(qty,14)
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


def _rewrite_market(base_orders,obs,f,game,p):
    rewritten=[];seen_sell=set();shed=dict(obs.get('private',{}).get('shed',{}) or {})
    for order in base_orders or []:
        if not isinstance(order,list) or not order:continue
        op=order[0]
        candidate=None
        if op=='SELL' and len(order)>=3:
            item=order[1];qty=max(0,int(order[2] or 0));decision=sell_decision(item,qty,obs,f,game,p)
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
            if not (int(f.get('unlocked_quadrants',1) or 1)>=3 and float(f.get('productive_utilization',0) or 0)<.62 and float(f.get('remaining_turns',0) or 0)<360):
                candidate=order
        else:
            candidate=order

        candidate=_capital_guard(candidate,obs,f,p)
        if candidate is not None:
            rewritten.append(candidate)

    for item,n in shed.items():
        if item in seen_sell or item not in MARKET_PARAMS or int(n or 0)<=0:continue
        should,batch,_,_=sell_decision(item,int(n),obs,f,game,p)
        if should and batch>0:rewritten.append(['SELL',item,batch]);seen_sell.add(item)

    decorated=[(_market_priority(o,obs,f,game,p),i,o) for i,o in enumerate(rewritten)]
    decorated.sort(key=lambda x:(x[0],-x[1]),reverse=True)
    return [o for _,_,o in decorated[:10]]


def decide_v57(obs,game,p):
    p=validate_params(p)
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
    """Testing/research helper; never required by the submitted agent contract."""
    game=configuration or {};p=validate_params(params);f=features(obs,game)
    return economic_snapshot(obs,f,game,p)
