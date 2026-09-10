"""Pure public-observation features for the V5 mixed-farm economy lane.

Important: Kaggriculture 1.32.7 can omit ``obs['step']`` for seat 1. Never use that
field as the authoritative clock. ``day * turnsPerDay + hour`` is available to both
seats and is therefore the canonical turn index used by V5.
"""
from incumbent import BASE_PRICE

FIRST = {'WHEAT': 2, 'CARROT': 2, 'TOMATO': 8, 'STRAWBERRY': 10, 'MELON': 10}
LAND_COSTS = (1000, 2000, 4000)
SHOP_PRODUCTS = {
    'BAKERY': ('EGG', 'WHEAT'),
    'PIZZA_SHOP': ('MILK', 'TOMATO', 'WHEAT'),
    'BRUNCH_SPOT': ('EGG', 'WHEAT', 'STRAWBERRY'),
    'YARN_STORE': ('WOOL',),
    'ICE_CREAM_SHOP': ('STRAWBERRY', 'MILK', 'WHEAT'),
    'PET_CAFE': ('CARROT',),
    'SMOOTHIE_SHOP': ('STRAWBERRY', 'MILK'),
    'FARMERS_MARKET': ('WHEAT', 'CARROT', 'TOMATO', 'STRAWBERRY'),
}


def _count_kind(tiles, predicate):
    return sum(1 for row in tiles for t in row if predicate(t))


def canonical_step(obs, cfg):
    turns = int(cfg.get('turnsPerDay', 24) or 24)
    return int(obs.get('day', 0) or 0) * turns + int(obs.get('hour', 0) or 0)


