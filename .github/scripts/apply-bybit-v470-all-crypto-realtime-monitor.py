from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def patch(path,replacements):
    p=ROOT/path;s=p.read_text()
    for old,new in replacements:
        if new in s:
            continue
        if old not in s:
            raise SystemExit(f'MISSING_PATTERN {path}: {old[:160]}')
        s=s.replace(old,new,1)
    p.write_text(s)

# 1) Bridge: wider dynamic WS coverage + market telemetry for Android mark-to-market.
patch(Path('bybit-live-bridge/bybit_live_bridge.py'),[
("MAX_WS_SYMBOLS=max(18,min(72,int(os.environ.get('BYBIT_MAX_WS_SYMBOLS','48'))))","MAX_WS_SYMBOLS=max(18,min(120,int(os.environ.get('BYBIT_MAX_WS_SYMBOLS','72'))))"),
("if turn>=12_000_000 and spread<=9.5:rows.append((turn,-spread,s))","if turn>=1_000_000 and spread<=20.0:rows.append((turn,-spread,s))"),
("    return {'healthy':connected>=min_connected and fresh>=min_fresh,'connectedCount':connected,'readyCount':ready,'freshCount':fresh,'totalCount':len(snaps),'p50DataAgeMs':pct(.50),'p95DataAgeMs':pct(.95),'maxDataAgeMs':int(max(ages)) if ages else None,'staleSymbols':sorted(stale,key=lambda x:x['dataAgeMs'],reverse=True)[:20],'freshThresholdMs':5000,'timestamp':now}\n\n\nMICROS=",
"    return {'healthy':connected>=min_connected and fresh>=min_fresh,'connectedCount':connected,'readyCount':ready,'freshCount':fresh,'totalCount':len(snaps),'p50DataAgeMs':pct(.50),'p95DataAgeMs':pct(.95),'maxDataAgeMs':int(max(ages)) if ages else None,'staleSymbols':sorted(stale,key=lambda x:x['dataAgeMs'],reverse=True)[:20],'freshThresholdMs':5000,'timestamp':now}\n\ndef market_telemetry(snaps):\n    now=int(time.time()*1000);out={}\n    for symbol,x in snaps.items():\n        if not x.get('ok'):continue\n        d=x.get('data') or {};book=d.get('book') or {};trades=d.get('trades') or {};bid=float(book.get('bestBid') or 0);ask=float(book.get('bestAsk') or 0);mid=float(book.get('mid') or ((bid+ask)/2 if bid>0 and ask>0 else 0));last=float(trades.get('lastPrice') or 0);px=last or mid;bt=int(book.get('updateTime') or 0);tt=int(trades.get('lastTradeTime') or trades.get('updateTime') or 0);fresh=max(bt,tt);age=max(0,now-fresh) if fresh>0 else 999999\n        out[symbol]={'lastPrice':px,'mid':mid,'bid':bid,'ask':ask,'ageMs':age,'fresh':age<=5000,'source':'VPS_BYBIT_WS'}\n    return out\n\n\nMICROS="),
("'maxWsSymbols':MAX_WS_SYMBOLS,'wsTelemetry':ws_telemetry(snaps),'microstructure'","'maxWsSymbols':MAX_WS_SYMBOLS,'wsTelemetry':ws_telemetry(snaps),'marketTelemetry':market_telemetry(snaps),'microstructure'")
])

