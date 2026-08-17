#!/usr/bin/env python3
"""Read frozen V73 symbol methods and route observable regime features. No optimizer and no order execution."""
import json,sys
from pathlib import Path
CFG=Path('data/nocut_intraday_allpass_v73.json')

def load_config(path=CFG):
    with open(path,encoding='utf-8') as f:return json.load(f)

def get_symbol(symbol,cfg=None):
    cfg=cfg or load_config();s=symbol.upper().replace('/','').replace('-','')
    if s in cfg['forex']['symbols']:return 'forex',s,cfg['forex']['symbols'][s]
    if s in cfg['crypto']['symbols']:return 'crypto',s,cfg['crypto']['symbols'][s]
    raise KeyError(f'Unknown V73 symbol: {symbol}')

def _route_node(node,features):
    kind=node.get('kind')
    if kind=='leaf':return node['action']
    f=node['feature'];th=node['threshold'];v=float(features[f])
    if kind=='root':return _route_node(node['lo'] if v<=th else node['hi'],features)
    if kind=='split':
        if 'loAction' in node:return node['loAction'] if v<=th else node['hiAction']
        return _route_node(node['lo'] if v<=th else node['hi'],features)
    raise ValueError(f'Unsupported router node: {kind}')

def choose_action(entry,features=None):
    method=entry['method']
    if 'router' not in method:return method.get('style')
    if features is None:raise ValueError('Observable regime features are required for this symbol router')
    action_id=_route_node(method['router'],features)
    actions={a['id']:a for a in method['actions']}
    if action_id not in actions:raise KeyError(f'Router selected missing action id {action_id}')
    return actions[action_id]

def main():
    if len(sys.argv)<2:raise SystemExit('usage: python scripts/nocut_intraday_method_v73.py SYMBOL [JSON_FEATURES]')
    market,sym,e=get_symbol(sys.argv[1]);out={'market':market,'symbol':sym,'timeframe':e['timeframe'],'source':e['source'],'newsProfile':e['newsProfile'],'method':e['method']}
    if len(sys.argv)>=3:out['selectedAction']=choose_action(e,json.loads(sys.argv[2]))
    print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=='__main__':main()
