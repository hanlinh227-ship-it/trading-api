"""V4 full-farm controller: preserve V3 safety while accelerating expansion and utilization."""
import copy
from incumbent import DEFAULT_PARAMS, SEED_COST, BASE_PRICE, _market_actions, _move_toward, _choose_crop, _plan_units
from features import features

V3_DEFAULT = dict(
    route=True,
    market=True,
    endgame=True,
    distance_cost=9.0,
    target_hands=11,
    crop_mode='balanced',
    harvest_wait=False,
    expansion_mode='fast',
    land_buffer=180,
    fill_target=0.90,
    fill_priority=88.0,
    seed_scale=1.45,
    dynamic_labor=True,
)
FIRST = {'WHEAT': 2, 'CARROT': 2, 'TOMATO': 8, 'STRAWBERRY': 10, 'MELON': 10}
MAX_AGE = {'WHEAT': 4, 'CARROT': 3, 'MELON': 12}
LAND_COSTS = (1000, 2000, 4000)
EXPANSION = {
    'balanced': {'deadlines': (1, 7, 12), 'buffers': (250, 350, 500)},
    'fast': {'deadlines': (0, 4, 9), 'buffers': (180, 220, 300)},
    'max': {'deadlines': (0, 2, 7), 'buffers': (50, 80, 120)},
}


def validate_params(params):
    p = dict(V3_DEFAULT)
    if params:
        if set(params) - set(p):
            raise ValueError('Unknown V4 parameter')
        p.update(params)
    for k in ('route', 'market', 'endgame', 'harvest_wait', 'dynamic_labor'):
        if type(p[k]) is not bool:
            raise ValueError(k)
    if type(p['target_hands']) is not int or not 5 <= p['target_hands'] <= 14:
        raise ValueError('target_hands')
    if not isinstance(p['distance_cost'], (int, float)) or not 1 <= p['distance_cost'] <= 40:
        raise ValueError('distance_cost')
    if p['crop_mode'] not in ('balanced', 'grains', 'demand', 'fast_cash'):
        raise ValueError('crop_mode')
    if p['expansion_mode'] not in EXPANSION:
        raise ValueError('expansion_mode')
    if not isinstance(p['land_buffer'], (int, float)) or not 0 <= p['land_buffer'] <= 1500:
        raise ValueError('land_buffer')
    if not isinstance(p['fill_target'], (int, float)) or not .55 <= p['fill_target'] <= .98:
        raise ValueError('fill_target')
    if not isinstance(p['fill_priority'], (int, float)) or not 25 <= p['fill_priority'] <= 125:
        raise ValueError('fill_priority')
    if not isinstance(p['seed_scale'], (int, float)) or not .6 <= p['seed_scale'] <= 3.0:
        raise ValueError('seed_scale')
    return p


def _fast_cash_weights():
    return {'WHEAT': .48, 'CARROT': .34, 'TOMATO': .10, 'STRAWBERRY': .02, 'MELON': .06}


