"""Dynamic economy reasoning for the Kaggriculture rank lane.

This module deliberately uses only public/current observation state plus our own private farm
inventory.  It does not replay another participant's actions and does not depend on hidden
Kaggle state.  The goal is to turn public lessons about the game into *runtime economics*:
produce what the town is likely to absorb, keep feed/fertilizer loops healthy, and sell into
scarcity rather than dumping high-value output into its own glut.

The constants below are derived from kaggle-environments 1.32.7.  The policy still validates
against the installed engine in CI before any candidate can be promoted.
"""
from __future__ import annotations

import math

MARKET_I0 = 10000.0
PRICE_FLOOR = 1.0
HINGE_GAIN = 8.0
MARKET_PARAMS = {
    'WHEAT':      {'base':25.,  'T':400., 'below_func':'sqrt',  'below_target':.80, 'above_func':'log',    'above_target':.20},
    'CARROT':     {'base':35.,  'T':450., 'below_func':'hinge', 'below_target':1.00, 'above_func':'sqrt',   'above_target':.70},
    'TOMATO':     {'base':60.,  'T':200., 'below_func':'hinge', 'below_target':.40, 'above_func':'sqrt',   'above_target':.60},
    'STRAWBERRY': {'base':120., 'T':100., 'below_func':'sqrt',  'below_target':.70, 'above_func':'linear', 'above_target':1.60},
    'MELON':      {'base':250., 'T':300., 'below_func':'log',   'below_target':.20, 'above_func':'sq',     'above_target':3.60},
    'EGG':        {'base':50.,  'T':332., 'below_func':'hinge', 'below_target':.40, 'above_func':'log',    'above_target':.20},
    'MILK':       {'base':160., 'T':122., 'below_func':'sqrt',  'below_target':.60, 'above_func':'linear', 'above_target':1.60},
    'WOOL':       {'base':200., 'T':105., 'below_func':'log',   'below_target':.20, 'above_func':'sq',     'above_target':3.20},
    'FERTILIZER': {'base':100., 'T':200., 'below_func':'linear','below_target':.40, 'above_func':'linear', 'above_target':.40},
}

# Expected per-shop-instance consumption on one shop tick.  Shops are sampled with replacement
# from eight types.  Single-product shops consume 2x.  This is a prior for *future* unknown shops;
# already unlocked shops are read directly from the public observation instead.
EXPECTED_SHOP_UNITS_PER_TICK = {
    'WHEAT': 5/8,
    'CARROT': 3/8,
    'TOMATO': 2/8,
    'STRAWBERRY': 4/8,
    'MELON': 0.,
    'EGG': 2/8,
    'MILK': 3/8,
    'WOOL': 2/8,
    'FERTILIZER': 0.,
}

CROP_PRODUCT = {
    'WHEAT':'WHEAT','CARROT':'CARROT','TOMATO':'TOMATO','STRAWBERRY':'STRAWBERRY','MELON':'MELON'
}
CROP_SEED = {'WHEAT':10.,'CARROT':20.,'TOMATO':50.,'STRAWBERRY':100.,'MELON':80.}
CROP_YIELD = {'WHEAT':6.,'CARROT':4.,'TOMATO':4.,'STRAWBERRY':4.,'MELON':6.}
CROP_FIRST = {'WHEAT':2.,'CARROT':2.,'TOMATO':8.,'STRAWBERRY':10.,'MELON':10.}
CROP_CYCLE = {'WHEAT':4.,'CARROT':3.,'TOMATO':12.,'STRAWBERRY':16.,'MELON':12.}
ANIMAL_SPEC = {
    'GOOSE': {'cost':300.,'product':'EGG','first':4.,'interval':1.},
    'COW': {'cost':400.,'product':'MILK','first':8.,'interval':2.},
    'SHEEP': {'cost':500.,'product':'WOOL','first':6.,'interval':3.},
}
PREMIUM_GLUT_SENSITIVE = {'STRAWBERRY','MILK','WOOL','MELON'}


def _shape(kind, x, T):
    x=max(0.0,float(x))
    if kind=='linear': return x
    if kind=='sq': return x*x
    if kind=='sqrt': return math.sqrt(x)
    if kind=='log': return math.log1p(x)
    if kind=='log10': return math.log10(1.0+x)
    if kind=='hinge':
        u=x/max(1e-9,float(T))
        return u + HINGE_GAIN*max(0.0,u-1.0)**2
    return x