# 2) All active crypto USDT perpetuals may participate; only execution-unsafe products remain blocked.
p=ROOT/'cloudflare-worker/bybit-dynamic-universe.js';s=p.read_text()
old="""  else if(ageDays!==null&&ageDays<3){classification='WATCH_NEW';reason='NEW_LISTING_OBSERVATION_LT_3D';}
  else if(ageDays!==null&&ageDays<14){classification='WATCH_NEW';reason='NEW_LISTING_OBSERVATION_LT_14D';}
  else if(core&&turnover>=Math.max(8_000_000,num(profile?.minTurnoverUsd)*.35)&&spreadBps<=Math.max(3.5,num(profile?.maxSpreadBps))){classification='TRADE_CORE';eligible=true;reason=null;}
  else if(turnover>=150_000_000&&spreadBps<=3.5){classification='TRADE_STABLE';eligible=true;reason=null;}
  else if(turnover>=22_000_000&&spreadBps<=8.0&&(Math.abs(change)>=.007||oiValue>=10_000_000)){classification='TRADE_SCALP_FAST';eligible=true;reason=null;}
  else if(turnover>=55_000_000&&spreadBps<=6.5){classification='TRADE_STABLE';eligible=true;reason=null;}
  else if(turnover<6_000_000||spreadBps>12){classification='WATCH_THIN';reason=turnover<6_000_000?'TURNOVER_TOO_LOW':'SPREAD_TOO_WIDE';}
  else {classification='WATCH_READY';reason='OBSERVE_UNTIL_EDGE_AND_EXECUTION_QUALITY_IMPROVE';}
"""
new="""  else if(!(bid>0&&ask>0&&last>0)){classification='WATCH_EXECUTION_UNSAFE';reason='NO_EXECUTABLE_TWO_SIDED_MARKET';}
  else if(turnover<500_000||spreadBps>20){classification='WATCH_EXECUTION_UNSAFE';reason=turnover<500_000?'TURNOVER_BELOW_ABSOLUTE_EXECUTION_FLOOR':'SPREAD_ABOVE_ABSOLUTE_EXECUTION_FLOOR';}
  else {classification=core?'TRADE_CORE':'TRADE_ALL_CRYPTO';eligible=true;reason=null;}
"""
if new not in s:
    if old not in s:raise SystemExit('MISSING_PATTERN dynamic classification')
    s=s.replace(old,new,1)
s=s.replace("BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V4_BROAD_OPPORTUNITY_PROMOTION","BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V5_ALL_ACTIVE_CRYPTO",2)
s=s.replace("promotionCandidates=watchOnly.filter(x=>x.ageDays===null||x.ageDays>=14).filter(x=>x.turnover>=4_000_000&&x.spreadBps<=11.5&&promotionPotential(x)>=.40)","promotionCandidates=watchOnly.filter(x=>x.classification==='WATCH_READY').filter(x=>x.turnover>=4_000_000&&x.spreadBps<=11.5&&promotionPotential(x)>=.40)")
p.write_text(s)

# 3) Dynamic symbols get a conservative low-risk profile but no artificial $15m turnover barrier.
p=ROOT/'cloudflare-worker/bybit-coin-profiles.js';s=p.read_text()
s=s.replace("authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V6_BROAD_OPPORTUNITY_SAME_RISK_BUDGET'","authority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V7_ALL_CRYPTO_SAME_RISK_BUDGET'")
s=s.replace("deepScanCount:12,promotionScanCount:12","deepScanCount:16,promotionScanCount:0")
old="const DYNAMIC_PROFILE_BASE=freeze({...base,marketCapClass:'DYNAMIC',riskMult:.55,targetMult:1.04,stopMult:1.04,signalGain:.96,flowThresholdMult:1.03,qualityThresholdMult:1.04,bookToleranceMult:.95,leverageMult:.90,maxSpreadBps:9.0,minTurnoverUsd:15_000_000,runnerMaxR:4.2,holdMult:1.05,minNetProfitMult:1.00,profitGivebackMult:.96,reverseExitEvidenceMult:1.05,style:'BALANCED',correlationGroup:'DYNAMIC_ALT',priority:42,dynamicProfile:true});"
new="const DYNAMIC_PROFILE_BASE=freeze({...base,marketCapClass:'DYNAMIC',riskMult:.35,targetMult:1.02,stopMult:1.06,signalGain:.94,flowThresholdMult:1.05,qualityThresholdMult:1.12,bookToleranceMult:.92,leverageMult:.70,maxSpreadBps:20.0,minTurnoverUsd:500_000,runnerMaxR:3.8,holdMult:1.00,minNetProfitMult:1.00,profitGivebackMult:.92,reverseExitEvidenceMult:1.08,style:'BALANCED',correlationGroup:'DYNAMIC_ALT',priority:35,dynamicProfile:true});"
if new not in s:
    if old not in s:raise SystemExit('MISSING_PATTERN dynamic profile')
    s=s.replace(old,new,1)
