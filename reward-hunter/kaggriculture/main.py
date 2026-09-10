from __future__ import annotations

import copy
import json
from pathlib import Path

DEFAULT_PARAMS = {
    "target_hands": 12,
    "late_hands": 5,
    "late_hire_stop_day": 27,
    "first_land_threshold": 4200,
    "second_land_threshold": 9000,
    "third_land_threshold": 18000,
    "first_land_deadline": 12,
    "second_land_deadline": 17,
    "third_land_deadline": 19,
    "sell_floor_ratio": 0.72,
    "behind_sell_floor_ratio": 0.62,
    "late_liquidation_day": 27,
    "seed_budget_ratio": 0.34,
    "seed_buffer_per_unit": 1.6,
    "max_seed_stock": 42,
    "weights_early": {"WHEAT": 0.28, "CARROT": 0.12, "TOMATO": 0.25, "STRAWBERRY": 0.25, "MELON": 0.10},
    "weights_mid": {"WHEAT": 0.12, "CARROT": 0.08, "TOMATO": 0.34, "STRAWBERRY": 0.34, "MELON": 0.12},
    "weights_late": {"WHEAT": 0.42, "CARROT": 0.30, "TOMATO": 0.18, "STRAWBERRY": 0.00, "MELON": 0.10},
    "weights_end": {"WHEAT": 0.58, "CARROT": 0.42, "TOMATO": 0.00, "STRAWBERRY": 0.00, "MELON": 0.00},
}

SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
BASE_PRICE = {"WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250, "EGG": 50, "MILK": 160, "WOOL": 200}
FIRST_YIELD = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10}
MAX_YIELD_DAY = {"WHEAT": 4, "CARROT": 3, "MELON": 12}
ONGOING = {"TOMATO", "STRAWBERRY"}


def _load_submission_params():
    p = Path(__file__).with_name("champion.json")
    if not p.exists():
        return copy.deepcopy(DEFAULT_PARAMS)
    try:
        data = json.loads(p.read_text())
        if isinstance(data, dict) and isinstance(data.get("params"), dict):
            data = data["params"]
        out = copy.deepcopy(DEFAULT_PARAMS)
        for k, v in data.items():
            if k in out:
                out[k] = v
        return out
    except Exception:
        return copy.deepcopy(DEFAULT_PARAMS)


def _weights(day, params):
    if day <= 4:
        return params["weights_early"]
    if day <= 16:
        return params["weights_mid"]
    if day <= 22:
        return params["weights_late"]
    return params["weights_end"]


def _is_viable(crop, day):
    remain = 30 - day
    if crop in {"WHEAT", "CARROT"}:
        return remain >= FIRST_YIELD[crop] + 1
    if crop == "TOMATO":
        return remain >= 9
    if crop == "STRAWBERRY":
        return remain >= 11
    if crop == "MELON":
        return remain >= 11
    return False


def _crop_counts(tiles):
    out = {k: 0 for k in SEED_COST}
    for row in tiles:
        for t in row:
            if isinstance(t, dict) and t.get("kind") == "PLANT":
                c = t.get("crop")
                if c in out:
                    out[c] += 1
    return out


def _choose_crop(day, tiles, seed_budget, params):
    weights = _weights(day, params)
    counts = _crop_counts(tiles)
    choices = []
    for crop, w in weights.items():
        if w <= 0 or seed_budget.get(crop, 0) <= 0 or not _is_viable(crop, day):
            continue
        ratio = counts.get(crop, 0) / max(w, 1e-6)
        choices.append((ratio, SEED_COST[crop], crop))
    if not choices:
        return None
    choices.sort()
    return choices[0][2]


def _task_for_tile(tile, day, step, can_plant):
    if tile == "LOCKED":
        return None
    if tile is None:
        return (24, "PLANT") if can_plant else None
    if not isinstance(tile, dict):
        return None
    kind = tile.get("kind")
    if kind == "WEED":
        return (82, "DIG")
    if kind == "PLANT":
        crop = tile.get("crop")
        if not tile.get("watered_today", False):
            urgency = 112 if int(tile.get("consecutive_unwatered", 0)) >= 1 else 76
            return (urgency, "WATER")
        y = int(tile.get("yield_units", 0) or 0)
        if y > 0:
            age = day - int(tile.get("planted_day", day))
            if crop in ONGOING:
                return (92, "HARVEST")
            if crop in MAX_YIELD_DAY and age >= MAX_YIELD_DAY[crop]:
                return (108, "HARVEST")
            return (70 + min(y, 10), "HARVEST")
        return None
    if kind in {"COOP", "PASTURE"} and tile.get("animal"):
        if not tile.get("fed_today", False):
            urgency = 114 if int(tile.get("consecutive_unfed", 0)) >= 1 else 80
            return (urgency, "FEED")
        if int(tile.get("yield_units", 0) or 0) > 0:
            return (96, "HARVEST")
        if not tile.get("cared_today", False):
            return (38, "CARE")
        if tile.get("fertilizer_available", False):
            return (28, "COLLECT_FERTILIZER")
    return None


def _move_toward(pos, target, salt):
    x, y = pos
    tx, ty = target
    dx, dy = tx - x, ty - y
    if dx == 0 and dy == 0:
        return ["PASS"]
    prefer_x = ((salt + abs(dx) + abs(dy)) % 2 == 0)
    if dx and (prefer_x or not dy):
        return ["EAST" if dx > 0 else "WEST"]
    if dy:
        return ["SOUTH" if dy > 0 else "NORTH"]
    return ["EAST" if dx > 0 else "WEST"]