def model_price(item, inventory):
    """Reproduce the 1.32.7 default market curve for planning only."""
    p=MARKET_PARAMS[item];base=p['base'];T=p['T'];inventory=float(inventory)
    if inventory<MARKET_I0:
        f=p['below_func'];amp=p['below_target']*base/max(1e-9,_shape(f,T,T));price=base+amp*_shape(f,MARKET_I0-inventory,T)
    else:
        f=p['above_func'];amp=p['above_target']*base/max(1e-9,_shape(f,T,T));price=base-amp*_shape(f,inventory-MARKET_I0,T)
    return max(PRICE_FLOOR,float(round(price)))


def _cfg(game,key,default):
    if isinstance(game,dict): return game.get(key,default)
    return getattr(game,key,default)


def remaining_days(f,game=None):
    turns=max(1.0,float(_cfg(game or {},'turnsPerDay',24) or 24))
    return max(0.0,float(f.get('remaining_turns',0) or 0)/turns)


def current_shop_drain_per_day(item,f,game=None):
    turns=max(1.0,float(_cfg(game or {},'turnsPerDay',24) or 24))
    interval=max(1.0,float(_cfg(game or {},'townShopSellInterval',4) or 4))
    return max(0.0,float(f.get('demand',{}).get(item,0) or 0))*turns/interval


def future_unknown_shop_drain(item,obs,f,game=None):
    """Conservative expected drain from shops that have not unlocked yet.

    We integrate future unlock timing instead of pretending all eight shops are active now. This
    prevents early overproduction and lets the runtime policy grow into newly revealed demand.
    """
    if item=='FERTILIZER': return 0.0
    day=int(f.get('day',0) or 0);remain=remaining_days(f,game);end_day=day+remain
    unlocked=len(obs.get('town',{}).get('unlocked_shops',[]) or [])
    max_new=max(0,8-unlocked);unlock_interval=max(1,int(_cfg(game or {},'townShopUnlockInterval',3) or 3))
    turns=max(1.0,float(_cfg(game or {},'turnsPerDay',24) or 24));sell_interval=max(1.0,float(_cfg(game or {},'townShopSellInterval',4) or 4));ticks_per_day=turns/sell_interval
    expected=0.0;seen=0
    # Shops unlock when the next day is a multiple of the unlock interval.
    for unlock_day in range(day+1,int(math.ceil(end_day))+1):
        if unlock_day%unlock_interval!=0: continue
        if seen>=max_new: break
        active_days=max(0.0,end_day-unlock_day)
        expected += EXPECTED_SHOP_UNITS_PER_TICK.get(item,0.0)*ticks_per_day*active_days
        seen+=1
    return expected


def projected_town_drain(item,obs,f,game=None):
    if item=='FERTILIZER': return 0.0
    days=remaining_days(f,game)
    shop=current_shop_drain_per_day(item,f,game)*days
    center_interval=max(1.0,float(_cfg(game or {},'townCenterSellInterval',24) or 24));turns=max(1.0,float(_cfg(game or {},'turnsPerDay',24) or 24))
    center=days*turns/center_interval
    return max(0.0,shop+center+future_unknown_shop_drain(item,obs,f,game))


def scarcity_knee_ratio(item,f):
    p=MARKET_PARAMS[item]
    scarcity=float(f.get('scarcity',{}).get(item,0.0) or 0.0)
    return scarcity/max(1.0,p['T'])


def projected_opportunity_price(item,obs,f,game=None):
    if item not in MARKET_PARAMS:return float(f.get('prices',{}).get(item,0.0) or 0.0)
    market_inv=float(obs.get('market',{}).get('inventory',{}).get(item,MARKET_I0) or MARKET_I0)
    drain=projected_town_drain(item,obs,f,game)
    # Do not assume we capture the entire theoretical end-of-season hole.  A 55% horizon capture
    # is intentionally conservative because the opponent also sells into the shared market.
    horizon_fraction=.55 if remaining_days(f,game)>5 else .78
    projected=max(0.0,market_inv-drain*horizon_fraction)
    return model_price(item,projected)


def price_capture_ratio(item,obs,f,game=None):
    current=float(f.get('prices',{}).get(item,MARKET_PARAMS.get(item,{}).get('base',1.0)) or 1.0)
    future=max(current,projected_opportunity_price(item,obs,f,game))
    return current/max(1.0,future)


def _supply_pressure(item,f):
    if item in CROP_PRODUCT:
        own=float(f.get('crop_counts',{}).get(item,0) or 0);opp=float(f.get('opponent_crop_counts',{}).get(item,0) or 0)
        scale=12.0
    else:
        animal={'EGG':'GOOSE','MILK':'COW','WOOL':'SHEEP'}.get(item)
        if not animal:return 0.0
        own=float(f.get('animal_counts',{}).get(animal,0) or 0);opp=float(f.get('opponent_animal_counts',{}).get(animal,0) or 0);scale=8.0
    return (own+.75*opp)/scale