p.write_text(s)

# 4) Rotate many more non-head symbols through each scan cycle.
p=ROOT/'cloudflare-worker/bybit-multi-asset-controller.js';s=p.read_text()
old="const headCount=Math.max(1,Math.min(n,Math.max(2,n-2))),head=eligible.slice(0,headCount),tail=eligible.slice(headCount),rotateCount=Math.max(0,n-head.length),out=[...head];"
new="const headCount=Math.max(1,Math.min(n,6)),head=eligible.slice(0,headCount),tail=eligible.slice(headCount),rotateCount=Math.max(0,n-head.length),out=[...head];"
if new not in s:
    if old not in s:raise SystemExit('MISSING_PATTERN deep rotation')
    s=s.replace(old,new,1)
p.write_text(s)

# 5) Runtime contract versioning.
p=ROOT/'cloudflare-worker/bybit-runtime-contract.js';s=p.read_text()
s=s.replace("BYBIT_MULTI_ASSET_RUNTIME_V24_BROAD_SCALP_OPPORTUNITY_NETWORK","BYBIT_MULTI_ASSET_RUNTIME_V25_ALL_CRYPTO_SCALP_NETWORK")
s=s.replace("BYBIT-MULTI-STATEFLOW-4.6.0","BYBIT-MULTI-STATEFLOW-4.7.0")
s=s.replace("BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V4_BROAD_OPPORTUNITY_PROMOTION","BYBIT_DYNAMIC_CRYPTO_SCALP_UNIVERSE_V5_ALL_ACTIVE_CRYPTO")
s=s.replace("portfolioAuthority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V5_CONTINUOUS_RISK_SLOTS'","portfolioAuthority:'DYNAMIC_BYBIT_SCALP_PORTFOLIO_V7_ALL_CRYPTO_SAME_RISK_BUDGET'")
s=s.replace("universeClasses:['TRADE_CORE','TRADE_STABLE','TRADE_SCALP_FAST','TRADE_PROMOTED','WATCH_NEW','WATCH_READY','WATCH_THIN','DO_NOT_TRADE']","universeClasses:['TRADE_CORE','TRADE_ALL_CRYPTO','WATCH_EXECUTION_UNSAFE','DO_NOT_TRADE']")
s=s.replace("newListingsWatchBeforeTrade:true,watchThinNoNewRisk:true","newListingsWatchBeforeTrade:false,allActiveCryptoEligible:true,executionUnsafeNoNewRisk:true")
p.write_text(s)

