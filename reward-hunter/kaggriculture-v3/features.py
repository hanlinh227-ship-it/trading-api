"""Pure public-observation features; no opponent private inventory or hidden state."""
from incumbent import BASE_PRICE


def features(obs, cfg):
    me, opp = obs['farms'][obs['player']], obs['farms'][1-obs['player']]
    day, hour = obs['day'], obs['hour']
    plants = [t for row in me['tiles'] for t in row if isinstance(t, dict) and t.get('kind') == 'PLANT']
    private = obs['private']
    shed = private.get('shed', {})
    carried = sum(sum(i.values()) for i in private.get('inventories', []))
    prices = obs['market']['prices']
    free = sum(t is None for row in me['tiles'] for t in row)
    ripe = sum(t.get('yield_units', 0) > 0 and day-t['planted_day'] >= {'WHEAT':2,'CARROT':2,'TOMATO':8,'STRAWBERRY':10,'MELON':10}[t['crop']] for t in plants)
    gap = me['money']-opp['money']
    end_step = int(cfg.get('episodeSteps', 720))-2
    remain = end_step-int(obs['step'])+1
    if remain <= cfg.get('turnsPerDay',24): regime = 'endgame'
    elif sum(shed.values())+carried > .8*cfg.get('shedCapacity',100): regime = 'market_liquidation'
    elif ripe > len(plants)*.35: regime = 'harvest_heavy'
    elif gap < -2500: regime = 'comeback'
    elif gap > 4000: regime = 'protect_lead'
    elif day < 12 and free < 5: regime = 'expansion'
    elif sum(shed.values()) > 20: regime = 'inventory_accumulation'
    else: regime = 'production'
    op_plants = [t for row in opp['tiles'] for t in row if isinstance(t,dict)]
    if len(opp.get('unlocked_quadrants',[])) > len(me.get('unlocked_quadrants',[])): behavior='expansion'
    elif len(opp.get('hands',[])) >= 13: behavior='high_labor'
    elif any('animal' in t for t in op_plants): behavior='livestock'
    elif len(opp.get('hands',[])) < 3: behavior='low_labor'
    elif gap < -4000: behavior='strong_lead'
    else: behavior='crop_economy'
    return dict(day=day,hour=hour,remaining_turns=remain,money=me['money'],gap=gap,
                hands=len(me.get('hands',[])),plants=len(plants),ripe=ripe,free=free,
                utilization=len(plants)/max(1,len(plants)+free),carried=carried,
                shed_units=sum(shed.values()),inventory_value=sum(prices.get(k,0)*v for k,v in shed.items()),
                price_ratios={k:v/BASE_PRICE.get(k,max(1,v)) for k,v in prices.items()},
                water_due=sum(not t.get('watered_today',False) for t in plants),
                regime=regime,opponent_behavior=behavior)
