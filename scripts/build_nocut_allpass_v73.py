#!/usr/bin/env python3
"""Build the frozen canonical no-CUT intraday configuration from completed offline optimizers."""
import json
from pathlib import Path
from scripts.offline_crypto_v28_separate import PROFILE
import scripts.offline_forex_precision_evolver_v15 as fx
import scripts.offline_crypto_precision_evolver_v36 as cr

OUT='data/nocut_intraday_allpass_v73.json';DOC='docs/checkpoints/NO_CUT_INTRADAY_ALLPASS_V73.md'
FX66=set('USDJPY AUDUSD NZDUSD EURAUD EURCAD GBPJPY GBPAUD GBPNZD AUDCAD NZDJPY CADJPY'.split())
CR69=set('SOL HYPE XRP ALGO APT DOT ETC FIL INJ JTO ONDO PENGU RENDER TIA UNI WLD AIXBT FARTCOIN LIT PUMP XPL ZEC'.split())
CCY={
 'USD':['Fed/FOMC','US CPI/PCE/NFP','US10Y + DXY','Treasury/liquidity conditions'],
 'EUR':['ECB','Eurozone CPI/PMI','Germany growth/industrial data','EU fiscal/political risk'],
 'GBP':['BoE','UK CPI/wages/jobs','UK GDP/retail sales','UK fiscal/political risk'],
 'JPY':['BoJ','MoF intervention risk','Japan/Tokyo CPI','JGB yields + global risk'],
 'CHF':['SNB','Swiss CPI','safe-haven flows','European risk sentiment'],
 'CAD':['BoC','Canada CPI/jobs/GDP','WTI crude oil','US-Canada growth differential'],
 'AUD':['RBA','Australia CPI/jobs','China PMIs/growth','iron ore + risk sentiment'],
 'NZD':['RBNZ','New Zealand CPI/jobs','China growth','dairy/commodity risk sentiment'],
}
PROFILE_DRIVERS={
 'BTC_CORE':['BTC ETF/treasury demand','miner/on-chain flows','macro liquidity/rates','BTC dominance'],
 'ETH_CORE':['ETH ETF/staking flows','Ethereum upgrades','L2 activity/fees','ETH/BTC relative strength'],
 'SOL_ECOSYSTEM':['Solana network activity','SOL ecosystem launches','validator/staking flows','SOL relative strength'],
 'MEME':['social attention velocity','whale/exchange flows','meme-sector breadth','listing/delisting catalysts'],
 'SOL_MEME':['Solana meme breadth','DEX volume/liquidity','social/whale activity','SOL regime'],
 'DEFI':['protocol TVL/fees','governance/upgrades','incentives/unlocks','ETH/DeFi breadth'],
 'L1':['chain upgrades/adoption','staking/validator flows','ecosystem TVL/activity','BTC regime'],
 'L2':['rollup activity/fees','token unlocks','Ethereum roadmap','L2 relative strength'],
 'AI_COMPUTE':['AI/compute narrative','network demand/revenue','token unlocks','AI-sector breadth'],
 'AI_INFOFI':['AI/InfoFi product growth','attention/data demand','unlocks/listings','AI-sector breadth'],
 'AI_AGENT':['AI-agent adoption','ecosystem integrations','unlocks/listings','AI-sector breadth'],
 'AI_DATA':['AI data demand','network usage','unlocks/listings','AI-sector breadth'],
 'RWA':['RWA adoption/partnerships','regulation','token unlocks','RWA sector flows'],
 'ORACLE_RWA':['oracle integrations','RWA/DeFi adoption','token economics','ETH/DeFi regime'],
 'INTERCHAIN':['IBC/interchain activity','ecosystem upgrades','staking/unlocks','L1 breadth'],
 'BTC_ECOSYSTEM':['BTC ecosystem activity','BTC trend/dominance','protocol upgrades','token unlocks'],
 'BTC_BETA':['BTC trend/dominance','relative beta to BTC','payments/adoption news','liquidity flows'],
 'PERP_DEX':['perp DEX volume/OI','protocol incentives','token unlocks','leverage regime'],
 'L1_PAYMENTS':['payments adoption','chain usage','staking/network changes','BTC regime'],
 'PAYMENTS':['payments/remittance adoption','regulation','institutional partnerships','BTC regime'],
 'ETH_STAKING':['ETH staking flows','LST/LRT market share','Ethereum upgrades','DeFi liquidity'],
 'SOL_DEFI':['Solana DeFi TVL/volume','SOL trend','protocol incentives','token unlocks'],
 'POW_L1':['PoW miner/hashrate economics','chain upgrades','BTC correlation','exchange liquidity'],
 'STORAGE':['storage demand/network usage','protocol upgrades','token unlocks','AI/data narrative'],
 'MODULAR':['data-availability adoption','ecosystem integrations','token unlocks','L1/L2 breadth'],
 'PRIVACY':['privacy regulation','network adoption','exchange access','BTC regime'],
 'IDENTITY':['identity/adoption integrations','network activity','unlocks/listings','sector flows'],
 'IP_RWA':['IP/RWA partnerships','licensing/adoption','token unlocks','RWA flows'],
 'MESSAGING_L1':['messaging ecosystem growth','chain usage','unlocks/listings','BTC regime'],
 'OTHER':['project announcements','token unlocks/listings','exchange/on-chain flows','BTC regime'],
}

def load(p):return json.load(open(p,encoding='utf-8'))
def wr_of(r):
 for k in ('development','mayJul30Development','walkForwardMayJuly'):
  s=r.get(k)
  if s:
   for w in ('wrAllTrades','wrAllSelected','wr'):
    if w in s:return float(s[w])
 return None

