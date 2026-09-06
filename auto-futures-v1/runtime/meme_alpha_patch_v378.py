#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: meme_alpha_patch_v378.py <micro-live-executor.js>")

p = Path(sys.argv[1])
s = p.read_text()

OLD_OPP = "function opportunityLane(c){const score=opportunityScore(c),base=n(c.score),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net);if(base<58)return false;const standard=score>=72;const liquid=score>=66&&liq>=500000&&net>=1&&imp<=0.80;const flow=score>=62&&liq>=100000&&net>=5&&avg>=3&&chg>=0.20&&imp<=0.80;return standard||liquid||flow}"
NEW_OPP = "function opportunityLane(c){const score=opportunityScore(c),base=n(c.score),liq=n(c.liquidityUsd),imp=impact(c),chg=n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net);if(base<55)return false;const standard=score>=69;const liquid=score>=63&&liq>=300000&&net>=1&&imp<=0.90;const flow=score>=59&&liq>=75000&&net>=4&&avg>=2.5&&chg>=0.05&&imp<=0.90;return standard||liquid||flow}"

OLD_ENTRY = "function trendEntryEligible(c){if(!coreSafe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.consecutiveEligible)<1)return false;const p=pulseFor(c),chg=p?n(p.price5m,-999):n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net),slope=n(c.scoreSlopeLast2,0),stable=c.liquidityStableLast2!==false;const pulseFlow=!!p&&p.status!=='EXHAUSTED'&&n(p.pulseScore)>=55&&n(p.volumeAcceleration)>=1.05&&n(p.txnAcceleration)>=1.0&&n(p.buySellRatio)>=1.10&&n(p.tx5)>=4;const buyerFlow=net>=2&&avg>=1.5;const fastFlow=net>=1&&pulseFlow;const momentumFloor=pulseFlow?0.05:0.15;return chg>=momentumFloor&&chg<=15&&(buyerFlow||fastFlow)&&slope>=-4&&stable&&opportunityLane(c)}"
NEW_ENTRY = "function trendEntryEligible(c){if(!coreSafe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.consecutiveEligible)<1)return false;const p=pulseFor(c),chg=p?n(p.price5m,-999):n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net),slope=n(c.scoreSlopeLast2,0),stable=c.liquidityStableLast2!==false;const pulseFlow=!!p&&p.status!=='EXHAUSTED'&&n(p.pulseScore)>=52&&n(p.volumeAcceleration)>=1.02&&n(p.txnAcceleration)>=0.95&&n(p.buySellRatio)>=1.05&&n(p.tx5)>=3;const buyerFlow=net>=1&&avg>=1;const fastFlow=net>=1&&pulseFlow;const momentumFloor=pulseFlow?0.00:0.10;return chg>=momentumFloor&&chg<=18&&(buyerFlow||fastFlow)&&slope>=-6&&stable&&opportunityLane(c)}"