def features(obs, cfg):
    me, opp = obs['farms'][obs['player']], obs['farms'][1 - obs['player']]
    day, hour = int(obs['day']), int(obs['hour'])
    step = canonical_step(obs, cfg)
    # Compatibility shim for downstream V3/V4 routing helpers that still read obs['step'].
    # This fixes the seat-1 omission without making the policy depend on the buggy field.
    if obs.get('step') is None:
        obs['step'] = step
    tiles = me['tiles']
    plants = [t for row in tiles for t in row if isinstance(t, dict) and t.get('kind') == 'PLANT']
    weeds = [t for row in tiles for t in row if isinstance(t, dict) and t.get('kind') == 'WEED']
    animals = [t for row in tiles for t in row if isinstance(t, dict) and 'animal' in t]
    structures = [t for row in tiles for t in row if isinstance(t, dict) and t.get('kind') in ('COOP', 'PASTURE')]
    private = obs['private']
    shed = private.get('shed', {})
    inventories = private.get('inventories', [])
    carried = sum(sum(i.values()) for i in inventories)
    prices = obs['market']['prices']
    market_inventory = obs.get('market', {}).get('inventory', {})

    crop_counts = {c: 0 for c in FIRST}
    for t in plants:
        crop_counts[t['crop']] = crop_counts.get(t['crop'], 0) + 1
    animal_counts = {'GOOSE': 0, 'COW': 0, 'SHEEP': 0}
    for t in animals:
        animal_counts[t['animal']] = animal_counts.get(t['animal'], 0) + 1

    free = _count_kind(tiles, lambda t: t is None)
    locked = _count_kind(tiles, lambda t: t == 'LOCKED')
    unlocked_tiles = _count_kind(tiles, lambda t: t != 'LOCKED')
    unlocked_quadrants = len(me.get('unlocked_quadrants', ['NW']))
    full_farm = unlocked_quadrants >= 4
    next_land_cost = LAND_COSTS[unlocked_quadrants - 1] if unlocked_quadrants < 4 else 0
    ripe = sum(t.get('yield_units', 0) > 0 and day - int(t['planted_day']) >= FIRST[t['crop']] for t in plants)
    animal_ripe = sum(int(t.get('yield_units', 0) or 0) > 0 for t in animals)
    feed_due = sum(not t.get('fed_today', False) for t in animals)
    feed_urgent = sum(not t.get('fed_today', False) and int(t.get('consecutive_unfed', 0) or 0) >= 1 for t in animals)
    care_due = sum(t.get('fed_today', False) and not t.get('cared_today', False) for t in animals)
    fertilizer_ready = sum(bool(t.get('fertilizer_available', False)) for t in animals)
    empty_pastures = sum(t.get('kind') == 'PASTURE' and 'animal' not in t for t in structures)
    empty_coops = sum(t.get('kind') == 'COOP' and 'animal' not in t for t in structures)

    gap = float(me['money']) - float(opp['money'])
    end_step = int(cfg.get('episodeSteps', 720)) - 2
    remain = max(0, end_step - step + 1)
    utilization = len(plants) / max(1, unlocked_tiles)
    productive_tiles = len(plants) + len(structures)
    productive_utilization = productive_tiles / max(1, unlocked_tiles)

    demand = {k: 0 for k in BASE_PRICE}
    for shop in obs.get('town', {}).get('unlocked_shops', []):
        products = SHOP_PRODUCTS.get(shop, ())
        mult = 2 if len(products) == 1 else 1
        for item in products:
            demand[item] = demand.get(item, 0) + mult
    price_ratios = {k: float(v) / BASE_PRICE.get(k, max(1.0, float(v))) for k, v in prices.items()}
    scarcity = {k: max(0.0, 10000.0 - float(market_inventory.get(k, 10000))) for k in prices}

    if remain <= cfg.get('turnsPerDay', 24):
        regime = 'endgame'
    elif sum(shed.values()) + carried > .78 * cfg.get('shedCapacity', 100):
        regime = 'market_liquidation'
    elif feed_urgent:
        regime = 'livestock_rescue'
    elif not full_farm and day <= 14:
        regime = 'expansion'
    elif ripe + animal_ripe > max(2, (len(plants) + len(animals)) * .30):
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
    op_objects = [t for row in op_tiles for t in row if isinstance(t, dict)]
    if len(opp.get('unlocked_quadrants', [])) > unlocked_quadrants:
        behavior = 'expansion'
    elif len(opp.get('hands', [])) >= 13:
        behavior = 'high_labor'
    elif any('animal' in t for t in op_objects):
        behavior = 'livestock'
    elif len(opp.get('hands', [])) < 3:
        behavior = 'low_labor'
    elif gap < -4000:
        behavior = 'strong_lead'
    else:
        behavior = 'crop_economy'

    carried_wheat = sum(int(i.get('WHEAT', 0) or 0) for i in inventories)
    carried_fertilizer = sum(int(i.get('FERTILIZER', 0) or 0) for i in inventories)
    return dict(
        step=step, day=day, hour=hour, remaining_turns=remain, money=float(me['money']), gap=gap,
        hands=len(me.get('hands', [])), plants=len(plants), weeds=len(weeds), animals=len(animals),
        structures=len(structures), crop_counts=crop_counts, animal_counts=animal_counts,
        ripe=ripe, animal_ripe=animal_ripe, feed_due=feed_due, feed_urgent=feed_urgent,
        care_due=care_due, fertilizer_ready=fertilizer_ready, empty_pastures=empty_pastures,
        empty_coops=empty_coops, free=free, locked=locked, unlocked_tiles=unlocked_tiles,
        unlocked_quadrants=unlocked_quadrants, full_farm=full_farm, next_land_cost=next_land_cost,
        utilization=utilization, productive_utilization=productive_utilization, carried=carried,
        carried_wheat=carried_wheat, carried_fertilizer=carried_fertilizer,
        shed_units=sum(shed.values()), shed_wheat=int(shed.get('WHEAT', 0) or 0),
        shed_fertilizer=int(shed.get('FERTILIZER', 0) or 0),
        shed_cows=int(shed.get('COW', 0) or 0), shed_sheep=int(shed.get('SHEEP', 0) or 0),
        shed_geese=int(shed.get('GOOSE', 0) or 0),
        inventory_value=sum(prices.get(k, 0) * v for k, v in shed.items() if k in prices),
        price_ratios=price_ratios, scarcity=scarcity, demand=demand,
        water_due=sum(not t.get('watered_today', False) for t in plants),
        regime=regime, opponent_behavior=behavior,
    )