def crop_portfolio_score(crop,obs,f,game=None,p=None):
    """Marginal crop score combining production, future price and anti-glut discipline."""
    if crop not in CROP_PRODUCT:return -1e12
    days=remaining_days(f,game)
    if days<CROP_FIRST[crop]+.35:return -1e12
    item=CROP_PRODUCT[crop];current=float(f.get('prices',{}).get(item,MARKET_PARAMS[item]['base']) or MARKET_PARAMS[item]['base']);future=projected_opportunity_price(item,obs,f,game)
    # Weight realizable current cash and future scarcity; shorten horizon near the end.
    future_weight=.58 if days>8 else (.35 if days>3 else .10)
    capture=(1-future_weight)*current+future_weight*future
    gross=capture*CROP_YIELD[crop];score=(gross-CROP_SEED[crop])/max(1.0,CROP_CYCLE[crop])
    demand=float(f.get('demand',{}).get(item,0) or 0);knee=scarcity_knee_ratio(item,f);supply=_supply_pressure(item,f)
    score*=1.0+.10*min(5.0,demand)

    # 1.32.7 scarcity hinge: carrot/tomato are situational options, not permanent allocations.
    if crop in ('CARROT','TOMATO'):
        projected_scarcity=float(f.get('scarcity',{}).get(item,0.0) or 0.0)+projected_town_drain(item,obs,f,game)*.45
        projected_knee=projected_scarcity/max(1.0,MARKET_PARAMS[item]['T'])
        if projected_knee>=1.0:score*=1.0+min(1.0,.55*(projected_knee-0.85))
        elif demand<=0 and knee<.45:score*=.78

    # Strawberry is an excellent market but a glut-sensitive crop; grow it only into visible/future demand.
    if crop=='STRAWBERRY':
        if demand<=0 and future<MARKET_PARAMS[item]['base']*1.10:score*=.55
        if supply>1.0:score/=1.0+1.7*(supply-1.0)

    # Melon has almost no town sink.  It can still pay at small scale, but stop scaling before its
    # convex glut curve destroys the price.
    if crop=='MELON':
        total=float(f.get('crop_counts',{}).get('MELON',0) or 0)+float(f.get('opponent_crop_counts',{}).get('MELON',0) or 0)
        if total>=8:score*=.18
        elif total>=5:score*=.48
        elif current>=220 and total<=3:score*=1.10

    # Wheat is both a sale line and the feed backbone.  Never optimize product revenue by starving
    # a profitable herd.
    animals=float(f.get('animals',0) or 0);wheat=float(f.get('crop_counts',{}).get('WHEAT',0) or 0)
    if crop=='WHEAT' and animals>0:
        target=max(4.0,.75*animals)
        if wheat<target:score*=1.0+min(1.2,(target-wheat)/max(1.0,target))

    if supply>1.0 and item in PREMIUM_GLUT_SENSITIVE:score/=1.0+1.25*(supply-1.0)
    return float(score)


def animal_portfolio_score(animal,obs,f,game=None,p=None):
    if animal not in ANIMAL_SPEC:return -1e12
    spec=ANIMAL_SPEC[animal];days=remaining_days(f,game)
    if days<=spec['first']+.5:return -1e12
    product=spec['product'];future=projected_opportunity_price(product,obs,f,game);current=float(f.get('prices',{}).get(product,MARKET_PARAMS[product]['base']) or MARKET_PARAMS[product]['base'])
    capture=.35*current+.65*future
    cycles=max(1.0,1.0+math.floor((days-spec['first'])/max(1.0,spec['interval'])))
    # CARE can add production when fed; use a conservative 1.55 units/cycle rather than assuming perfect care.
    product_value=cycles*1.55*capture
    wheat_price=float(f.get('prices',{}).get('WHEAT',25) or 25);feed_cost=days*wheat_price
    fert_price=float(f.get('prices',{}).get('FERTILIZER',100) or 100)
    # Fertilizer appears daily on every surviving animal; collection is limited by action capacity.
    labor_capacity=min(1.0,max(.25,float(f.get('hands',0) or 0)/10.0))
    fertilizer_value=max(0.0,days-1.0)*fert_price*.72*labor_capacity
    action_cost=days*7.0+cycles*4.0
    net=product_value+fertilizer_value-spec['cost']-feed_cost-action_cost
    demand=float(f.get('demand',{}).get(product,0) or 0);net*=1.0+.035*min(6.0,demand)
    supply=_supply_pressure(product,f)
    if product in PREMIUM_GLUT_SENSITIVE and supply>1.0:net/=1.0+.85*(supply-1.0)
    if animal=='SHEEP' and demand<=0 and future<MARKET_PARAMS['WOOL']['base']*1.08:net*=.52
    if animal=='GOOSE' and demand<=0 and future<MARKET_PARAMS['EGG']['base']*1.12:net*=.65
    return float(net/max(1.0,spec['cost']))