def strategic_params(obs, f, p):
    cfg = copy.deepcopy(DEFAULT_PARAMS)

    if p['dynamic_labor']:
        # Hands reset nightly and are cheap early in the Fibonacci schedule. Scale labor
        # with owned acreage and maintenance pressure instead of keeping a fixed crew.
        acreage_target = {1: 7, 2: 9, 3: 12, 4: 14}[min(4, max(1, f['unlocked_quadrants']))]
        workload = f['water_due'] + f['ripe'] + int(max(0, p['fill_target'] - f['utilization']) * f['unlocked_tiles'])
        pressure_target = 7 + min(7, workload // 14)
        cfg['target_hands'] = min(14, max(p['target_hands'], acreage_target, pressure_target))
    else:
        cfg['target_hands'] = p['target_hands']

    # Before full unlock, bias toward fast 2-day crops to finance the next land purchase.
    if not f['full_farm'] and p['crop_mode'] in ('balanced', 'fast_cash'):
        for name in ('weights_early', 'weights_mid'):
            cfg[name] = _fast_cash_weights()
    elif p['crop_mode'] == 'grains':
        for name in ('weights_early', 'weights_mid', 'weights_late', 'weights_end'):
            cfg[name] = {'WHEAT': .65, 'CARROT': .35, 'TOMATO': 0., 'STRAWBERRY': 0., 'MELON': 0.}
    elif p['crop_mode'] == 'fast_cash':
        for name in ('weights_early', 'weights_mid', 'weights_late'):
            cfg[name] = _fast_cash_weights()
    elif p['crop_mode'] == 'demand':
        for name in ('weights_early', 'weights_mid', 'weights_late', 'weights_end'):
            weights = cfg[name]
            for crop in weights:
                weights[crop] *= max(.35, min(1.8, f['price_ratios'].get(crop, 1)))
            total = sum(weights.values())
            cfg[name] = {k: v / total for k, v in weights.items()}

    # Maintain enough seed throughput to fill newly unlocked quadrants quickly.
    if not f['full_farm'] or f['utilization'] < p['fill_target']:
        cfg['seed_budget_ratio'] = min(.72, max(cfg['seed_budget_ratio'], .30 * p['seed_scale']))
        cfg['seed_buffer_per_unit'] = max(cfg['seed_buffer_per_unit'], 2.2 * p['seed_scale'])
        cfg['max_seed_stock'] = min(120, max(cfg['max_seed_stock'], int(64 * p['seed_scale'])))

    if p['market']:
        floor = cfg['sell_floor_ratio']
        if f['regime'] == 'market_liquidation' or f['money'] < 350:
            floor = .05
        elif f['regime'] == 'comeback':
            floor = .58
        elif f['opponent_behavior'] == 'high_labor':
            floor = .66
        if not f['full_farm']:
            stage = f['unlocked_quadrants'] - 1
            deadline = EXPANSION[p['expansion_mode']]['deadlines'][stage]
            # Convert shed inventory into expansion capital as the deadline approaches.
            if f['day'] >= deadline - 1 and f['money'] < f['next_land_cost'] + p['land_buffer']:
                floor = min(floor, .18)
        cfg['sell_floor_ratio'] = floor
        cfg['behind_sell_floor_ratio'] = min(floor, .58)
    return cfg


def task(tile, day, step, can_plant, p, final_day=False, fill_boost=False):
    if tile is None:
        if can_plant and not final_day:
            return (p['fill_priority'] if fill_boost else 28., 'PLANT')
        return None
    if not isinstance(tile, dict):
        return None
    if tile.get('kind') == 'WEED':
        return (104. if fill_boost else 42., 'DIG') if not final_day else None
    if tile.get('kind') != 'PLANT':
        return None
    crop = tile['crop']
    age = day - tile['planted_day']
    y = tile.get('yield_units', 0)
    mature = age >= FIRST[crop]
    if final_day:
        return (130. + y, 'HARVEST') if y > 0 and mature else None
    if y > 0 and mature:
        if crop in MAX_AGE and p['harvest_wait'] and age < MAX_AGE[crop]:
            if not tile.get('watered_today'):
                return (82., 'WATER')
            return None
        return (112. + min(y, 8), 'HARVEST')
    if not tile.get('watered_today'):
        return (145. if tile.get('consecutive_unwatered', 0) >= 1 else 79., 'WATER')
    return None


def plan(obs, f, p, cfg, game):
    me = obs['farms'][obs['player']]
    tiles = me['tiles']
    size = len(tiles)
    units = [me['farmer']] + me.get('hands', [])
    seeds = dict(obs['private'].get('seeds', {}))
    inventories = obs['private'].get('inventories', [])
    reserved, actions = set(), []
    final = p['endgame'] and f['regime'] == 'endgame'
    fill_boost = (not f['full_farm']) or f['utilization'] < p['fill_target']
    n = size // 2
    shed_spots = [(n - 1, n - 1), (n, n - 1), (n - 1, n), (n, n)]
    # Use the conservative cross-version subset for terminal DROP routing.
    shed_spots = [q for q in shed_spots if tiles[q[1]][q[0]] != 'LOCKED']
    worktiles = copy.deepcopy(tiles)

    for idx, pos in enumerate(units):
        x, y = pos
        inv = inventories[idx] if idx < len(inventories) else {}
        if final and sum(inv.values()) > 0:
            dest = min(shed_spots, key=lambda q: (abs(q[0] - x) + abs(q[1] - y), q))
            if tuple(pos) in shed_spots:
                actions.append(['DROP'])
                continue
            actions.append(_move_toward(pos, dest, idx + obs['step']))
            continue

        can_plant = _choose_crop(f['day'], worktiles, seeds, cfg) is not None
        best = None
        for ty, row in enumerate(tiles):
            for tx, tile in enumerate(row):
                if (tx, ty) in reserved:
                    continue
                work = task(tile, f['day'], obs['step'], can_plant, p, final, fill_boost)
                if not work:
                    continue
                priority, op = work
                dist = abs(tx - x) + abs(ty - y)
                if final:
                    to_shed = min(abs(tx - a) + abs(ty - b) for a, b in shed_spots)
                    if dist + 1 + to_shed + 1 > f['remaining_turns']:
                        continue
                if dist >= game.get('turnsPerDay', 24) - f['hour']:
                    continue
                # During farm fill, prefer nearby empty fields but never sacrifice urgent watering.
                score = priority - p['distance_cost'] * dist + (12 if dist == 0 else 0)
                if op == 'PLANT' and fill_boost:
                    score += 8
                key = (score, -dist, -ty, -tx)
                if best is None or key > best[0]:
                    best = (key, (tx, ty), op)
        if best is None:
            actions.append(['PASS'])
            continue
        _, dest, op = best
        reserved.add(dest)
        if dest != (x, y):
            actions.append(_move_toward(pos, dest, idx + obs['step']))
            continue
        if op == 'PLANT':
            crop = _choose_crop(f['day'], worktiles, seeds, cfg)
            if crop is None:
                actions.append(['PASS'])
                continue
            seeds[crop] -= 1
            worktiles[y][x] = {'kind': 'PLANT', 'crop': crop}
            actions.append(['PLANT', crop])
        else:
            actions.append([op])
    return actions[0], actions[1:]


def expansion_market_actions(obs, cfg, p, f):
    """Reorder the incumbent market plan so sell -> land -> labor -> seeds.

    This can unlock more than one quadrant in one turn when cash truly covers it,
    but it keeps a profile-dependent buffer so expansion never blindly spends every dollar.
    """
    base = _market_actions(obs, cfg)
    sells = [o for o in base if o and o[0] == 'SELL']
    hires = [o for o in base if o and o[0] == 'HIRE']
    seeds = [o for o in base if o and o[0] == 'BUY_SEED']
    other = [o for o in base if o and o[0] not in ('SELL', 'HIRE', 'BUY_SEED', 'BUY_LAND')]

    if f['full_farm']:
        return (sells + hires + seeds + other)[:10]

    mode = EXPANSION[p['expansion_mode']]
    unlocked = f['unlocked_quadrants']
    projected = f['money']
    # Conservative proceeds estimate: actual sequential sells can move price down.
    for order in sells:
        item, qty = order[1], int(order[2])
        projected += .65 * float(obs['market']['prices'].get(item, BASE_PRICE.get(item, 1))) * qty

    lands = []
    while unlocked < 4 and len(lands) < 3:
        stage = unlocked - 1
        cost = LAND_COSTS[stage]
        deadline = mode['deadlines'][stage]
        profile_buffer = mode['buffers'][stage] + p['land_buffer']
        urgent = f['day'] >= deadline
        near = f['day'] >= max(0, deadline - 2)
        productive = f['utilization'] >= .45 or f['day'] >= deadline
        buffer = 0 if urgent else profile_buffer
        if projected >= cost + buffer and (urgent or near or productive):
            lands.append(['BUY_LAND'])
            projected -= cost
            unlocked += 1
            continue
        break

    # If land is due but not yet affordable, conserve capital: keep labor but limit seed orders.
    if unlocked < 4:
        stage = unlocked - 1
        deadline = mode['deadlines'][stage]
        if f['day'] >= deadline - 1 and not lands:
            seeds = seeds[:1]

    return (sells + lands + hires + seeds + other)[:10]


def decide(obs, game, p):
    f = features(obs, game)
    cfg = strategic_params(obs, f, p)
    farmer, hands = plan(obs, f, p, cfg, game) if p['route'] else _plan_units(obs, cfg)
    orders = expansion_market_actions(obs, cfg, p, f) if p['market'] else _market_actions(obs, cfg)
    if p['endgame'] and f['regime'] == 'endgame':
        shed = dict(obs['private'].get('shed', {}))
        for inv in obs['private'].get('inventories', []):
            for k, v in inv.items():
                shed[k] = shed.get(k, 0) + v
        orders = [['SELL', k, int(v)] for k, v in sorted(shed.items()) if v > 0 and k in BASE_PRICE and k != 'FERTILIZER']
        if f['hour'] < 3:
            need = max(0, min(6, cfg['target_hands']) - f['hands'])
            orders.extend([['HIRE'] for _ in range(min(need, 10 - len(orders)))])
    return {'farmer': farmer, 'hands': hands, 'market': orders[:10]}


def make_v3(params=None):
    p = validate_params(params)

    def agent(obs, configuration=None):
        return decide(obs, configuration or {}, p)
    return agent