# 6) Monitor 750ms stream + realtime WS mark-to-market overlay.
p=ROOT/'cloudflare-worker/bybit-android-monitor.js';s=p.read_text()
s=s.replace("const loadBridgeHealth=env=>cached('bridge',1000,()=>bridgeFetch(env,'/health'));","const loadBridgeHealth=env=>cached('bridge',350,()=>bridgeFetch(env,'/health'));")
marker="function positionsSummary(rows=[]){"
helper="""function overlayRealtimePositions(rows=[],bridge={}){const market=bridge.marketTelemetry||{};return rows.map(p=>{const t=market[p.symbol]||{},mark=num(t.lastPrice||t.mid),age=num(t.ageMs);if(!(mark>0)||age>5000)return p;const side=String(p.side||''),size=Math.abs(num(p.size)),entry=num(p.entryPrice),pnl=entry>0&&size>0?(side==='Buy'?(mark-entry)*size:(entry-mark)*size):num(p.unrealizedPnl),value=mark*size,margin=Math.max(0,num(p.positionMargin))||(num(p.leverage)>0?value/num(p.leverage):0),roe=margin>0?pnl/margin*100:p.roePct;return {...p,markPrice:mark,unrealizedPnl:Number(pnl.toFixed(8)),roePct:Number.isFinite(Number(roe))?Number(Number(roe).toFixed(3)):null,positionValue:Number(value.toFixed(8)),realtimeMark:true,marketDataAgeMs:age};});}\n"""
if helper not in s:
    if marker not in s:raise SystemExit('MISSING_PATTERN monitor positionsSummary marker')
    s=s.replace(marker,helper+marker,1)
old="const positions=(Array.isArray(controller?.activePositions)?controller.activePositions:[]).filter(x=>num(x.size)>0).map(positionRow),summary=positionsSummary(positions),pg=controller?.performanceGovernor?.summary||{},p24=governorWindow(pg.h24||{},24),p72=governorWindow(pg.h72||{},72),scanner=scannerSnapshot(universe),ws=bridge.wsTelemetry||{},snapshotBuildMs=Math.max(0,perfNow()-started)"
new="const reconciledPositions=(Array.isArray(controller?.activePositions)?controller.activePositions:[]).filter(x=>num(x.size)>0).map(positionRow),reconciledSummary=positionsSummary(reconciledPositions),positions=overlayRealtimePositions(reconciledPositions,bridge),summary=positionsSummary(positions),pg=controller?.performanceGovernor?.summary||{},p24=governorWindow(pg.h24||{},24),p72=governorWindow(pg.h72||{},72),scanner=scannerSnapshot(universe),ws=bridge.wsTelemetry||{},snapshotBuildMs=Math.max(0,perfNow()-started)"
if new not in s:
    if old not in s:raise SystemExit('MISSING_PATTERN monitor positions build')
    s=s.replace(old,new,1)
old="const account={equity:num(controller.equityUsd),balance:num(controller.walletBalanceUsd),availableBalance:num(controller.availableUsd),unrealizedPnl:summary.totalUnrealizedPnl,realizedPnl:p24.realizedPnl,realizedPnlWindowHours:24,realizedPnl72h:p72.realizedPnl,source:'BOT_CONTROLLER_RECONCILED_ACCOUNT_STATE'};"
new="const realtimePnlDelta=summary.totalUnrealizedPnl-reconciledSummary.totalUnrealizedPnl,realtimeEquity=num(controller.equityUsd)>0?num(controller.equityUsd)+realtimePnlDelta:num(controller.equityUsd),account={equity:Number(realtimeEquity.toFixed(8)),balance:num(controller.walletBalanceUsd),availableBalance:num(controller.availableUsd),unrealizedPnl:summary.totalUnrealizedPnl,realizedPnl:p24.realizedPnl,realizedPnlWindowHours:24,realizedPnl72h:p72.realizedPnl,source:'BOT_CONTROLLER_PLUS_VPS_WS_MARK_TO_MARKET'};"
if new not in s:
    if old not in s:raise SystemExit('MISSING_PATTERN monitor account')
    s=s.replace(old,new,1)
s=s.replace("defaultIntervalMs:1500,minIntervalMs:1000,maxIntervalMs:10000","defaultIntervalMs:750,minIntervalMs:500,maxIntervalMs:10000")
s=s.replace("intervalMs=1500,seq=0","intervalMs=750,seq=0")
s=s.replace("clamp(num(m.intervalMs)||1500,1000,10000)","clamp(num(m.intervalMs)||750,500,10000)")
p.write_text(s)

print('BYBIT_V470_ALL_CRYPTO_REALTIME_MONITOR_PATCHED')
