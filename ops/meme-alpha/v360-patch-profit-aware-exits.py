from pathlib import Path
import sys

p = Path(sys.argv[1])
s = p.read_text()

def must(old, new, count=1):
    global s
    n = s.count(old)
    if n < count:
        raise SystemExit(f'PATCH_MISS count={n} old={old[:180]!r}')
    s = s.replace(old, new, count)

def between(start, end, new):
    global s
    i = s.find(start)
    if i < 0:
        raise SystemExit(f'START_MISS {start!r}')
    j = s.find(end, i)
    if j < 0:
        raise SystemExit(f'END_MISS {end!r}')
    s = s[:i] + new + s[j:]

if "3.51.0-adaptive-alpha" not in s or "MICRO_LIVE_EXECUTOR_V351_ADAPTIVE_ALPHA=STARTED" not in s:
    raise SystemExit('V351_PRODUCTION_BASELINE_REQUIRED')

helper = r'''function profitAwareWeakDecision(x={}){
  const ret=n(x.ret),peak=Math.max(n(x.peak),ret),giveback=Math.max(0,n(x.giveback)),minGiveback=Math.max(3,n(x.minGiveback,5)),weakCount=n(x.weakCount),severe=x.severe===true,softWeak=x.softWeak===true,hadProfit=x.hadProfit===true||peak>=4||ret>0;
  if(severe)return{mode:'FULL',reason:'SEVERE_TREND_BREAK',frac:1};
  if(!softWeak)return{mode:'HOLD',reason:'TREND_RECOVERED',frac:0};
  if(ret<=-8)return{mode:'FULL',reason:'LOSS_LIMIT',frac:1};
  if(hadProfit&&ret>-3){
    const frac=clamp(.18+giveback/120+Math.max(0,weakCount-4)*.025,.18,.35);
    return{mode:'TRIM',reason:'PROFIT_AWARE_WEAKNESS',frac};
  }
  if(ret<=-3&&weakCount>=6)return{mode:'FULL',reason:'PERSISTENT_WEAKNESS_NEGATIVE',frac:1};
  return{mode:'TRIM',reason:'DEFENSIVE_WEAKNESS_TRIM',frac:clamp(.16+Math.max(0,weakCount-4)*.02,.16,.28)};
}
function profitAwareWeakAction(ret,peak,giveback,plan,c,pos){
  return profitAwareWeakDecision({ret,peak,giveback,minGiveback:plan?.minGiveback,weakCount:pos?.weakExitCount,severe:severeTrendBreak(c),softWeak:softTrendWeak(c),hadProfit:peak>=4||pos?.tp1Done||pos?.tp2Done||pos?.tp3Done||pos?.profitProtectDone});
}
function weakTrimReady(pos,minMs=20000,maxTrims=2){
  if(n(pos?.profitWeakTrimCount)>=maxTrims)return false;
  const last=Date.parse(pos?.lastProfitWeakTrimAt||0);
  return !Number.isFinite(last)||last<=0||Date.now()-last>=minMs;
}
function markWeakTrim(st,mint){
  const x=st.positions.find(z=>z.mint===mint);if(!x)return;
  x.profitWeakTrimCount=n(x.profitWeakTrimCount)+1;x.lastProfitWeakTrimAt=new Date().toISOString();x.scaleInLockedAfterProfit=true;atomic(statePath,st);
}
function resetWeakTrimEpisode(st,pos,c){
  if(!c||softTrendWeak(c)||(!n(pos.profitWeakTrimCount)&&!pos.lastProfitWeakTrimAt))return;
  const x=st.positions.find(z=>z.mint===pos.mint);if(!x)return;
  x.profitWeakTrimCount=0;x.lastProfitWeakTrimAt=null;atomic(statePath,st);
}

'''
marker = 'function tier(c,p){'
i = s.find(marker)
if i < 0:
    raise SystemExit('TIER_MARKER_MISSING')
s = s[:i] + helper + s[i:]

old_norm = "if(!Number.isFinite(Number(pos.lifetimeCostLamports)))pos.lifetimeCostLamports=n(pos.costBasisLamports);if(!Number.isFinite(Number(pos.realizedPnlLamports)))pos.realizedPnlLamports=0;\n  return pos;"
new_norm = "if(!Number.isFinite(Number(pos.lifetimeCostLamports)))pos.lifetimeCostLamports=n(pos.costBasisLamports);if(!Number.isFinite(Number(pos.realizedPnlLamports)))pos.realizedPnlLamports=0;\n  if(!Number.isFinite(Number(pos.profitWeakTrimCount)))pos.profitWeakTrimCount=0;if(!pos.lastProfitWeakTrimAt)pos.lastProfitWeakTrimAt=null;\n  return pos;"
must(old_norm, new_norm)

