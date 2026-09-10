"""Stateless V3 controller. Incumbent remains separately frozen and callable."""
import copy
from incumbent import DEFAULT_PARAMS, SEED_COST, BASE_PRICE, _market_actions, _move_toward, _choose_crop, _plan_units
from features import features

V3_DEFAULT = dict(route=True, market=True, endgame=True, distance_cost=9.0,
                  target_hands=11, crop_mode='balanced', harvest_wait=True)
FIRST = {'WHEAT':2,'CARROT':2,'TOMATO':8,'STRAWBERRY':10,'MELON':10}
MAX_AGE = {'WHEAT':4,'CARROT':3,'MELON':12}


def validate_params(params):
    p = dict(V3_DEFAULT)
    if params:
        if set(params)-set(p): raise ValueError('Unknown V3 parameter')
        p.update(params)
    for k in ('route','market','endgame','harvest_wait'):
        if type(p[k]) is not bool: raise ValueError(k)
    if type(p['target_hands']) is not int or not 5 <= p['target_hands'] <= 14: raise ValueError('target_hands')
    if not isinstance(p['distance_cost'],(int,float)) or not 1 <= p['distance_cost'] <= 40: raise ValueError('distance_cost')
    if p['crop_mode'] not in ('balanced','grains','demand'): raise ValueError('crop_mode')
    return p


def strategic_params(obs, f, p):
    cfg=copy.deepcopy(DEFAULT_PARAMS)
    cfg['target_hands']=p['target_hands']
    if p['crop_mode']=='grains':
        for name in ('weights_early','weights_mid','weights_late','weights_end'):
            cfg[name]={'WHEAT':.65,'CARROT':.35,'TOMATO':0.,'STRAWBERRY':0.,'MELON':0.}
    elif p['crop_mode']=='demand':
        for name in ('weights_early','weights_mid','weights_late','weights_end'):
            weights=cfg[name]
            for crop in weights:
                weights[crop]*=max(.35,min(1.8,f['price_ratios'].get(crop,1)))
            total=sum(weights.values())
            cfg[name]={k:v/total for k,v in weights.items()}
    if p['market']:
        # Price floor adapts to own capacity/liquidity and observable competition.
        floor=cfg['sell_floor_ratio']
        if f['regime']=='market_liquidation' or f['money']<350: floor=.05
        elif f['regime']=='comeback': floor=.60
        elif f['opponent_behavior']=='high_labor': floor=.68
        cfg['sell_floor_ratio']=floor
        cfg['behind_sell_floor_ratio']=min(floor,.62)
    return cfg


def task(tile, day, step, can_plant, p, final_day=False):
    if tile is None: return (24.,'PLANT') if can_plant and not final_day else None
    if not isinstance(tile,dict): return None
    if tile.get('kind')=='WEED': return (30.,'DIG') if can_plant and not final_day else None
    if tile.get('kind')!='PLANT': return None
    crop=tile['crop'];age=day-tile['planted_day'];y=tile.get('yield_units',0)
    mature=age>=FIRST[crop]
    if final_day:
        return (130.+y,'HARVEST') if y>0 and mature else None
    if y>0 and mature:
        if crop in MAX_AGE and p['harvest_wait'] and age<MAX_AGE[crop]:
            if not tile.get('watered_today'): return (80.,'WATER')
            return None
        return (110.+min(y,8),'HARVEST')
    if not tile.get('watered_today'):
        return (140. if tile.get('consecutive_unwatered',0)>=1 else 76.,'WATER')
    return None


def plan(obs, f, p, cfg, game):
    me=obs['farms'][obs['player']];tiles=me['tiles'];size=len(tiles)
    units=[me['farmer']]+me.get('hands',[])
    seeds=dict(obs['private'].get('seeds',{}))
    inventories=obs['private'].get('inventories',[])
    reserved=set();actions=[]
    final=p['endgame'] and f['regime']=='endgame'
    n=size//2;shed_spots=[(n-1,n-1),(n,n-1),(n-1,n),(n,n)]
    worktiles=copy.deepcopy(tiles)  # sequential reservations also update crop-mix counts
    for idx,pos in enumerate(units):
        x,y=pos; inv=inventories[idx] if idx<len(inventories) else {}
        if final and sum(inv.values())>0:
            dest=min(shed_spots,key=lambda q:(abs(q[0]-x)+abs(q[1]-y),q))
            # Leave enough time for DROP + SELL; don't lose carried terminal assets.
            if tuple(pos) in shed_spots:
                actions.append(['DROP']);continue
            actions.append(_move_toward(pos,dest,idx+obs['step']));continue
        can_plant=_choose_crop(f['day'],worktiles,seeds,cfg) is not None
        best=None
        for ty,row in enumerate(tiles):
            for tx,tile in enumerate(row):
                if (tx,ty) in reserved: continue
                work=task(tile,f['day'],obs['step'],can_plant,p,final)
                if not work: continue
                priority,op=work;dist=abs(tx-x)+abs(ty-y)
                if final:
                    to_shed=min(abs(tx-a)+abs(ty-b) for a,b in shed_spots)
                    if dist+1+to_shed+1>f['remaining_turns']: continue
                # Finite daily horizon: workers reset each night.
                if dist>=game.get('turnsPerDay',24)-f['hour']: continue
                score=priority-p['distance_cost']*dist+(12 if dist==0 else 0)
                key=(score,-dist,-ty,-tx)
                if best is None or key>best[0]:best=(key,(tx,ty),op)
        if best is None: actions.append(['PASS']);continue
        _,dest,op=best;reserved.add(dest)
        if dest!=(x,y): actions.append(_move_toward(pos,dest,idx+obs['step']));continue
        if op=='PLANT':
            crop=_choose_crop(f['day'],worktiles,seeds,cfg)
            seeds[crop]-=1;worktiles[y][x]={'kind':'PLANT','crop':crop}
            actions.append(['PLANT',crop])
        else: actions.append([op])
    return actions[0],actions[1:]


def decide(obs, game, p):
    f=features(obs,game);cfg=strategic_params(obs,f,p)
    farmer,hands=plan(obs,f,p,cfg,game) if p['route'] else _plan_units(obs,cfg)
    orders=_market_actions(obs,cfg)
    if p['endgame'] and f['regime']=='endgame':
        # DROP is executed before market, so sell possible carried products too.
        shed=dict(obs['private'].get('shed',{}))
        for inv in obs['private'].get('inventories',[]):
            for k,v in inv.items():shed[k]=shed.get(k,0)+v
        orders=[['SELL',k,int(v)] for k,v in sorted(shed.items()) if v>0 and k in BASE_PRICE and k!='FERTILIZER']
        if f['hour']<3:
            need=max(0,min(6,p['target_hands'])-f['hands'])
            orders.extend([['HIRE'] for _ in range(min(need,10-len(orders)))])
    return {'farmer':farmer,'hands':hands,'market':orders[:10]}


def make_v3(params=None):
    p=validate_params(params)
    def agent(obs, configuration=None):
        # Fail loudly in simulator instead of disguising policy bugs as PASS.
        return decide(obs,configuration or {},p)
    return agent