def best_crop(seeds,obs,f,game=None,p=None):
    choices=[]
    for crop,n in (seeds or {}).items():
        if crop in CROP_PRODUCT and int(n or 0)>0:
            choices.append((crop_portfolio_score(crop,obs,f,game,p),-CROP_SEED[crop],crop))
    if not choices:return None
    choices.sort(reverse=True)
    return choices[0][2] if choices[0][0]>-1e10 else None


def sell_decision(item,units,obs,f,game=None,p=None):
    """Return (sell?, batch, priority, reason) for a shed item."""
    if item not in MARKET_PARAMS or int(units or 0)<=0:return (False,0,-1e12,'not_sellable')
    units=int(units);days=remaining_days(f,game);current=float(f.get('prices',{}).get(item,MARKET_PARAMS[item]['base']) or MARKET_PARAMS[item]['base']);future=projected_opportunity_price(item,obs,f,game);capture=price_capture_ratio(item,obs,f,game)
    shed_units=float(f.get('shed_units',0) or 0);cash=float(f.get('money',0) or 0);next_land=float(f.get('next_land_cost',0) or 0);land_buffer=float((p or {}).get('land_buffer',180) or 180)
    cash_pressure=(next_land>0 and cash<next_land+land_buffer) or f.get('regime') in ('comeback','expansion')
    capacity_pressure=shed_units>=72
    endgame=days<=1.5 or f.get('regime') in ('endgame','market_liquidation')

    if item=='FERTILIZER':
        # Town never consumes fertilizer.  Keep a small productive reserve; otherwise monetize the
        # daily livestock by-product instead of letting it crowd the shed.
        reserve=0 if endgame else int((p or {}).get('fertilizer_reserve',2) or 0)
        available=max(0,units-reserve)
        if available<=0:return (False,0,current,'fertilizer_reserve')
        should=endgame or capacity_pressure or current>=72 or cash_pressure
        batch=min(available,max(3,int((p or {}).get('sell_batch',6) or 6)))
        return (should,batch,current*(1.0+.2*capacity_pressure),'fertilizer_cashflow' if should else 'hold_fertilizer')

    # Sell immediately when the current quote is already close to the conservative future
    # opportunity.  Otherwise let town demand create scarcity unless capital/capacity needs cash now.
    threshold=.80 if item in PREMIUM_GLUT_SENSITIVE else .72
    if item in ('CARROT','TOMATO','EGG') and scarcity_knee_ratio(item,f)>=.85:threshold=.68
    should=endgame or capacity_pressure or cash_pressure or capture>=threshold or current>=future*.90
    base_batch=max(1,int((p or {}).get('sell_batch',6) or 6))
    if endgame:batch=units
    elif item in PREMIUM_GLUT_SENSITIVE and current>MARKET_PARAMS[item]['base']*1.15:batch=min(units,max(2,base_batch//2))
    elif capture<.85 and not cash_pressure:batch=min(units,max(2,base_batch//2))
    else:batch=min(units,base_batch*(2 if item in ('WHEAT','CARROT') else 1))
    priority=current*(1.0+max(0.0,1.0-capture))*(1.15 if capacity_pressure else 1.0)
    return (bool(should),int(batch),float(priority),'capture_now' if should else 'wait_for_scarcity')


def economic_snapshot(obs,f,game=None,p=None):
    crop_scores={c:crop_portfolio_score(c,obs,f,game,p) for c in CROP_PRODUCT}
    animal_scores={a:animal_portfolio_score(a,obs,f,game,p) for a in ANIMAL_SPEC}
    future_prices={i:projected_opportunity_price(i,obs,f,game) for i in MARKET_PARAMS}
    captures={i:price_capture_ratio(i,obs,f,game) for i in MARKET_PARAMS}
    return {
        'crop_scores':crop_scores,
        'animal_scores':animal_scores,
        'future_prices':future_prices,
        'capture_ratios':captures,
        'remaining_days':remaining_days(f,game),
    }
