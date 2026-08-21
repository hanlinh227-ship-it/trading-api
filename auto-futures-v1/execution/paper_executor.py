import json
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path('/opt/trading/trading-api/auto-futures-v1');STATE=ROOT/'state';LOGS=ROOT/'logs'
risk=json.loads((STATE/'risk_decisions.json').read_text(encoding='utf-8'));orders=[]
for symbol,d in risk.get('decisions',{}).items():
    if not d.get('approved'):continue
    orders.append({'timestamp':datetime.now(timezone.utc).isoformat(),'symbol':symbol,'side':d.get('action'),'entry':d.get('entry'),'stop_loss':d.get('stop_loss'),'tp1':d.get('tp1'),'tp2':d.get('tp2'),'tp3':d.get('tp3'),'risk_pct':d.get('risk_pct_research_reference',d.get('risk_pct',.5)),'risk_source':'PAPER_RESEARCH_ONLY','max_leverage':d.get('max_leverage',3),'status':'PAPER_OPEN'})
out={'mode':'PAPER','orders':orders,'policy':{'never_used_for_live_sizing':True,'live_sizing_source':'BINANCE_AVAILABLE_BALANCE'}}
(STATE/'paper_orders.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
with (LOGS/'paper_orders.jsonl').open('a',encoding='utf-8') as f:
    for x in orders:f.write(json.dumps(x)+'\n')
print(json.dumps(out,indent=2));print('NO BINANCE ORDER WAS SENT')