def _plan_units(obs, params):
    p = obs["player"]
    me = obs["farms"][p]
    tiles = me["tiles"]
    day = int(obs.get("day", 0))
    step = int(obs.get("step", 0))
    seed_budget = dict(obs.get("private", {}).get("seeds", {}))
    for c in SEED_COST:
        seed_budget.setdefault(c, 0)

    units = [me["farmer"]] + list(me.get("hands", []))
    reserved = set()
    actions = []

    for idx, pos in enumerate(units):
        x, y = pos
        tile = tiles[y][x]
        can_plant_here = sum(seed_budget.values()) > 0
        current = _task_for_tile(tile, day, step, can_plant_here)
        if current and (x, y) not in reserved:
            op = current[1]
            if op == "PLANT":
                crop = _choose_crop(day, tiles, seed_budget, params)
                if crop:
                    seed_budget[crop] -= 1
                    actions.append(["PLANT", crop])
                    reserved.add((x, y))
                    continue
            else:
                actions.append([op])
                reserved.add((x, y))
                continue

        best = None
        any_seed = sum(seed_budget.values()) > 0
        for ty, row in enumerate(tiles):
            for tx, t in enumerate(row):
                if (tx, ty) in reserved:
                    continue
                task = _task_for_tile(t, day, step, any_seed)
                if not task:
                    continue
                priority, op = task
                dist = abs(tx - x) + abs(ty - y)
                score = priority * 100 - dist * 7
                key = (score, -dist, -ty, -tx)
                if best is None or key > best[0]:
                    best = (key, (tx, ty), op)
        if best:
            target = best[1]
            reserved.add(target)
            actions.append(_move_toward(pos, target, step + idx))
        else:
            actions.append(["PASS"])

    return actions[0], actions[1:]


def _market_actions(obs, params):
    p = obs["player"]
    me = obs["farms"][p]
    opp = obs["farms"][1 - p]
    private = obs.get("private", {})
    shed = private.get("shed", {})
    seeds = private.get("seeds", {})
    prices = obs.get("market", {}).get("prices", {})
    day = int(obs.get("day", 0))
    hour = int(obs.get("hour", 0))
    money = float(me.get("money", 0) or 0)
    orders = []

    behind = money + 2000 < float(opp.get("money", 0) or 0)
    floor_ratio = params["behind_sell_floor_ratio"] if behind else params["sell_floor_ratio"]
    liquidate = day >= params["late_liquidation_day"]

    sellable = []
    for item, count in shed.items():
        n = int(count or 0)
        if n <= 0 or item == "FERTILIZER":
            continue
        price = float(prices.get(item, BASE_PRICE.get(item, 1)) or 1)
        base = BASE_PRICE.get(item, max(price, 1))
        if liquidate or price >= base * floor_ratio:
            sellable.append((price * n, item, n))
    sellable.sort(reverse=True)
    for _, item, n in sellable[:4]:
        orders.append(["SELL", item, n])

    unlocked = len(me.get("unlocked_quadrants", ["NW"]))
    thresholds = [params["first_land_threshold"], params["second_land_threshold"], params["third_land_threshold"]]
    deadlines = [params["first_land_deadline"], params["second_land_deadline"], params["third_land_deadline"]]
    if unlocked < 4:
        idx = unlocked - 1
        if 0 <= idx < 3 and day <= deadlines[idx] and money >= thresholds[idx] and len(orders) < 10:
            orders.append(["BUY_LAND"])

    hands = len(me.get("hands", []))
    target_hands = params["target_hands"] if day < params["late_hire_stop_day"] else params["late_hands"]
    need_hires = max(0, int(target_hands) - hands)
    while need_hires > 0 and len(orders) < 8:
        orders.append(["HIRE"])
        need_hires -= 1

    if day < 28 and len(orders) < 10:
        tiles = me["tiles"]
        free = sum(1 for row in tiles for t in row if t is None)
        desired_stock = min(int(params["max_seed_stock"]), max(5, int((1 + hands) * params["seed_buffer_per_unit"])))
        current_stock = sum(int(seeds.get(c, 0) or 0) for c in SEED_COST)
        shortage = max(0, min(free + 4, desired_stock) - current_stock)
        weights = _weights(day, params)
        budget = max(0.0, money * params["seed_budget_ratio"])
        buys = []
        if shortage > 0 and (hour < 8 or current_stock < max(3, hands // 2)):
            for crop, w in sorted(weights.items(), key=lambda kv: kv[1], reverse=True):
                if w <= 0 or not _is_viable(crop, day):
                    continue
                qty = max(0, int(round(shortage * w)) - int(seeds.get(crop, 0) or 0))
                if qty <= 0:
                    continue
                affordable = int(budget // SEED_COST[crop])
                qty = min(qty, affordable, 12)
                if qty > 0:
                    buys.append((w, crop, qty))
                    budget -= qty * SEED_COST[crop]
        for _, crop, qty in buys:
            if len(orders) >= 10:
                break
            orders.append(["BUY_SEED", crop, qty])

    return orders[:10]


def make_agent(params=None):
    cfg = copy.deepcopy(DEFAULT_PARAMS)
    if isinstance(params, dict):
        for k, v in params.items():
            if k in cfg:
                cfg[k] = v

    def _agent(obs):
        try:
            farmer, hands = _plan_units(obs, cfg)
            market = _market_actions(obs, cfg)
            return {"farmer": farmer, "hands": hands, "market": market}
        except Exception:
            me = obs.get("farms", [{}])[obs.get("player", 0)] if obs.get("farms") else {}
            return {"farmer": ["PASS"], "hands": [["PASS"] for _ in me.get("hands", [])], "market": []}

    return _agent


SUBMISSION_PARAMS = _load_submission_params()
agent = make_agent(SUBMISSION_PARAMS)
