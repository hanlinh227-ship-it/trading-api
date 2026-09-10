"""V5.1 mixed-farm controller: working-capital-first crops, livestock logistics and fast expansion."""
import copy
import math
from incumbent import DEFAULT_PARAMS, SEED_COST, BASE_PRICE, _move_toward
from features import features

V3_DEFAULT = dict(
    route=True, market=True, endgame=True, distance_cost=7.0, target_hands=11,
    crop_mode='roi', harvest_wait=False, expansion_mode='fast', land_buffer=180,
    fill_target=0.84, fill_priority=84.0, seed_scale=1.45, dynamic_labor=True,
    herd_mode='dynamic', cow_max=8, sheep_max=6, goose_max=0, livestock_start_day=1,
    livestock_cash_buffer=650, feed_carry=5, drop_at=8, fertilizer_mode='adaptive',
    sell_batch=6, structure_radius=4,
)
FIRST = {'WHEAT': 2, 'CARROT': 2, 'TOMATO': 8, 'STRAWBERRY': 10, 'MELON': 10}
MAX_AGE = {'WHEAT': 4, 'CARROT': 3, 'MELON': 12}
CROP_UNITS = {'WHEAT': 6, 'CARROT': 4, 'TOMATO': 4, 'STRAWBERRY': 4, 'MELON': 6}
CROP_DAYS = {'WHEAT': 4, 'CARROT': 3, 'TOMATO': 12, 'STRAWBERRY': 16, 'MELON': 12}
ANIMAL = {
    'GOOSE': {'cost': 300, 'product': 'EGG', 'structure': 'COOP', 'first': 4, 'interval': 1},
    'COW': {'cost': 400, 'product': 'MILK', 'structure': 'PASTURE', 'first': 8, 'interval': 2},
    'SHEEP': {'cost': 500, 'product': 'WOOL', 'structure': 'PASTURE', 'first': 6, 'interval': 3},
}
LAND_COSTS = (1000, 2000, 4000)
EXPANSION = {
    'balanced': {'deadlines': (1, 7, 12), 'buffers': (300, 400, 550)},
    'fast': {'deadlines': (0, 5, 10), 'buffers': (200, 300, 450)},
    'max': {'deadlines': (0, 3, 8), 'buffers': (120, 180, 300)},
}


def validate_params(params):
    p = dict(V3_DEFAULT)
    if params:
        if set(params) - set(p):
            raise ValueError('Unknown V5 parameter')
        p.update(params)
    for k in ('route', 'market', 'endgame', 'harvest_wait', 'dynamic_labor'):
        if type(p[k]) is not bool:
            raise ValueError(k)
    if type(p['target_hands']) is not int or not 5 <= p['target_hands'] <= 14:
        raise ValueError('target_hands')
    if p['crop_mode'] not in ('roi', 'balanced', 'fast_cash', 'demand', 'grains'):
        raise ValueError('crop_mode')
    if p['expansion_mode'] not in EXPANSION:
        raise ValueError('expansion_mode')
    if p['herd_mode'] not in ('none', 'cow_sheep', 'dynamic'):
        raise ValueError('herd_mode')
    if p['fertilizer_mode'] not in ('off', 'herd_only', 'adaptive'):
        raise ValueError('fertilizer_mode')
    ranges = {
        'distance_cost': (1, 40), 'land_buffer': (0, 1600), 'fill_target': (.45, .98),
        'fill_priority': (25, 140), 'seed_scale': (.5, 3), 'livestock_cash_buffer': (0, 4000),
        'feed_carry': (1, 12), 'drop_at': (2, 30), 'sell_batch': (1, 30), 'structure_radius': (2, 8),
    }
    for k, (lo, hi) in ranges.items():
        if not isinstance(p[k], (int, float)) or not math.isfinite(float(p[k])) or not lo <= p[k] <= hi:
            raise ValueError(k)
    for k in ('cow_max', 'sheep_max', 'goose_max', 'livestock_start_day'):
        if type(p[k]) is not int or p[k] < 0:
            raise ValueError(k)
    if p['cow_max'] > 14 or p['sheep_max'] > 14 or p['goose_max'] > 12 or p['livestock_start_day'] > 20:
        raise ValueError('livestock bounds')
    return p