OLD_ROT = "function rotationSource(st,newC){\n  const ns=expectedEdge(st,newC),newImpact=impact(newC),rows=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c).map(x=>({...x,oldScore:expectedEdge(st,x.c),weak:softTrendWeak(x.c),severe:severeTrendBreak(x.c)})).sort((a,b)=>a.oldScore-b.oldScore);\n  for(const x of rows){\n    const switchingCost=(newImpact+Math.max(0,n(x.pos.lastPreviewImpactPct,impact(x.c))))*1.5,advantage=ns-x.oldScore-switchingCost,ret=n(x.pos.lastReturnPct),peak=n(x.pos.peakReturnPct),winner=ret>0||peak>=8||x.pos.tp1Done||x.pos.tp2Done||x.pos.tp3Done||x.pos.profitProtectDone;\n    const threshold=x.severe?0:(winner?(ret>=12||peak>=20?34:28):(x.weak?5:13));\n    if(x.severe||advantage>=threshold)return{...x,advantage,switchingCost,winner,threshold,ret,peak};\n  }\n  return null;\n}"
NEW_ROT = "function rotationSource(st,newC){\n  const ns=expectedEdge(st,newC),newImpact=impact(newC),now=Date.now(),rows=st.positions.map((pos,index)=>({pos,index,c:candidate(pos.mint)})).filter(x=>x.c).map(x=>({...x,oldScore:expectedEdge(st,x.c),weak:softTrendWeak(x.c),severe:severeTrendBreak(x.c)})).sort((a,b)=>a.oldScore-b.oldScore);\n  for(const x of rows){\n    const switchingCost=(newImpact+Math.max(0,n(x.pos.lastPreviewImpactPct,impact(x.c))))*1.25,advantage=ns-x.oldScore-switchingCost,ret=n(x.pos.lastReturnPct),peak=n(x.pos.peakReturnPct),winner=ret>0||peak>=8||x.pos.tp1Done||x.pos.tp2Done||x.pos.tp3Done||x.pos.profitProtectDone,ageMin=Math.max(0,(now-Date.parse(x.pos.openedAt||now))/60000),stagnant=ageMin>=18&&ret<=4&&peak<10&&n(x.c.netBuyers5m)<=2&&n(x.c.avgNetBuyersLast2)<=2;\n    const threshold=x.severe?0:(stagnant?4:(winner?(ret>=12||peak>=20?24:18):(x.weak?3:8)));\n    if(x.severe||advantage>=threshold)return{...x,advantage,switchingCost,winner,threshold,ret,peak,stagnant,ageMin};\n  }\n  return null;\n}"

OLD_FRAC = "const frac=x.severe?.50:x.winner?clamp(.15+x.advantage/180,.15,.28):x.weak?.50:clamp(.20+x.advantage/100,.20,.45),reason=x.winner?'AUTO_WINNER_ROTATE_TO_STRONGER_OPPORTUNITY':'AUTO_ROTATE_TO_STRONGER_OPPORTUNITY';"
NEW_FRAC = "const frac=x.severe?.65:x.stagnant?.60:x.winner?clamp(.20+x.advantage/150,.20,.35):x.weak?.65:clamp(.30+x.advantage/90,.30,.60),reason=x.winner?'AUTO_WINNER_ROTATE_TO_STRONGER_OPPORTUNITY':'AUTO_ROTATE_TO_STRONGER_OPPORTUNITY';"

OLD_ALLOC = "const invested=portfolioInvested(st),exposure=clamp(invested/capitalBaseLamports,0,1),freeRatio=clamp((capitalBaseLamports-invested)/capitalBaseLamports,0,1),basePct=4+31*Math.pow(quality,1.20),cashBoost=1+0.38*freeRatio,pct=clamp(basePct*growth*cashBoost,0,p.maxUtilizationPct);"
NEW_ALLOC = "const invested=portfolioInvested(st),exposure=clamp(invested/capitalBaseLamports,0,1),freeRatio=clamp((capitalBaseLamports-invested)/capitalBaseLamports,0,1),basePct=5+28*Math.pow(quality,1.12),cashBoost=1+0.45*freeRatio,pct=clamp(basePct*growth*cashBoost,0,p.maxUtilizationPct);"

pairs = [
    (OLD_OPP, NEW_OPP, "opportunity lane"),
    (OLD_ENTRY, NEW_ENTRY, "entry eligibility"),
    (OLD_ROT, NEW_ROT, "rotation source"),
    (OLD_FRAC, NEW_FRAC, "rotation fraction"),
    (OLD_ALLOC, NEW_ALLOC, "allocation profile"),
]

for old, new, name in pairs:
    if new in s:
        continue
    if old not in s:
        raise SystemExit(f"PATCH_MISMATCH: {name}")
    s = s.replace(old, new, 1)

marker = "MICRO_LIVE_EXECUTOR_V378_AGGRESSIVE_ROTATION"
if marker not in s:
    s = s.replace("MICRO_LIVE_EXECUTOR_V360_PROFIT_AWARE=STARTED", marker + "=STARTED", 1)

p.write_text(s)
print("MEME_V378_PATCH=PASS")