def main():
 v64=load('data/offline_forex_nocut_geometry_v64.json');v66=load('data/offline_forex_nocut_refine_v66.json')
 v69=load('data/offline_crypto_h1_coordinate_v69.json');v70=load('data/offline_crypto_h1_regime_router_v70.json');v71=load('data/offline_crypto_h1_special_v71.json');v72=load('data/offline_crypto_4h_ton_ip_v72.json')
 forex={}
 for sym in fx.PAIRS:
  src='V66' if sym in FX66 else 'V64';r=(v66 if src=='V66' else v64)['results'][sym]
  if r.get('status')!='PASS':raise RuntimeError(f'Forex {sym} not PASS in {src}')
  a,b=sym[:3],sym[3:];forex[sym]={'source':src,'timeframe':'H1','method':r,'newsProfile':{'base':{a:CCY[a]},'quote':{b:CCY[b]},'liveRoutingRule':'Use point-in-time news for both currencies to choose/confirm the pair-specific regime/action; because daily trading is mandatory, news changes execution geometry rather than creating NO TRADE.'}}
 crypto={}
 for sym in cr.SYMBOLS:
  if sym in ('TON','IP'):src='V72';r=v72['results'][sym];tf='4H'
  elif sym in ('HBAR','TAO'):src='V71';r=v71['results'][sym];tf='H1'
  elif sym in CR69:src='V69';r=v69['results'][sym];tf='H1'
  else:src='V70';r=v70['results'][sym];tf='H1'
  if r.get('status')!='PASS':raise RuntimeError(f'Crypto {sym} not PASS in {src}')
  prof=PROFILE.get(sym,'OTHER');crypto[sym]={'source':src,'timeframe':tf,'method':r,'newsProfile':{'profile':prof,'symbolSpecific':[f'{sym} project/protocol announcements',f'{sym} token unlock/supply schedule',f'{sym} exchange/on-chain/whale flows'], 'profileDrivers':PROFILE_DRIVERS.get(prof,PROFILE_DRIVERS['OTHER']),'liveRoutingRule':'Refresh symbol-specific news plus BTC/market regime before the daily/session decision. News routes among the frozen symbol actions; it does not silently convert a mandatory trading day into NO TRADE.'}}
 badfx=[s for s,r in forex.items() if (wr_of(r['method']) or 0)<80];badcr=[s for s,r in crypto.items() if (wr_of(r['method']) or 0)<80]
 if badfx or badcr:raise RuntimeError(f'WR gate failed fx={badfx} crypto={badcr}')
 out={'version':'NO_CUT_INTRADAY_ALLPASS_V73','classification':'EXPOSED DEVELOPMENT ALL-PASS; NOT UNTOUCHED OOS','created':'2026-08-17','hardRules':{'cutUsed':False,'noTradeAllowed':False,'minimumTradesPerDay':1,'maximumTradesPerDay':3,'currentFrozenDevelopmentStylesUseTradesPerDay':1,'rrAllowed':[1.0,2.0],'currentPassingRR':1.0,'sameBarTPandSL':'SL conservative','timeout':'non-win'},'forex':{'universeCount':len(forex),'passCount':len(forex),'allPassed':True,'symbols':forex},'crypto':{'universeCount':len(crypto),'passCount':len(crypto),'allPassed':True,'symbols':crypto},'integrity':{'optimizationPeriod':'2026-05-01 through 2026-07-30 development rows','warning':'These all-pass maps were optimized on exposed development data. Freeze before any independent validation; do not describe development WR as future/live guarantee.'}}
 Path(OUT).parent.mkdir(parents=True,exist_ok=True);json.dump(out,open(OUT,'w'),indent=2)
 minfx=min(wr_of(r['method']) for r in forex.values());mincr=min(wr_of(r['method']) for r in crypto.values())
 doc=f'''# NO-CUT INTRADAY ALL-PASS V73\n\nUpdated: 2026-08-17 UTC+7\n\n## Locked user target\n- No CUT.\n- No NO-TRADE day.\n- 1 to 3 trades per symbol per day; current passing development maps use exactly 1/day.\n- RR only 1:1 or 1:2; current passing maps use 1:1.\n- Every Forex pair and every Crypto symbol must have development WR >=80%.\n- Every symbol has its own method and news/context profile.\n\n## Development result\n- Forex: 28/28 PASS; minimum per-pair WR {minfx:.2f}%.\n- Crypto: 61/61 PASS; minimum per-coin WR {mincr:.2f}%.\n- H1 is canonical for Forex and 59 crypto symbols. TON/IP use their own 4H regime method because full H1 spot history was unavailable in the common source.\n- All results count TIMEOUT as a non-win and same-bar TP+SL as SL.\n\n## Canonical sources\n- Forex: V64 base + V66 targeted refinement.\n- Crypto: V69 static passes + V70 observable regime routers + V71 HBAR/TAO special H1 + V72 TON/IP special 4H.\n- Exact frozen methods, routers, actions, statistics and news profiles are in `{OUT}`.\n\n## Integrity\n**This is an exposed-development all-pass checkpoint, not untouched OOS validation.** May-Jul was used to search/refine the maps. The next integrity step is to freeze V73 unchanged and test on independent history before calling it robust/live-proven.\n'''
 Path(DOC).parent.mkdir(parents=True,exist_ok=True);Path(DOC).write_text(doc,encoding='utf-8');print(json.dumps({'forex':len(forex),'crypto':len(crypto),'minForexWR':minfx,'minCryptoWR':mincr},indent=2),flush=True)
if __name__=='__main__':main()