def _animal_targets(f, p):
    if p['herd_mode'] == 'none' or f['day'] < p['livestock_start_day']:
        return {'GOOSE': 0, 'COW': 0, 'SHEEP': 0}
    targets = {'GOOSE': p['goose_max'], 'COW': p['cow_max'], 'SHEEP': p['sheep_max']}
    if p['herd_mode'] == 'cow_sheep':
        targets['GOOSE'] = 0
        return targets
    for animal, spec in ANIMAL.items():
        product = spec['product']; ratio = f['price_ratios'].get(product, 1.0); demand = f['demand'].get(product, 0)
        if ratio < .55 and demand == 0:
            targets[animal] = 0
        elif ratio < .80 and targets[animal] > 2:
            targets[animal] = max(2, targets[animal] // 2)
    if f['demand'].get('EGG', 0) == 0 and f['price_ratios'].get('EGG', 1) < 1.25:
        targets['GOOSE'] = 0
    return targets


def _crop_score(crop, f, p):
    remain_days = max(0.0, f['remaining_turns'] / 24.0)
    if remain_days < FIRST[crop] + .5:
        return -1e9
    ratio = f['price_ratios'].get(crop, 1.0)
    price = BASE_PRICE[crop] * ratio
    score = (price * CROP_UNITS[crop] - SEED_COST[crop]) / max(1, CROP_DAYS[crop])
    score *= .85 + .12 * f['demand'].get(crop, 0)
    score *= max(.45, min(2.2, ratio))

    if not f['full_farm'] and f['money'] < f['next_land_cost'] + p['land_buffer']:
        score *= 2.2 if crop in ('WHEAT', 'CARROT') else .50

    wheat_target = max(5, int(math.ceil(max(0, f['animals']) * .65)))
    if crop == 'WHEAT' and f['crop_counts'].get('WHEAT', 0) < wheat_target:
        score *= 2.4

    if crop == 'MELON' and f['demand'].get('MELON', 0) == 0:
        if ratio < 1.15:
            score *= .10
        if f['crop_counts'].get('MELON', 0) >= 4:
            score *= .08
    if crop in ('CARROT', 'TOMATO') and (ratio > 1.25 or f['demand'].get(crop, 0) >= 2):
        score *= 1.45
    if crop == 'STRAWBERRY' and f['fertilizer_ready'] + f['shed_fertilizer'] > 0:
        score *= 1.35

    # Marginal diversity penalty prevents ROI from degenerating into one-crop monoculture.
    total = max(1, f['plants'])
    desired = {'WHEAT': .42, 'CARROT': .25, 'TOMATO': .13, 'STRAWBERRY': .16, 'MELON': .04}
    if f['animals'] >= 4:
        desired['WHEAT'] = .50; desired['STRAWBERRY'] = .13; desired['MELON'] = .02
    target_count = max(1.0, desired[crop] * max(10, total + 8))
    saturation = (f['crop_counts'].get(crop, 0) + 1) / target_count
    if saturation > 1:
        score /= saturation ** .8
    return score


def _choose_crop(f, seeds, p):
    available = [c for c in SEED_COST if int(seeds.get(c, 0) or 0) > 0]
    if p['crop_mode'] == 'grains':
        available = [c for c in ('WHEAT', 'CARROT') if c in available]
    if not available:
        return None
    scores = [(_crop_score(c, f, p), -SEED_COST[c], c) for c in available]
    scores.sort(reverse=True)
    return scores[0][2] if scores and scores[0][0] > -1e8 else None


def _near_center(pos, size):
    n = size // 2
    return min(abs(pos[0] - x) + abs(pos[1] - y) for x, y in ((n-1,n-1),(n,n-1),(n-1,n),(n,n)))


def _structure_need(f, p):
    """Build only for the visible/purchased herd plus a two-animal pipeline.

    Earlier V5 built the entire target herd's pastures before proving cash flow, starving
    crops of actions. This bounded pipeline keeps structures synchronized with capital.
    """
    targets = _animal_targets(f, p)
    active_pasture = f['animal_counts']['COW'] + f['animal_counts']['SHEEP']
    queued_pasture = f['shed_cows'] + f['shed_sheep']
    desired_pasture = min(targets['COW'] + targets['SHEEP'], active_pasture + queued_pasture + 2)
    pasture_need = max(0, desired_pasture - active_pasture - f['empty_pastures'])
    active_coop = f['animal_counts']['GOOSE']; queued_coop = f['shed_geese']
    desired_coop = min(targets['GOOSE'], active_coop + queued_coop + 1)
    coop_need = max(0, desired_coop - active_coop - f['empty_coops'])
    return pasture_need, coop_need


def _base_tile_task(tile, f, p, can_plant, fill_boost, inv):
    if tile is None:
        return (p['fill_priority'] if fill_boost and can_plant else 28., 'PLANT') if can_plant else None
    if not isinstance(tile, dict):
        return None
    kind = tile.get('kind')
    if kind == 'WEED':
        return (105. if fill_boost else 45., 'DIG')
    if kind == 'PLANT':
        crop = tile['crop']; age = f['day'] - int(tile['planted_day']); y = int(tile.get('yield_units', 0) or 0)
        if f['regime'] == 'endgame':
            return (210. + y, 'HARVEST') if y > 0 and age >= FIRST[crop] else None
        # Keep crops alive first. Harvest follows on later actions after watering.
        if not tile.get('watered_today', False):
            return (180. if int(tile.get('consecutive_unwatered', 0) or 0) >= 1 else 112., 'WATER')
        if p['fertilizer_mode'] != 'off' and int(inv.get('FERTILIZER', 0) or 0) > 0 and crop in ('STRAWBERRY', 'TOMATO') and int(tile.get('fertilized_until_day', -1) or -1) < f['day'] + 1:
            return (94. + 12 * f['price_ratios'].get(crop, 1), 'FERTILIZE')
        if y > 0 and age >= FIRST[crop]:
            if crop in MAX_AGE and p['harvest_wait'] and age < MAX_AGE[crop]:
                return None
            return (142. + min(y, 8), 'HARVEST')
        return None
    if 'animal' in tile:
        if not tile.get('fed_today', False):
            if int(inv.get('WHEAT', 0) or 0) > 0:
                return (235. if int(tile.get('consecutive_unfed', 0) or 0) >= 1 else 190., 'FEED')
            return None
        if not tile.get('cared_today', False):
            return (165., 'CARE')
        if int(tile.get('yield_units', 0) or 0) > 0:
            return (158., 'HARVEST')
        if p['fertilizer_mode'] != 'off' and tile.get('fertilizer_available', False):
            return (60., 'COLLECT_FERTILIZER')
    return None


def plan(obs, f, p, game):
    me = obs['farms'][obs['player']]; tiles = me['tiles']; size = len(tiles)
    units = [me['farmer']] + list(me.get('hands', [])); inventories = obs['private'].get('inventories', [])
    seeds = dict(obs['private'].get('seeds', {})); shed_budget = dict(obs['private'].get('shed', {}))
    reserved, actions = set(), []
    fill_boost = f['productive_utilization'] < p['fill_target']
    n = size // 2; shed_spots = [(n-1,n-1),(n,n-1),(n-1,n),(n,n)]
    pasture_need, coop_need = _structure_need(f, p); targets = _animal_targets(f, p)
    pasture_pickup_slots = max(0, f['empty_pastures']); coop_pickup_slots = max(0, f['empty_coops'])

    def nearest_shed(pos):
        return min(shed_spots, key=lambda q: (abs(q[0]-pos[0])+abs(q[1]-pos[1]), q))

    for idx, pos in enumerate(units):
        x, y = pos; inv = inventories[idx] if idx < len(inventories) else {}; at_shed = tuple(pos) in shed_spots
        inv_total = sum(int(v or 0) for v in inv.values())

        if f['regime'] == 'endgame' and inv_total > 0:
            if at_shed:
                actions.append(['DROP']); continue
            actions.append(_move_toward(pos, nearest_shed(pos), idx + obs['step'])); continue
        if inv_total >= p['drop_at'] and any(k not in ('WHEAT','FERTILIZER','COW','SHEEP','GOOSE') for k in inv):
            if at_shed:
                actions.append(['DROP']); continue
            if f['hour'] >= 17:
                actions.append(_move_toward(pos, nearest_shed(pos), idx + obs['step'])); continue

        carrying_animal = next((a for a in ('COW','SHEEP','GOOSE') if int(inv.get(a,0) or 0) > 0), None)
        if carrying_animal:
            want = ANIMAL[carrying_animal]['structure']; candidates=[]
            for ty,row in enumerate(tiles):
                for tx,t in enumerate(row):
                    if (tx,ty) in reserved: continue
                    if isinstance(t,dict) and t.get('kind') == want and 'animal' not in t:
                        candidates.append((abs(tx-x)+abs(ty-y),ty,tx))
            if candidates:
                _,ty,tx=min(candidates); reserved.add((tx,ty))
                actions.append(['PLACE',carrying_animal] if (tx,ty)==(x,y) else _move_toward(pos,(tx,ty),idx+obs['step'])); continue

        if at_shed:
            picked=False
            for a in ('COW','SHEEP','GOOSE'):
                have=f['animal_counts'].get(a,0)
                slots=coop_pickup_slots if a=='GOOSE' else pasture_pickup_slots
                if int(shed_budget.get(a,0) or 0)>0 and have<targets[a] and slots>0:
                    actions.append(['PICKUP',a,1]);shed_budget[a]-=1;picked=True
                    if a=='GOOSE': coop_pickup_slots-=1
                    else: pasture_pickup_slots-=1
                    break
            if picked: continue
            if f['feed_due']>0 and int(inv.get('WHEAT',0) or 0)==0 and int(shed_budget.get('WHEAT',0) or 0)>0:
                q=min(int(p['feed_carry']),int(shed_budget.get('WHEAT',0) or 0));actions.append(['PICKUP','WHEAT',q]);shed_budget['WHEAT']-=q;continue
            if p['fertilizer_mode']!='off' and int(inv.get('FERTILIZER',0) or 0)==0 and int(shed_budget.get('FERTILIZER',0) or 0)>0 and f['crop_counts'].get('STRAWBERRY',0)+f['crop_counts'].get('TOMATO',0)>0:
                q=min(3,int(shed_budget.get('FERTILIZER',0) or 0));actions.append(['PICKUP','FERTILIZER',q]);shed_budget['FERTILIZER']-=q;continue

        if f['feed_due']>0 and int(inv.get('WHEAT',0) or 0)==0 and not at_shed and f['hour']<17 and int(shed_budget.get('WHEAT',0) or 0)>0:
            dest=nearest_shed(pos);d=abs(x-dest[0])+abs(y-dest[1])
            if d<=3:
                actions.append(_move_toward(pos,dest,idx+obs['step']));continue

        can_plant = _choose_crop(f, seeds, p) is not None
        best=None
        for ty,row in enumerate(tiles):
            for tx,tile in enumerate(row):
                if (tx,ty) in reserved or tile=='LOCKED': continue
                work=_base_tile_task(tile,f,p,can_plant,fill_boost,inv)
                if tile is None and _near_center((tx,ty),size)<=p['structure_radius']:
                    if pasture_need>0: work=(132.,'BUILD_PASTURE')
                    elif coop_need>0: work=(126.,'BUILD_COOP')
                if not work: continue
                priority,op=work;dist=abs(tx-x)+abs(ty-y)
                if dist>=game.get('turnsPerDay',24)-f['hour']: continue
                score=priority-p['distance_cost']*dist+(14 if dist==0 else 0)
                if op=='PLANT' and fill_boost: score+=8
                key=(score,-dist,-ty,-tx)
                if best is None or key>best[0]: best=(key,(tx,ty),op)
        if best is None:
            actions.append(['PASS']);continue
        _,dest,op=best;reserved.add(dest)
        if op=='BUILD_PASTURE': pasture_need=max(0,pasture_need-1)
        elif op=='BUILD_COOP': coop_need=max(0,coop_need-1)
        if dest!=(x,y):
            actions.append(_move_toward(pos,dest,idx+obs['step']));continue
        if op=='PLANT':
            crop=_choose_crop(f,seeds,p)
            if crop is None: actions.append(['PASS']);continue
            seeds[crop]=int(seeds.get(crop,0) or 0)-1;actions.append(['PLANT',crop])
        else:
            actions.append([op])
    return actions[0],actions[1:]


def _sell_orders(obs,f,p,projected_drop=None):
    shed=dict(obs['private'].get('shed',{}));projected_drop=projected_drop or {}
    for k,v in projected_drop.items():shed[k]=shed.get(k,0)+v
    prices=obs['market']['prices'];reserve_wheat=max(0,f['animals']*2-f['carried_wheat']);items=[]
    for item,n0 in shed.items():
        if item not in BASE_PRICE or item=='FERTILIZER':continue
        n=int(n0 or 0)
        if item=='WHEAT':n=max(0,n-reserve_wheat)
        if n<=0:continue
        ratio=f['price_ratios'].get(item,1);floor=.72
        if f['regime'] in ('endgame','market_liquidation'):floor=.03
        elif not f['full_farm'] and f['money']<f['next_land_cost']+p['land_buffer']:floor=.30
        elif f['gap']<-2500:floor=.55
        if ratio>=floor:items.append((ratio*prices.get(item,1),item,n))
    orders=[]
    for _,item,n in sorted(items,reverse=True)[:4]:
        batch=n if f['regime']=='endgame' else min(n,int(p['sell_batch']*(2 if item in ('WHEAT','CARROT') else 1)))
        orders.append(['SELL',item,batch])
    return orders


def _desired_seed_buys(f,p,seeds,slots):
    if slots<=0 or f['day']>=28:return []
    # Keep a modest rolling stock. Huge seed inventories delay land and livestock payback.
    desired=max(8,min(42,int((1+f['hands'])*1.6*p['seed_scale'] + max(0,12-f['plants']))))
    current=sum(int(seeds.get(c,0) or 0) for c in SEED_COST);shortage=max(0,desired-current)
    if shortage<=0:return []
    scored=sorted(((_crop_score(c,f,p),c) for c in SEED_COST),reverse=True);out=[]
    for score,crop in scored:
        if score<=-1e8 or len(out)>=slots:continue
        qty=max(1,min(16,shortage if not out else max(1,shortage//2)))
        out.append(['BUY_SEED',crop,qty]);shortage-=qty
        if shortage<=0:break
    return out


def _fib(n):
    a,b=1,1
    for _ in range(n):a,b=b,a+b
    return a


def _working_floor(f,p):
    # Seed/feed/next-day labor reserve: expansion is useless if it kills the income engine.
    return max(450.0,float(p['livestock_cash_buffer'])) + min(500.0,45.0*f['animals'])


def market_actions(obs,f,p,unit_actions):
    me=obs['farms'][obs['player']];shed=obs['private'].get('shed',{});seeds=obs['private'].get('seeds',{})
    inventories=obs['private'].get('inventories',[]);projected_drop={}
    all_actions=[unit_actions[0]]+unit_actions[1]
    for i,a in enumerate(all_actions):
        if a==['DROP'] and i<len(inventories):
            for k,v in inventories[i].items():projected_drop[k]=projected_drop.get(k,0)+int(v or 0)
    orders=_sell_orders(obs,f,p,projected_drop);projected=float(f['money'])
    for o in orders:
        projected+=.65*float(obs['market']['prices'].get(o[1],BASE_PRICE.get(o[1],1)))*int(o[2])

    unlocked=f['unlocked_quadrants'];mode=EXPANSION[p['expansion_mode']];working=_working_floor(f,p)
    while unlocked<4 and len(orders)<10:
        stage=unlocked-1;cost=LAND_COSTS[stage];deadline=mode['deadlines'][stage]
        # Even when late, never spend the last operating capital. This fixes the V5.0
        # land-reserve deadlock where the farm could neither buy the next field nor seeds.
        buffer=max(working,mode['buffers'][stage]+p['land_buffer'])
        pressure=f['day']>=deadline or f['day']>=max(0,deadline-2) or f['productive_utilization']>=.45
        if projected>=cost+buffer and pressure:
            orders.append(['BUY_LAND']);projected-=cost;unlocked+=1
        else:break

    # Buy the income engine BEFORE repeated hires. One market order can buy many seeds,
    # while every hire consumes an order slot.
    seed_orders=_desired_seed_buys(f,p,seeds,3)
    for order in seed_orders:
        if len(orders)>=10:break
        cost=SEED_COST[order[1]]*int(order[2])
        # Allow productive seed spend whenever cash is below the next land price; otherwise
        # retain a modest land escrow instead of freezing the whole next-land cost.
        escrow=min(600.0,LAND_COSTS[unlocked-1]*.20) if unlocked<4 else 250.0
        if projected-cost>=escrow:
            orders.append(order);projected-=cost

    # Existing animals get feed insurance before new herd purchases.
    feed_need=max(0,int(math.ceil(f['animals']*2.2))-f['shed_wheat']-f['carried_wheat'])
    wheat_price=float(obs['market']['prices'].get('WHEAT',25))
    if feed_need>0 and f['animals']>0 and len(orders)<10:
        q=min(feed_need,12);cost=wheat_price*q
        if projected>=cost+250:
            orders.append(['BUY_PRODUCT','WHEAT',q]);projected-=cost

    targets=_animal_targets(f,p);cutoffs={'COW':19,'SHEEP':21,'GOOSE':23}
    visible={a:f['animal_counts'][a]+int(shed.get(a,0) or 0) for a in ANIMAL}
    new_animals=0
    for a in ('COW','SHEEP','GOOSE'):
        if f['day']>cutoffs[a] or len(orders)>=10:continue
        need=max(0,targets[a]-visible[a])
        # Keep only a small purchased pipeline ahead of built structures.
        if a in ('COW','SHEEP'):
            capacity=f['empty_pastures']+2
            queued=f['shed_cows']+f['shed_sheep']
            need=min(need,max(0,capacity-queued))
        else:
            need=min(need,max(0,f['empty_coops']+1-f['shed_geese']))
        while need>0 and new_animals<2 and len(orders)<10 and projected>=ANIMAL[a]['cost']+working:
            orders.append(['BUY_ANIMAL',a,1]);projected-=ANIMAL[a]['cost'];need-=1;new_animals+=1

    if p['fertilizer_mode']=='adaptive' and len(orders)<10 and f['plants']>=10 and f['hands']>=8:
        fert_price=float(obs['market']['prices'].get('FERTILIZER',100));fert_have=f['shed_fertilizer']+f['carried_fertilizer']+f['fertilizer_ready']
        fert_need=max(0,min(8,f['crop_counts'].get('STRAWBERRY',0)+f['crop_counts'].get('TOMATO',0))-fert_have)
        if fert_need>0 and fert_price<=35 and projected>=fert_price*fert_need+working:
            orders.append(['BUY_PRODUCT','FERTILIZER',fert_need]);projected-=fert_price*fert_need

    # Hire only workers the current economy can use, at most three per turn. Hands reset
    # nightly, so blindly rehiring 12-14 before production exists can drain the account.
    workload=f['water_due']+2*f['feed_due']+f['care_due']+f['ripe']+f['animal_ripe']+max(0,10-f['plants'])
    acreage={1:5,2:7,3:9,4:11}[min(4,max(1,unlocked))]
    target=min(14,max(5,min(p['target_hands'],acreage+2),5+int(math.ceil(workload/10.0)))) if p['dynamic_labor'] else p['target_hands']
    hire_idx=int(me.get('hires_today',0) or 0);to_hire=min(3,max(0,target-f['hands']))
    for _ in range(to_hire):
        if len(orders)>=10:break
        cost=_fib(hire_idx);hire_idx+=1
        if projected>=cost+250:
            orders.append(['HIRE']);projected-=cost
        else:break
    return orders[:10]


def decide(obs,game,p):
    f=features(obs,game)
    farmer,hands=plan(obs,f,p,game) if p['route'] else (['PASS'],[['PASS'] for _ in obs['farms'][obs['player']].get('hands',[])])
    orders=market_actions(obs,f,p,(farmer,hands)) if p['market'] else []
    return {'farmer':farmer,'hands':hands,'market':orders}


def make_v3(params=None):
    p=validate_params(params)
    def agent(obs,configuration=None):
        return decide(obs,configuration or {},p)
    return agent
