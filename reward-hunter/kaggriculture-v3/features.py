"""Pure public-observation features for the V4 full-farm lane."""
from incumbent import BASE_PRICE

FIRST = {'WHEAT': 2, 'CARROT': 2, 'TOMATO': 8, 'STRAWBERRY': 10, 'MELON': 10}
LAND_COSTS = (1000, 2000, 4000)


def features(obs, cfg):
    me, opp = obs['farms'][obs['player']], obs['farms'][1 - obs['player']]
    day, hour = int(obs['day']), int(obs['hour'])
    tiles = me['tiles']
    plants = [t for row in tiles for t in row if isinstance(t, dict) and t.get('kind') == 'PLANT']
    weeds = [t for row in tiles for t in row if isinstance(t, dict) and t.get('kind') == 'WEED']
    animals = [t for row in tiles for t in row if isinstance(t, dict) and 'animal' in t]
    structures = [t for row in tiles for t in row if isinstance(t, dict) and t.get('kind') in ('COOP', 'PASTURE')]
    private = obs['private']
    shed = private.get('shed', {})
    carried = sum(sum(i.values()) for i in private.get('inventories', []))
    prices = obs['market']['prices']
    free = sum(t is None for row in tiles for t in row)
    locked = sum(t == 'LOCKED' for row in tiles for t in row)
    unlocked_tiles = sum(t != 'LOCKED' for row in tiles for t in row)
    unlocked_quadrants = len(me.get('unlocked_quadrants', ['NW']))
    full_farm = unlocked_quadrants >= 4
    next_land_cost = LAND_COSTS[unlocked_quadrants - 1] if unlocked_quadrants < 4 else 0
    ripe = sum(
        t.get('yield_units', 0) > 0 and day - int(t['planted_day']) >= FIRST[t['crop']]
        for t in plants
    )
    gap = float(me['money']) - float(opp['money'])
    end_step = int(cfg.get('episodeSteps', 720)) - 2
    remain = end_step - int(obs['step']) + 1
    utilization = len(plants) / max(1, unlocked_tiles)

    if remain <= cfg.get('turnsPerDay', 24):
        regime = 'endgame'
    elif sum(shed.values()) + carried > .8 * cfg.get('shedCapacity', 100):
        regime = 'market_liquidation'
    elif not full_farm and day <= 14:
        regime = 'expansion'
    elif ripe > len(plants) * .35:
        regime = 'harvest_heavy'
    elif gap < -2500:
        regime = 'comeback'
    elif gap > 4000:
        regime = 'protect_lead'
    elif sum(shed.values()) > 20:
        regime = 'inventory_accumulation'
    else:
        regime = 'production'

    op_tiles = opp['tiles']
    op_plants = [t for row in op_tiles for t in row if isinstance(t, dict)]
    if len(opp.get('unlocked_quadrants', [])) > unlocked_quadrants:
        behavior = 'expansion'
    elif len(opp.get('hands', [])) >= 13:
        behavior = 'high_labor'
    elif any('animal' in t for t in op_plants):
        behavior = 'livestock'
    elif len(opp.get('hands', [])) < 3:
        behavior = 'low_labor'
    elif gap < -4000:
        behavior = 'strong_lead'
    else:
        behavior = 'crop_economy'

    return dict(
        day=day,
        hour=hour,
        remaining_turns=remain,
        money=float(me['money']),
        gap=gap,
        hands=len(me.get('hands', [])),
        plants=len(plants),
        weeds=len(weeds),
        animals=len(animals),
        structures=len(structures),
        ripe=ripe,
        free=free,
        locked=locked,
        unlocked_tiles=unlocked_tiles,
        unlocked_quadrants=unlocked_quadrants,
        full_farm=full_farm,
        next_land_cost=next_land_cost,
        utilization=utilization,
        carried=carried,
        shed_units=sum(shed.values()),
        inventory_value=sum(prices.get(k, 0) * v for k, v in shed.items()),
        price_ratios={k: v / BASE_PRICE.get(k, max(1, v)) for k, v in prices.items()},
        water_due=sum(not t.get('watered_today', False) for t in plants),
        regime=regime,
        opponent_behavior=behavior,
    )
