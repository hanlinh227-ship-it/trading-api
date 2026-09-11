from pathlib import Path

p=Path('signalhub-worker/gateway-v3.js')
s=p.read_text()

def block(text,start,end,replacement,name):
    i=text.find(start); assert i>=0, f'{name}: start marker missing'
    j=text.find(end,i); assert j>i, f'{name}: end marker missing'
    return text[:i]+replacement+text[j:]

converter=r'''function marketOnlySevenCandidate(raw){
  const s={...(raw||{})},style=String(s.style||'SCALP').toUpperCase(),side=String(s.side||'').toUpperCase(),dir=['LONG','BUY'].includes(side)?1:['SHORT','SELL'].includes(side)?-1:0,read=s.marketReadV322||{},tech=s.technicalAtIssue||{},ev=s.qualityEvidence||{},src=Number(s.sourcePrice||s.lastPrice||s.entry||0),atr=Math.abs(Number(tech.atr||0));
  if(!dir||!(src>0&&atr>0))return null;
  const cross=s.crossProviderConsensus||{},checked=Number(cross.checked||0),confirmed=Number(cross.confirmed||0),opposed=Number(cross.opposed||0),crossQuality=checked===0?'UNAVAILABLE':confirmed>opposed?'CONFIRMED':opposed>confirmed?'OPPOSED':'MIXED';
  // One transient secondary disagreement is not enough to erase an otherwise clean setup.
  // Majority opposition, or the only checked venue opposing, remains a hard rejection.
  if(opposed>=2||(checked===1&&opposed===1))return null;
  const rule=stableUniverseRule(style),spread=Number(tech.spreadBps??999),turnover=Number(tech.turnover24h||0),move=Math.abs(Number(tech.change24hPct||0)),rsi=Number(tech.rsi||50),ext=Math.abs(Number(tech.extensionAtr||read.extensionAtr||0));
  const spreadCap=rule.maxSpread*(style==='SWING'?.98:.95),turnoverFloor=rule.minTurnover;
  if(!(spread>=0&&spread<=spreadCap&&turnover>=turnoverFloor&&move<=rule.maxMove))return null;
  if((dir>0&&rsi>72)||(dir<0&&rsi<28))return null;
  const trends=Array.isArray(tech.tfTrend)?tech.tfTrend.map(x=>Number(x)>0?1:Number(x)<0?-1:0):[],derivedAligned=style==='SWING'?trends.length>=3&&trends[1]===dir&&trends[2]===dir:trends.length>=3&&trends[1]!==-dir&&trends[2]!==-dir&&(trends[1]===dir||trends[2]===dir),scalpStrong=style==='SCALP'&&trends.length>=3&&trends[1]===dir&&trends[2]===dir,contextAligned=read.contextAligned===true||ev.v322ContextAligned===true||derivedAligned,contextStrong=read.contextStrong===true||derivedAligned||scalpStrong,execEvent=read.executionEvent===true||Boolean(ev.liquidityEvent)||Boolean(ev.displacementConfirmed),momentum=read.executionMomentum===true,evidenceCount=[contextStrong,execEvent,momentum].filter(Boolean).length;
  if(style==='SWING'&&!contextStrong)return null;
  if(style==='SCALP'&&!contextAligned)return null;
  const maxExt=style==='SWING'?.30:.38;if(ext>maxExt)return null;
  const strict=read.marketEntryReady===true&&contextStrong&&execEvent&&momentum&&crossQuality==='CONFIRMED';
  const tightLocation=ext<=(style==='SWING'?.22:.28),excellentLiquidity=spread<=spreadCap*.82&&turnover>=turnoverFloor*1.10;
  // Ranked-safe tier is still a real hard floor: context must align, no majority secondary
  // opposition, at least one execution/structure confirmation, and either two pieces of
  // evidence or especially clean location/liquidity. This is deliberately tighter than
  // V3.23.0 ALIGNED_SAFE without starving the 5+2 book.
  const safeEvidence=(execEvent||momentum||contextStrong)&&(evidenceCount>=2||(tightLocation&&excellentLiquidity));
  const precisionSafe=contextAligned&&crossQuality!=='OPPOSED'&&safeEvidence;
  if(!strict&&!precisionSafe)return null;
  const spreadPx=Math.max(0,src*spread/10000),minRisk=atr*(style==='SWING'?1.02:.70),maxRisk=atr*(style==='SWING'?3.05:2.20),buffer=Math.max(atr*(style==='SWING'?.29:.21),spreadPx*3.4);
  const oldSl=Number(s.sl||0),inv=Number(s.invalidationLevel||0),recentLow=Number(tech.recentLow||0),recentHigh=Number(tech.recentHigh||0),ema50=Number(tech.ema50||0),anchors=dir>0?[inv,recentLow,oldSl,ema50].filter(x=>Number.isFinite(x)&&x>0&&x<src):[inv,recentHigh,oldSl,ema50].filter(x=>Number.isFinite(x)&&x>src);
  let anchor=anchors.length?(dir>0?Math.max(...anchors):Math.min(...anchors)):src-dir*minRisk,sl=anchor-dir*buffer,risk=Math.abs(src-sl);
  if(risk<minRisk){risk=minRisk;sl=src-dir*risk;}if(!(risk>0)||risk>maxRisk)return null;
  const minRR=style==='SWING'?2.90:2.25,t1Base=src+dir*risk*1.00,t2Base=src+dir*risk*1.65,t3Base=src+dir*risk*minRR,oldT1=Number(s.tp1||0),oldT2=Number(s.tp2||0),oldT3=Number(s.tp3||s.tp||0);
  const useTarget=(old,base)=>dir>0?(old>src?Math.max(old,base):base):(old>0&&old<src?Math.min(old,base):base),tp1=useTarget(oldT1,t1Base),tp2=useTarget(oldT2,dir>0?Math.max(t2Base,tp1+risk*.25):Math.min(t2Base,tp1-risk*.25)),tp3=useTarget(oldT3,dir>0?Math.max(t3Base,tp2+risk*.35):Math.min(t3Base,tp2-risk*.35)),rr=Math.abs(tp3-src)/risk;
  if(rr<minRR)return null;
  return stampMarketJudgment({...s,orderType:'MARKET',status:'OPEN',entryState:'LIVE',lifecycle:'ACTIVE',entry:Number(src.toPrecision(10)),actualEntry:Number(src.toPrecision(10)),sl:Number(sl.toPrecision(10)),tp1:Number(tp1.toPrecision(10)),tp2:Number(tp2.toPrecision(10)),tp3:Number(tp3.toPrecision(10)),tp:Number(tp3.toPrecision(10)),invalidationLevel:Number(anchor.toPrecision(10)),targetRR:Number(rr.toFixed(3)),coverageFallback:false,referenceFallback:false,marketOnly:true,marketOnlyQuality:strict?'PRECISION_CONFIRMED':'PRECISION_RANKED_SAFE',marketOnlyFacts:{strict,contextAligned,contextStrong,executionEvent:execEvent,executionMomentum:momentum,evidenceCount,crossProvider:crossQuality,crossChecked:checked,crossConfirmed:confirmed,crossOpposed:opposed,extensionAtr:Number(ext.toFixed(3)),spreadBps:Number(spread.toFixed(3)),spreadCapBps:Number(spreadCap.toFixed(3)),turnover24h:turnover,targetRR:Number(rr.toFixed(3)),riskAtr:Number((risk/atr).toFixed(3)),tightLocation,excellentLiquidity},entryAssessment:{verdict:'PASS',method:'V3231_BALANCED_PRECISION_RANKED_HARD_FLOOR_NO_WIN_PROBABILITY',failed:[]}},'CRYPTO',style);
}
function compareMarketOnlyQuality(a,b){
  const aq=a.marketOnlyQuality==='PRECISION_CONFIRMED'?0:1,bq=b.marketOnlyQuality==='PRECISION_CONFIRMED'?0:1;if(aq!==bq)return aq-bq;const af=a.marketOnlyFacts||{},bf=b.marketOnlyFacts||{};
  if(Number(af.evidenceCount||0)!==Number(bf.evidenceCount||0))return Number(bf.evidenceCount||0)-Number(af.evidenceCount||0);
  const cr=x=>x==='CONFIRMED'?0:x==='MIXED'?1:x==='UNAVAILABLE'?2:3,ac=cr(af.crossProvider),bc=cr(bf.crossProvider);if(ac!==bc)return ac-bc;
  for(const k of ['contextStrong','executionEvent','executionMomentum','tightLocation','excellentLiquidity']){const av=af[k]?0:1,bv=bf[k]?0:1;if(av!==bv)return av-bv;}
  if(Number(af.extensionAtr)!==Number(bf.extensionAtr))return Number(af.extensionAtr)-Number(bf.extensionAtr);
  if(Number(af.spreadBps)!==Number(bf.spreadBps))return Number(af.spreadBps)-Number(bf.spreadBps);
  if(Number(af.riskAtr)!==Number(bf.riskAtr))return Number(af.riskAtr)-Number(bf.riskAtr);
  if(Number(af.turnover24h)!==Number(bf.turnover24h))return Number(bf.turnover24h)-Number(af.turnover24h);
  return Number(bf.targetRR||0)-Number(af.targetRR||0);
}

'''
s=block(s,'function marketOnlySevenCandidate(raw){','async function maybeCreateV31(env,market,style,setups){',converter,'V3.23.1 balanced admission')

