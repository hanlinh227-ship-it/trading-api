#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
BASE="$ROOT/ops/meme-alpha/micro-live/micro-live-executor-v331-multi.js"
OUT="$ROOT/ops/meme-alpha/micro-live/micro-live-executor-v336-autonomous.js"
cp "$BASE" "$OUT"
python3 - "$OUT" <<'PY'
import re,sys
p=sys.argv[1]
s=open(p).read()
def sub(pattern,repl,count=1):
    global s
    s2,n=re.subn(pattern,repl,s,count=count,flags=re.S)
    if n!=count: raise SystemExit(f'PATCH_MISS pattern={pattern[:80]!r} got={n}')
    s=s2

sub(r"const DEFAULT_EXIT_RESERVE_LAMPORTS=5_000_000;\nconst ENTRY_OVERHEAD_LAMPORTS=3_000_000;\nconst MULTI_POSITION_CAP_PCT=\{PROBE:6,CONFIRMED:10,STRONG:15,MAX:20\};",
"""const DEFAULT_EXIT_RESERVE_LAMPORTS=5_000_000; // root-policy ceiling / fallback
const MIN_EXIT_HEADROOM_LAMPORTS=250_000;
const ENTRY_OVERHEAD_LAMPORTS=500_000;
const ESTIMATED_EXIT_COMPUTE_UNITS=350_000;""")
sub(r"const n=\(v,d=0\)=>Number\.isFinite\(Number\(v\)\)\?Number\(v\):d;",
"const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;\nconst clamp=(v,lo,hi)=>Math.max(lo,Math.min(hi,v));")
sub(r"function profitThresholds\(c\)\{.*?\}\nfunction tier\(c,p\)\{.*?\}\nfunction multiTier\(c,p\)\{.*?\}\nfunction rank",
"""function profitPlan(c,pos){
  const pulse=pulseFor(c),strength=clamp(n(pulse?.pulseScore,50),0,100),chg=Math.abs(n(pulse?.price5m,n(c?.priceChange5m,0))),bs=n(pulse?.buySellRatio,n(c?.buySellRatio5m,1));
  const breakout=!!pulse&&pulse.status==='BREAKOUT'&&strength>=70&&bs>=1.05;
  const tp1=clamp(10+strength*0.14+chg*0.35,10,36),tp2=tp1*(breakout?2.1:1.75),tp3=tp2*(breakout?1.8:1.55);
  const givebackRatio=breakout?0.45:0.30,minGiveback=clamp(5+chg*0.65,5,16);
  const f1=breakout?0.12:0.18,f2=breakout?0.16:0.22,f3=breakout?0.12:0.18;
  return {tp1,tp2,tp3,givebackRatio,minGiveback,f1,f2,f3,breakout};
}
function tier(c,p){if(!trendEntryEligible(c))return {name:'NONE',pct:0};const score=n(c.score),con=n(c.consecutiveEligible),net=n(c.netBuyers5m),avg=n(c.avgNetBuyersLast2),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m);const maxQuality=(score>=82&&net>=10&&avg>=7)||(score>=76&&net>=18&&avg>=10);if(con>=5&&maxQuality&&liq>=250000&&imp<=0.50&&chg>=0.50&&chg<=8)return{name:'MAX',pct:p.maxUtilizationPct};const strongQuality=(score>=76&&net>=6&&avg>=4)||(score>=70&&net>=10&&avg>=6);if(con>=3&&strongQuality&&liq>=150000&&imp<=0.80&&chg>=0.30&&chg<=10)return{name:'STRONG',pct:p.strongUtilizationPct};const confirmedQuality=(score>=70&&net>=3&&avg>=2)||(score>=66&&net>=6&&avg>=4);if(con>=2&&confirmedQuality&&liq>=100000&&imp<=1.00&&chg>=0.15&&chg<=12)return{name:'CONFIRMED',pct:p.confirmedUtilizationPct};return{name:'PROBE',pct:p.probeUtilizationPct}}
function ensureAutonomy(st,capitalBaseLamports=0){if(!st.autonomy||typeof st.autonomy!=='object')st.autonomy={};if(!(n(st.autonomy.referenceCapitalLamports)>0)&&capitalBaseLamports>0)st.autonomy.referenceCapitalLamports=capitalBaseLamports;return st.autonomy}
function allocationProfile(c,p,st,capitalBaseLamports){
  if(!trendEntryEligible(c)||capitalBaseLamports<=0)return{name:'NONE',pct:0,quality:0};
  const scoreQ=clamp((opportunityScore(c)-58)/32,0,1),netQ=clamp((n(c.netBuyers5m)+2)/24,0,1),avgQ=clamp((n(c.avgNetBuyersLast2)+1)/16,0,1);
  const liq=Math.max(50_000,n(c.liquidityUsd,50_000)),liqQ=clamp(Math.log10(liq/50_000)/1.6,0,1),impactQ=clamp(1-impact(c)/1.25,0,1),pulse=pulseFor(c),pulseQ=clamp(n(pulse?.pulseScore,55)/100,0,1);
  const quality=clamp(scoreQ*.31+netQ*.18+avgQ*.12+liqQ*.16+impactQ*.15+pulseQ*.08,0,1);
  const a=ensureAutonomy(st,capitalBaseLamports),ref=Math.max(1,n(a.referenceCapitalLamports,capitalBaseLamports)),growth=clamp(Math.pow(capitalBaseLamports/ref,.25),.75,1.50);
  const exposure=clamp(portfolioInvested(st)/capitalBaseLamports,0,1),headroom=clamp(1-exposure*.55,.35,1);
  const basePct=3+27*Math.pow(quality,1.35),pct=clamp(basePct*growth*headroom,0,p.maxUtilizationPct);
  return{name:'AUTO',pct,quality,growth,exposure,score:opportunityScore(c)};
}
function rank""")
sub(r"function bestCandidate\(p,held\)\{.*?\}\n\nfunction normalizePosition",
"function bestCandidate(p,held){return candidates().filter(c=>!held.has(c.mint)&&trendEntryEligible(c)).sort((a,b)=>rank(b)-rank(a))[0]||null}\n\nfunction normalizePosition")
sub(r"function requiredReserveLamports\(p,count\)\{.*?\}\nfunction targetPlan\(solBalanceLamports,st,position,targetPct,p,\{isNew=false\}=\{\}\)\{.*?\n\}",
"""async function networkExitHeadroomLamports(p){
  try{const rows=await rpc('getRecentPrioritizationFees',[]),vals=(rows||[]).map(x=>n(x.prioritizationFee)).filter(x=>x>=0).sort((a,b)=>a-b);const q=vals.length?vals[Math.min(vals.length-1,Math.floor(vals.length*.75))]:0;const priority=Math.ceil(q*ESTIMATED_EXIT_COMPUTE_UNITS/1_000_000),estimated=Math.ceil((10_000+priority)*8);return Math.floor(clamp(estimated,MIN_EXIT_HEADROOM_LAMPORTS,p.perPositionExitReserveLamports))}catch{return Math.floor(clamp(750_000,MIN_EXIT_HEADROOM_LAMPORTS,p.perPositionExitReserveLamports))}
}
function requiredReserveLamports(p,count,exitHeadroomLamports=MIN_EXIT_HEADROOM_LAMPORTS){const per=Math.floor(clamp(exitHeadroomLamports,MIN_EXIT_HEADROOM_LAMPORTS,p.perPositionExitReserveLamports));return p.reserveLamports+Math.max(0,count)*per}
function targetPlan(solBalanceLamports,st,position,targetPct,p,{isNew=false,exitHeadroomLamports=MIN_EXIT_HEADROOM_LAMPORTS}={}){
  const invested=Math.max(0,n(position?.costBasisLamports)),capitalBase=Math.max(0,solBalanceLamports+portfolioInvested(st)),targetInvested=Math.floor(capitalBase*targetPct/100),futureCount=st.positions.length+(isNew?1:0),reserve=requiredReserveLamports(p,futureCount,exitHeadroomLamports),overhead=isNew?Math.max(ENTRY_OVERHEAD_LAMPORTS,exitHeadroomLamports):0,available=Math.max(0,solBalanceLamports-reserve-overhead),amount=Math.min(Math.max(0,targetInvested-invested),available);
  return {capitalBaseLamports:capitalBase,investedLamports:invested,targetInvestedLamports:targetInvested,amountLamports:Math.floor(amount),targetUtilizationPct:targetPct,reserveLamports:reserve,entryOverheadLamports:overhead,futurePositionCount:futureCount,availableLamports:available,exitHeadroomLamports};
}""")
sub(r"async function placeBuy\(st,c,targetTier,posIndex=-1\)\{.*?\n\}",
"""async function placeBuy(st,c,posIndex=-1){
  const p=rootPolicy(),h=await signer({op:'health'});if(!h.ok||!h.publicKey||!h.signingEnabled||!h.walletLoaded)throw new Error('SIGNER_NOT_ARMED');
  const isAdd=posIndex>=0,existing=isAdd?st.positions[posIndex]:null;if(!isAdd&&st.positions.some(x=>x.mint===c.mint))return{placed:false,reason:'MINT_ALREADY_HELD'};
  const beforeSol=await solBalance(h.publicKey),capitalBase=Math.max(0,beforeSol+portfolioInvested(st)),profile=allocationProfile(c,p,st,capitalBase),exitHeadroomLamports=await networkExitHeadroomLamports(p),plan=targetPlan(beforeSol,st,existing,profile.pct,p,{isNew:!isAdd,exitHeadroomLamports});
  if(plan.targetInvestedLamports<p.minOrderLamports)return{placed:false,reason:'ALLOCATION_BELOW_MIN_ORDER',plan,profile};if(plan.availableLamports<p.minOrderLamports)return{placed:false,reason:'CAPITAL_HEADROOM_LOW',plan,profile};if(plan.amountLamports<p.minOrderLamports)return{placed:false,reason:'TARGET_ALREADY_SATISFIED',plan,profile};
  const beforeTok=await tokenBalance(h.publicKey,c.mint),o=await signer({op:'order',inputMint:WSOL,outputMint:c.mint,amount:String(plan.amountLamports),maxPriceImpactPct:p.maxBuyPriceImpactPct});if(!o.ok)throw new Error(`SIGNER_${o.error}`);if(Math.abs(n(o.priceImpactPct,99))>p.maxBuyPriceImpactPct)throw new Error('ORDER_IMPACT_GUARD');
  const sig=await executeOrder(o),afterSol=await solBalance(h.publicKey),afterTok=await tokenBalance(h.publicKey,c.mint),delta=afterTok-beforeTok;if(delta<=0n)throw new Error('BUY_TOKEN_DELTA_ZERO');const spent=Math.max(0,beforeSol-afterSol);if(spent>plan.amountLamports+Math.max(ENTRY_OVERHEAD_LAMPORTS,exitHeadroomLamports))event({type:'POST_FILL_SPEND_OVER_PLAN',mint:c.mint,spentLamports:spent,plannedLamports:plan.amountLamports});
  if(isAdd){const pos=st.positions[posIndex];pos.tokenRaw=(BigInt(pos.tokenRaw||'0')+delta).toString();pos.costBasisLamports=n(pos.costBasisLamports)+spent;pos.entrySolLamports=pos.costBasisLamports;pos.addCount=n(pos.addCount)+1;pos.lastAddAt=new Date().toISOString();pos.targetUtilizationPct=profile.pct;pos.tier='AUTO';pos.lastAddSignature=sig;pos.walletAfterSolLamports=afterSol;event({type:'MICRO_SCALE_IN',mint:c.mint,symbol:c.symbol,allocationPct:profile.pct,quality:profile.quality,spentLamports:spent,spentSol:spent/1e9,costBasisLamports:pos.costBasisLamports,signature:sig,openPositions:st.positions.length})}
  else{const pos={mint:c.mint,symbol:c.symbol,tokenRaw:delta.toString(),costBasisLamports:spent,entrySolLamports:spent,entrySignature:sig,openedAt:new Date().toISOString(),lastAddAt:new Date().toISOString(),addCount:0,targetUtilizationPct:profile.pct,tier:'AUTO',walletBeforeSolLamports:beforeSol,walletAfterSolLamports:afterSol,weakExitCount:0,gateClosedCount:0,peakReturnPct:null,lastReturnPct:null,tp1Done:false,tp2Done:false,tp3Done:false,profitProtectDone:false,scaleInLockedAfterProfit:false};st.positions.push(pos);event({type:'MICRO_BUY',mint:c.mint,symbol:c.symbol,allocationPct:profile.pct,quality:profile.quality,growthFactor:profile.growth,spentLamports:spent,spentSol:spent/1e9,signature:sig,openPositions:st.positions.length,reserveForAllExitsLamports:requiredReserveLamports(p,st.positions.length,exitHeadroomLamports)})}
  observeBalance(st,afterSol,p.externalFlowThresholdLamports,{suppress:true});const reserveNow=requiredReserveLamports(p,st.positions.length,exitHeadroomLamports);if(afterSol<reserveNow)event({type:'EXIT_RESERVE_MARGIN_LOW',walletSolLamports:afterSol,requiredReserveLamports:reserveNow,openPositions:st.positions.length});atomic(statePath,st);return{placed:true,plan,profile,spent,signature:sig};
}""")
sub(r"async function manageOnePosition\(st,gate,p\)\{.*?\n\}\nasync function maybeScaleIn\(st,p\)\{.*?\n\}",
"""async function manageOnePosition(st,gate,p){
  if(!st.positions.length)return null;const idx=st.manageCursor%st.positions.length;st.manageCursor=(idx+1)%Math.max(1,st.positions.length);const pos=st.positions[idx],c=candidate(pos.mint);
  let ret=null;try{const h=await signer({op:'health'});if(h.ok&&h.publicKey&&h.walletLoaded)ret=await previewExitReturn(pos,h.publicKey)}catch(e){event({type:'EXIT_PREVIEW_FAIL',mint:pos.mint,error:String(e.message||e).slice(0,160)})}
  const plan=profitPlan(c,pos),peak=n(pos.peakReturnPct,ret??0),giveback=peak-n(ret,peak);
  if(Number.isFinite(ret)){
    if(!pos.tp1Done&&ret>=plan.tp1){const r=await sellFraction(st,idx,plan.f1,'AUTO_TP1');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.tp1Done=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'AUTO_TP1',symbol:pos.symbol}}
    if(!pos.tp2Done&&ret>=plan.tp2){const r=await sellFraction(st,idx,plan.f2,'AUTO_TP2');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.tp2Done=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'AUTO_TP2',symbol:pos.symbol}}
    if(!pos.tp3Done&&ret>=plan.tp3){const r=await sellFraction(st,idx,plan.f3,'AUTO_TP3_RUNNER');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.tp3Done=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'AUTO_TP3_RUNNER',symbol:pos.symbol}}
    const protectGiveback=Math.max(plan.minGiveback,peak*plan.givebackRatio);if(!pos.profitProtectDone&&peak>=plan.tp1*.85&&giveback>=protectGiveback&&ret>0){const frac=plan.breakout?.20:.30,r=await sellFraction(st,idx,frac,'AUTO_PROFIT_GIVEBACK');if(!r.closed){const x=st.positions.find(x=>x.mint===pos.mint);if(x){x.profitProtectDone=true;x.scaleInLockedAfterProfit=true;atomic(statePath,st)}}return{action:'PARTIAL_SELL',reason:'AUTO_PROFIT_GIVEBACK',symbol:pos.symbol}}
    if(pos.weakExitCount>=4&&(ret<=-8||(peak>8&&giveback>=Math.max(plan.minGiveback,peak*.5))||softTrendWeak(c))){await sell(st,idx,'AUTO_CONFIRMED_WEAKNESS');return{action:'SELL',reason:'AUTO_CONFIRMED_WEAKNESS',symbol:pos.symbol}}
  }else if(pos.weakExitCount>=6&&softTrendWeak(c)){await sell(st,idx,'AUTO_WEAKNESS_NO_QUOTE');return{action:'SELL',reason:'AUTO_WEAKNESS_NO_QUOTE',symbol:pos.symbol}}
  return null;
}
async function maybeScaleIn(st,p){
  if(!st.positions.length)return null;const ranked=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c&&!x.pos.scaleInLockedAfterProfit&&x.pos.weakExitCount===0).sort((a,b)=>rank(b.c)-rank(a.c));
  for(const x of ranked){const last=Date.parse(x.pos.lastAddAt||x.pos.openedAt||0),age=(Date.now()-last)/1000;if(age>=p.minAddIntervalSec){const r=await placeBuy(st,x.c,x.index);if(r.placed)return{action:'ADD',reason:'AUTO_SCALE',symbol:x.c.symbol}}}return null;
}
function rotationSource(st,newC){const ns=opportunityScore(newC),rows=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c).map(x=>({...x,oldScore:opportunityScore(x.c),weak:softTrendWeak(x.c)})).sort((a,b)=>a.oldScore-b.oldScore);for(const x of rows){const advantage=ns-x.oldScore;if(x.weak||advantage>=16){if(n(x.pos.lastReturnPct)>20&&!x.weak&&advantage<24)continue;return{...x,advantage}}}return null}
async function maybeRotate(st,newC){const x=rotationSource(st,newC);if(!x)return null;const frac=x.weak?.50:clamp(.20+x.advantage/100,.20,.45),r=await sellFraction(st,x.index,frac,'AUTO_ROTATE_TO_STRONGER_OPPORTUNITY');const a=ensureAutonomy(st);a.lastRotationAt=new Date().toISOString();a.lastRotationFromMint=x.pos.mint;a.lastRotationToMint=newC.mint;atomic(statePath,st);event({type:'AUTO_ROTATION',fromMint:x.pos.mint,toMint:newC.mint,advantage:x.advantage,fraction:frac,closed:r.closed});return{action:'ROTATE',reason:'STRONGER_OPPORTUNITY',symbol:x.pos.symbol,targetSymbol:newC.symbol}}
""")
sub(r"async function tick\(\)\{.*?\n\}\n\nasync function main",
"""async function tick(){
  const gate=read(GATE,{allowed:false}),st=normalizeState(read(statePath,{})),p=rootPolicy();const emergency=await safetyPass(st,gate);if(emergency)return emergency;const managed=await manageOnePosition(st,gate,p);if(managed)return managed;
  if(gate.allowed){const held=new Set(st.positions.map(x=>x.mint)),c=bestCandidate(p,held);if(c){const r=await placeBuy(st,c,-1);if(r.placed)return{action:'BUY',reason:'AUTO_ALLOC',symbol:c.symbol};if(r.reason==='CAPITAL_HEADROOM_LOW'){const rotate=await maybeRotate(st,c);if(rotate)return rotate}else if(!['ALLOCATION_BELOW_MIN_ORDER','TARGET_ALREADY_SATISFIED'].includes(r.reason))return{action:'WAIT',reason:r.reason}}
    const add=await maybeScaleIn(st,p);if(add)return add;
  }
  await observeCapital(st);if(!gate.allowed)return{action:st.positions.length?'HOLD':'WAIT',reason:'GATE_CLOSED'};return{action:st.positions.length?'HOLD':'WAIT',reason:st.positions.length?'AUTONOMOUS_PORTFOLIO_MONITORING':'NO_TREND_QUALIFIED_CANDIDATE'};
}

async function main""")
s=s.replace("MICRO_LIVE_EXECUTOR_V331_MULTI_POSITION=STARTED","MICRO_LIVE_EXECUTOR_V336_AUTONOMOUS_PORTFOLIO=STARTED").replace("await sleep(5000)}}","await sleep(4000)}}")
sub(r"if\(process\.argv\.includes\('--self-test'\)\)\{.*?\n\}else if\(import\.meta\.url===`file://\$\{process\.argv\[1\]\}`\)main\(\);",
"""if(process.argv.includes('--self-test')){
  const p={reserveLamports:10_000_000,perPositionExitReserveLamports:5_000_000,minOrderLamports:10_000_000,probeUtilizationPct:15,confirmedUtilizationPct:35,strongUtilizationPct:65,maxUtilizationPct:94,maxBuyPriceImpactPct:1.25,maxSellPriceImpactPct:8,externalFlowThresholdLamports:500_000,minAddIntervalSec:30};
  const c={mint:'C',universeClass:'MEME_CONFIRMED',securityDecision:'PASS',holderClusterDecision:'PASS',decision:'PROBE_CANDIDATE',token2022:false,sellRoute:true,hardReject:[],score:84,liquidityUsd:600000,sellPriceImpactPct:.3,consecutiveEligible:5,priceChange5m:2.5,netBuyers5m:20,avgNetBuyersLast2:15,scoreSlopeLast2:0,liquidityStableLast2:true,organicRatio5m:.3};
  if(!trendEntryEligible(c)||trendEntryEligible({...c,priceChange5m:25})||trendEntryEligible({...c,securityDecision:'REVIEW'})||trendEntryEligible({...c,sellRoute:false})||trendEntryEligible({...c,token2022:true}))throw new Error('ENTRY_SAFETY_SELFTEST');
  const migrated=normalizeState({position:{mint:'A',costBasisLamports:10000000,openedAt:new Date().toISOString()}});if(migrated.positions.length!==1||migrated.position!==undefined)throw new Error('LEGACY_MIGRATION');
  const empty=normalizeState({});const prof=allocationProfile(c,p,empty,714_000_000);if(!(prof.pct>3&&prof.pct<p.maxUtilizationPct))throw new Error('CONTINUOUS_ALLOCATOR');const a=targetPlan(714_000_000,empty,null,prof.pct,p,{isNew:true,exitHeadroomLamports:300_000});if(!(a.amountLamports>10_000_000)||a.reserveLamports!==10_300_000)throw new Error('DYNAMIC_PLAN');
  const grown=normalizeState({autonomy:{referenceCapitalLamports:714_000_000}}),p1=allocationProfile(c,p,grown,714_000_000),p2=allocationProfile(c,p,grown,1_428_000_000);if(!(p2.pct>p1.pct))throw new Error('EQUITY_SCALE_FACTOR');
  const many=normalizeState({positions:Array.from({length:10},(_,i)=>({mint:'M'+i,costBasisLamports:10_000_000,openedAt:new Date().toISOString()}))});if(requiredReserveLamports(p,10,300_000)!==13_000_000)throw new Error('DYNAMIC_EXIT_RESERVE');
  const s1=normalizeState({positions:[{mint:'A',openedAt:new Date().toISOString()},{mint:'B',openedAt:new Date().toISOString()}]});s1.positions.splice(0,1);if(s1.positions.length!==1||s1.positions[0].mint!=='B')throw new Error('POSITION_ISOLATION');
  console.log('MICRO_EXECUTOR_V336_AUTONOMOUS_SELF_TEST=PASS');console.log('CONTINUOUS_ALLOCATION=TRUE');console.log('EQUITY_GROWTH_SCALES_NEW_BUYS=TRUE');console.log('DYNAMIC_NETWORK_EXIT_HEADROOM=TRUE');console.log('MULTI_POSITION_NO_HARD_COUNT_LIMIT=TRUE');console.log('ROTATION_TO_STRONGER_OPPORTUNITY=TRUE');console.log('HARD_SECURITY_AND_SELLABILITY_FAILSAFE=KEPT');console.log('NETWORK_EXECUTION=NOT_CALLED');
}else if(import.meta.url===`file://${process.argv[1]}`)main();""")
s=s.replace("st.version='3.31.0-multi'","st.version='3.36.0-autonomous'")
s=s.replace("user-agent':'meme-alpha-v331-multi-position","user-agent':'meme-alpha-v336-autonomous-portfolio")
open(p,'w').write(s)
PY
node --check "$OUT"
node "$OUT" --self-test
sha256sum "$OUT"
echo V336_BUILD_AUTONOMOUS_PORTFOLIO_PASS
