"""Market-value overlay for the mixed-farm agent.

The base policy decides what to grow/raise and produces a valid market queue.  This overlay
only changes the timing/size/order of market sales using public current-state information.
It is intentionally conservative: it never invents hidden information, never exceeds the
original quantity, and endgame / shed-pressure / working-capital needs override holding.

Kaggriculture's official market is endogenous: selling increases market inventory and can
push prices down, while town consumption and BUY_PRODUCT reduce inventory and can raise prices.
Premium goods are much more glut-sensitive than staples, so production volume and realization
price must be optimized together rather than maximizing raw output alone.
"""
from __future__ import annotations

BASE = {
    'WHEAT': 25.0, 'CARROT': 35.0, 'TOMATO': 60.0, 'STRAWBERRY': 120.0,
    'MELON': 250.0, 'EGG': 50.0, 'MILK': 160.0, 'WOOL': 200.0,
    'FERTILIZER': 100.0,
}
# Official above-I0 target magnitudes: larger means own/market oversupply destroys price faster.
GLUT_SENSITIVITY = {
    'WHEAT': .20, 'CARROT': .70, 'TOMATO': .60, 'STRAWBERRY': 1.60,
    'MELON': 3.60, 'EGG': .20, 'MILK': 1.60, 'WOOL': 3.20,
    'FERTILIZER': .40,
}
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
PREMIUM = frozenset(('STRAWBERRY', 'MELON', 'MILK', 'WOOL'))
LAND_COSTS = (1000.0, 2000.0, 4000.0)


def _demand(obs, item):
    score = 0 if item == 'FERTILIZER' else 1  # town center consumes all non-fertilizer goods
    for shop in obs.get('town', {}).get('unlocked_shops', []):
        products = SHOP_PRODUCTS.get(shop, ())
        if item in products:
            score += 2 if len(products) == 1 else 1
    return score


def _remaining_turns(obs, cfg):
    turns = int(cfg.get('turnsPerDay', 24) or 24)
    step = int(obs.get('day', 0) or 0) * turns + int(obs.get('hour', 0) or 0)
    return max(0, int(cfg.get('episodeSteps', 720) or 720) - 1 - step)


def _cash_pressure(obs, params):
    me = obs['farms'][obs['player']]
    money = float(me.get('money', 0.0) or 0.0)
    unlocked = len(me.get('unlocked_quadrants', ['NW']))
    target = int(params.get('land_target_quadrants', 4) or 4)
    working = max(450.0, float(params.get('livestock_cash_buffer', 650) or 650))
    if unlocked < target:
        next_cost = LAND_COSTS[min(2, max(0, unlocked - 1))]
        return money < next_cost + max(working, float(params.get('land_buffer', 180) or 180))
    return money < working


def _sell_opportunity(obs, item):
    market = obs.get('market', {})
    price = float(market.get('prices', {}).get(item, BASE.get(item, 1.0)) or 1.0)
    ratio = price / max(1.0, BASE.get(item, price))
    inventory = float(market.get('inventory', {}).get(item, 10000) or 10000)
    scarcity = max(0.0, 10000.0 - inventory)
    demand = _demand(obs, item)
    sensitivity = GLUT_SENSITIVITY.get(item, .5)
    # High current price and genuine scarcity are opportunities.  High demand is useful because
    # town consumption can restore price after a small sale.  Existing glut is penalized heavily
    # for premium goods.
    glut = max(0.0, 1.0 - ratio)
    return ratio + .035 * demand + .0004 * min(500.0, scarcity) - .28 * sensitivity * glut


def _sale_cap(obs, cfg, params, item, requested):
    requested = max(1, int(requested))
    private = obs.get('private', {})
    shed = private.get('shed', {})
    shed_units = sum(int(v or 0) for v in shed.values())
    remaining = _remaining_turns(obs, cfg)
    endgame = remaining <= int(cfg.get('turnsPerDay', 24) or 24)
    pressure = _cash_pressure(obs, params)
    if endgame or shed_units >= 82 or pressure:
        return requested

    market = obs.get('market', {})
    price = float(market.get('prices', {}).get(item, BASE.get(item, 1.0)) or 1.0)
    ratio = price / max(1.0, BASE.get(item, price))
    demand = _demand(obs, item)
    sensitivity = GLUT_SENSITIVITY.get(item, .5)

    # Premium products crash fastest above I0.  Sell in smaller clips when price is soft so town
    # demand can absorb supply between turns.  We never increase requested size here.
    if item in PREMIUM or sensitivity >= 1.5:
        if ratio < .72 and demand > 0 and remaining > 72:
            return 0
        if ratio < .90:
            return max(1, min(requested, int(round(requested * .30))))
        if ratio < 1.03:
            return max(1, min(requested, int(round(requested * .50))))
        if ratio < 1.15:
            return max(1, min(requested, int(round(requested * .70))))
        return requested

    # Staples absorb gluts better; still avoid dumping a full batch at a very weak quote when
    # there is time for town demand to recover the market.
    if ratio < .55 and demand > 0 and remaining > 96:
        return max(1, min(requested, requested // 3 or 1))
    if ratio < .75:
        return max(1, min(requested, requested // 2 or 1))
    return requested


def coordinate_action(obs, cfg, action, params):
    """Return a market-value-aware copy of a valid base-policy action."""
    if not isinstance(action, dict):
        return action
    market_orders = action.get('market', [])
    if not isinstance(market_orders, list) or not market_orders:
        return action

    sells = []
    others = []
    for order in market_orders:
        if not isinstance(order, list) or not order:
            continue
        if order[0] == 'SELL' and len(order) >= 3 and order[1] in BASE:
            cap = _sale_cap(obs, cfg, params, order[1], order[2])
            if cap > 0:
                sells.append((_sell_opportunity(obs, order[1]), [order[0], order[1], cap]))
        else:
            others.append(list(order))

    # Realize the strongest current prices first.  This matters because each sold unit changes
    # the shared market inventory/next quote and opponents may be selling in the same turn.
    sells.sort(key=lambda x: (x[0], x[1][1]), reverse=True)
    out = dict(action)
    out['market'] = [order for _, order in sells] + others
    return out
