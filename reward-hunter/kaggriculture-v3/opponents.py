"""Original local variants, not competitor identities/code."""
from incumbent import make_agent

FAMILIES={
 'incumbent':{},
 'expansion':{'first_land_threshold':1800,'second_land_threshold':3500,'third_land_threshold':6500,'target_hands':13},
 'cash':{'first_land_threshold':100000,'second_land_threshold':100000,'target_hands':7,'sell_floor_ratio':.45,'behind_sell_floor_ratio':.45},
 'early_sell':{'sell_floor_ratio':.05,'behind_sell_floor_ratio':.05},
 'hoarder':{'sell_floor_ratio':1.15,'behind_sell_floor_ratio':1.05,'late_liquidation_day':28},
 'labor':{'target_hands':14,'late_hands':8},
 'grains':{k:{'WHEAT':.7,'CARROT':.3,'TOMATO':0.,'STRAWBERRY':0.,'MELON':0.} for k in ('weights_early','weights_mid','weights_late','weights_end')},
}
SUITE=('starter',*FAMILIES)


def opponent(name):
    if name=='starter':return 'starter'
    return make_agent(FAMILIES[name])