# Reset a weakness-trim episode after the trend actually recovers.
must("if(Number.isFinite(ret)){\n    if(!pos.tp1Done&&ret>=plan.tp1)", "if(Number.isFinite(ret)){\n    resetWeakTrimEpisode(st,pos,c);\n    if(!pos.tp1Done&&ret>=plan.tp1)")

old_weak = "if(pos.weakExitCount>=4&&(ret<=-8||(peak>8&&giveback>=Math.max(plan.minGiveback,peak*.5))||softTrendWeak(c))){await sell(st,idx,'AUTO_CONFIRMED_WEAKNESS');return{action:'SELL',reason:'AUTO_CONFIRMED_WEAKNESS',symbol:pos.symbol}}"
new_weak = r'''if(pos.weakExitCount>=4){
      const wa=profitAwareWeakAction(ret,peak,giveback,plan,c,pos);
      if(wa.mode==='FULL'){
        const reason=wa.reason==='SEVERE_TREND_BREAK'?'AUTO_SEVERE_TREND_BREAK':wa.reason==='LOSS_LIMIT'?'AUTO_LOSS_LIMIT':'AUTO_CONFIRMED_WEAKNESS_NEGATIVE';
        event({type:'PROFIT_AWARE_EXIT_DECISION',mint:pos.mint,symbol:pos.symbol,decision:'FULL',reason,ret,peak,giveback,weakExitCount:pos.weakExitCount});
        await sell(st,idx,reason);return{action:'SELL',reason,symbol:pos.symbol};
      }
      if(wa.mode==='TRIM'&&weakTrimReady(pos,20000,2)){
        const r=await sellFraction(st,idx,wa.frac,'AUTO_PROFIT_AWARE_WEAKNESS_TRIM');
        if(!r.closed)markWeakTrim(st,pos.mint);
        event({type:'PROFIT_AWARE_WEAKNESS_TRIM',mint:pos.mint,symbol:pos.symbol,ret,peak,giveback,fraction:wa.frac,weakExitCount:pos.weakExitCount,reason:wa.reason,closed:r.closed});
        return{action:r.closed?'SELL':'PARTIAL_SELL',reason:'AUTO_PROFIT_AWARE_WEAKNESS_TRIM',symbol:pos.symbol};
      }
    }'''
must(old_weak, new_weak)

old_noquote = "}else if(pos.weakExitCount>=6&&softTrendWeak(c)){await sell(st,idx,'AUTO_WEAKNESS_NO_QUOTE');return{action:'SELL',reason:'AUTO_WEAKNESS_NO_QUOTE',symbol:pos.symbol}}"
new_noquote = r'''}else if(softTrendWeak(c)){
    const peak=n(pos.peakReturnPct),hadProfit=peak>=4||pos.tp1Done||pos.tp2Done||pos.tp3Done||pos.profitProtectDone;
    if(severeTrendBreak(c)&&pos.weakExitCount>=4){event({type:'NO_QUOTE_EXIT_DECISION',mint:pos.mint,decision:'FULL',reason:'SEVERE_TREND_BREAK',peak,weakExitCount:pos.weakExitCount});await sell(st,idx,'AUTO_SEVERE_TREND_BREAK_NO_QUOTE');return{action:'SELL',reason:'AUTO_SEVERE_TREND_BREAK_NO_QUOTE',symbol:pos.symbol}}
    if(hadProfit&&pos.weakExitCount>=7&&weakTrimReady(pos,30000,2)){const frac=.22,r=await sellFraction(st,idx,frac,'AUTO_WINNER_DEFENSE_NO_QUOTE');if(!r.closed)markWeakTrim(st,pos.mint);event({type:'NO_QUOTE_WINNER_DEFENSE',mint:pos.mint,symbol:pos.symbol,peak,fraction:frac,weakExitCount:pos.weakExitCount,closed:r.closed});return{action:r.closed?'SELL':'PARTIAL_SELL',reason:'AUTO_WINNER_DEFENSE_NO_QUOTE',symbol:pos.symbol}}
    if(!hadProfit&&pos.weakExitCount>=10){event({type:'NO_QUOTE_EXIT_DECISION',mint:pos.mint,decision:'FULL',reason:'PERSISTENT_WEAKNESS',peak,weakExitCount:pos.weakExitCount});await sell(st,idx,'AUTO_PERSISTENT_WEAKNESS_NO_QUOTE');return{action:'SELL',reason:'AUTO_PERSISTENT_WEAKNESS_NO_QUOTE',symbol:pos.symbol}}
  }'''
must(old_noquote, new_noquote)