# Make scan diagnostics explicit for production audit without changing user-facing signals.
s=s.replace("strictConfirmed:marketCandidates.filter(x=>x.marketOnlyQuality==='STRICT_CONFIRMED').length,safeFill:marketCandidates.filter(x=>x.marketOnlyQuality==='ALIGNED_SAFE').length,","strictConfirmed:marketCandidates.filter(x=>x.marketOnlyQuality==='PRECISION_CONFIRMED').length,safeFill:marketCandidates.filter(x=>x.marketOnlyQuality==='PRECISION_RANKED_SAFE').length,")
s=s.replace("strictConfirmed:marketCandidates.filter(x=>x.marketOnlyQuality==='PRECISION_CONFIRMED').length,safeFill:marketCandidates.filter(x=>x.marketOnlyQuality==='PRECISION_ALIGNED').length,","strictConfirmed:marketCandidates.filter(x=>x.marketOnlyQuality==='PRECISION_CONFIRMED').length,safeFill:marketCandidates.filter(x=>x.marketOnlyQuality==='PRECISION_RANKED_SAFE').length,")

assert "marketOnlyQuality:strict?'PRECISION_CONFIRMED':'PRECISION_RANKED_SAFE'" in s
assert 'V3231_BALANCED_PRECISION_RANKED_HARD_FLOOR_NO_WIN_PROBABILITY' in s
assert "const maxExt=style==='SWING'?.30:.38" in s
assert "if(opposed>=2||(checked===1&&opposed===1))return null;" in s
p.write_text(s)
print('V3.23.1 balanced precision admission patched')