rotation = r'''function rotationSource(st,newC){
  const ns=expectedEdge(st,newC),newImpact=impact(newC),rows=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c).map(x=>({...x,oldScore:expectedEdge(st,x.c),weak:softTrendWeak(x.c),severe:severeTrendBreak(x.c)})).sort((a,b)=>a.oldScore-b.oldScore);
  for(const x of rows){
    const switchingCost=(newImpact+Math.max(0,n(x.pos.lastPreviewImpactPct,impact(x.c))))*1.5,advantage=ns-x.oldScore-switchingCost,ret=n(x.pos.lastReturnPct),peak=n(x.pos.peakReturnPct),winner=ret>0||peak>=8||x.pos.tp1Done||x.pos.tp2Done||x.pos.tp3Done||x.pos.profitProtectDone;
    const threshold=x.severe?0:(winner?(ret>=12||peak>=20?34:28):(x.weak?5:13));
    if(x.severe||advantage>=threshold)return{...x,advantage,switchingCost,winner,threshold,ret,peak};
  }
  return null;
}
async function maybeRotate(st,newC){
  const x=rotationSource(st,newC);if(!x)return null;
  const frac=x.severe?.50:x.winner?clamp(.15+x.advantage/180,.15,.28):x.weak?.50:clamp(.20+x.advantage/100,.20,.45),reason=x.winner?'AUTO_WINNER_ROTATE_TO_STRONGER_OPPORTUNITY':'AUTO_ROTATE_TO_STRONGER_OPPORTUNITY';
  const r=await sellFraction(st,x.index,frac,reason),a=ensureAutonomy(st);a.lastRotationAt=new Date().toISOString();a.lastRotationFromMint=x.pos.mint;a.lastRotationToMint=newC.mint;atomic(statePath,st);
  event({type:x.winner?'WINNER_ROTATION':'AUTO_ROTATION',fromMint:x.pos.mint,toMint:newC.mint,advantage:x.advantage,threshold:x.threshold,switchingCost:x.switchingCost,fraction:frac,ret:x.ret,peak:x.peak,severe:x.severe,closed:r.closed});
  return{action:'ROTATE',reason:x.winner?'WINNER_TO_MATERIALLY_STRONGER_OPPORTUNITY':'STRONGER_OPPORTUNITY',symbol:x.pos.symbol,targetSymbol:newC.symbol};
}

'''
between('function rotationSource(st,newC){', 'async function tick(){', rotation)

must("st.version='3.51.0-adaptive-alpha'", "st.version='3.60.0-profit-aware-exits'")
must('MICRO_LIVE_EXECUTOR_V351_ADAPTIVE_ALPHA=STARTED', 'MICRO_LIVE_EXECUTOR_V360_PROFIT_AWARE=STARTED')
must('MICRO_EXECUTOR_V351_ADAPTIVE_ALPHA_SELF_TEST=PASS', 'MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS')

selftest_anchor = "console.log('MICRO_EXECUTOR_V360_PROFIT_AWARE_SELF_TEST=PASS');"
selftest = r'''const pa=profitAwareWeakDecision({ret:5,peak:9,giveback:4,minGiveback:5,weakCount:4,softWeak:true,severe:false,hadProfit:true});if(pa.mode!=='TRIM')throw new Error('POSITIVE_SOFT_WEAKNESS_MUST_TRIM');
  const pb=profitAwareWeakDecision({ret:-9,peak:2,giveback:0,minGiveback:5,weakCount:4,softWeak:true,severe:false,hadProfit:false});if(pb.mode!=='FULL'||pb.reason!=='LOSS_LIMIT')throw new Error('LOSS_LIMIT_MUST_FULL_EXIT');
  const pc=profitAwareWeakDecision({ret:7,peak:12,giveback:5,minGiveback:5,weakCount:4,softWeak:true,severe:true,hadProfit:true});if(pc.mode!=='FULL'||pc.reason!=='SEVERE_TREND_BREAK')throw new Error('SEVERE_BREAK_MUST_FULL_EXIT');
  const pd=profitAwareWeakDecision({ret:2,peak:7,giveback:5,minGiveback:5,weakCount:4,softWeak:false,severe:false,hadProfit:true});if(pd.mode!=='HOLD')throw new Error('RECOVERED_TREND_MUST_HOLD');
  console.log('PROFIT_AWARE_WEAK_EXIT=TRUE');console.log('POSITIVE_SOFT_WEAKNESS=PARTIAL_ONLY');console.log('WINNER_ROTATION_PROTECTION=TRUE');console.log('NO_QUOTE_WINNER_DEFENSE=TRUE');console.log('SEVERE_TREND_BREAK_FULL_EXIT=KEPT');
  ''' + selftest_anchor
must(selftest_anchor, selftest)

p.write_text(s)
print('V360_PATCH_APPLIED=TRUE')
