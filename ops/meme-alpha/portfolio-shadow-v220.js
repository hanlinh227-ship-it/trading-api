import fs from 'node:fs';
const APP='/opt/meme-alpha/app';
const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;
const TREND=`${APP}/runtime-status/trend-pulse.json`;
const OUT=`${APP}/runtime-status/portfolio-shadow.json`;
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const atomic=(p,x)=>{const t=p+'.tmp';fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p)};
const hardEmpty=v=>Array.isArray(v)?v.length===0:!v;
function impact(c){return Math.abs(n(c?.sellPriceImpactPct??c?.sellImpactPct??c?.priceImpactPct,99))}
function safe(c){return !!c&&c.universeClass==='MEME_CONFIRMED'&&c.securityDecision==='PASS'&&c.holderClusterDecision==='PASS'&&!c.token2022&&c.sellRoute===true&&hardEmpty(c.hardReject)&&n(c.liquidityUsd)>=50000&&impact(c)<=1.25}
function pulseMap(){const t=read(TREND,{});return {t,by:new Map((t.rows||[]).map(x=>[x.mint,x])),themes:new Map((t.themes||[]).map(x=>[x.narrative,x]))}}
function score(c,p,theme){
 let s=n(c.score); if(!p)return s;
 if(n(p.volumeAcceleration)>=1.45)s+=4; else if(n(p.volumeAcceleration)>=1.10)s+=2;
 if(n(p.txnAcceleration)>=1.30)s+=3; else if(n(p.txnAcceleration)>=1.05)s+=1;
 if(n(p.buySellRatio)>=1.25)s+=2;
 if(n(theme?.strength)>=60)s+=2;
 if(n(p.pulseScore)>=70)s+=1;
 if(p.status==='EXHAUSTED')s-=10;
 if(p.promotionFlag===true&&n(p.pulseScore)<65)s-=3;
 return clamp(s,0,100);
}
function eligible(c,p,theme){
 if(!safe(c)||c.decision!=='PROBE_CANDIDATE'||n(c.consecutiveEligible)<1)return false;
 const os=score(c,p,theme),chg=p?n(p.price5m,-999):n(c.priceChange5m,-999),net=n(c.netBuyers5m,-999),avg=n(c.avgNetBuyersLast2,net),slope=n(c.scoreSlopeLast2,0);
 const pf=!!p&&p.status!=='EXHAUSTED'&&n(p.pulseScore)>=55&&n(p.volumeAcceleration)>=1.05&&n(p.txnAcceleration)>=1.0&&n(p.buySellRatio)>=1.10&&n(p.tx5)>=4;
 return os>=62&&chg>=(pf?0.05:0.15)&&chg<=15&&(net>=2||pf)&&avg>=1.5&&slope>=-4&&c.liquidityStableLast2!==false;
}
function quality(c,p,theme){
 const os=score(c,p,theme); let q=os;
 q+=Math.min(8,Math.max(0,n(c.netBuyers5m))/5);
 q+=Math.min(7,Math.max(0,n(p?.pulseScore)-50)/7);
 q+=Math.min(5,n(theme?.strength)/20);
 q-=Math.max(0,n(p?.price5m,n(c.priceChange5m))-10)*1.5;
 q-=Math.max(0,impact(c)-0.5)*8;
 return q;
}
function tier(q,p){
 if(q>=95&&n(p?.pulseScore)>=80)return {name:'STRONG',capPct:32};
 if(q>=85)return {name:'CONFIRMED',capPct:24};
 return {name:'PROBE',capPct:15};
}
function plan(){
 const s=read(SIGNAL,{candidates:[]}),{t,by,themes}=pulseMap();
 const signalAge=(Date.now()-Date.parse(s.timestamp||0))/1000,trendAge=(Date.now()-Date.parse(t.timestamp||0))/1000;
 const rows=(s.candidates||[]).map(c=>{const p=by.get(c.mint),th=themes.get(p?.narrative);return {c,p,th,q:quality(c,p,th)}}).filter(x=>eligible(x.c,x.p,x.th)).sort((a,b)=>b.q-a.q);
 const picks=[];const narrativeCount=new Map();
 for(const x of rows){
  if(picks.length>=3)break;
  const nar=x.p?.narrative||'UNKNOWN';
  if((narrativeCount.get(nar)||0)>=2)continue;
  const tr=tier(x.q,x.p);picks.push({mint:x.c.mint,symbol:x.c.symbol,narrative:nar,quality:Number(x.q.toFixed(1)),tier:tr.name,maxPositionPct:tr.capPct,score:x.c.score,pulse:x.p?.pulseScore??null,trendStatus:x.p?.status??null,liquidityUsd:x.c.liquidityUsd,impactPct:impact(x.c)});narrativeCount.set(nar,(narrativeCount.get(nar)||0)+1);
 }
 let target=0;
 if(picks.length===1)target=Math.min(32,picks[0].maxPositionPct);
 if(picks.length===2)target=Math.min(65,picks.reduce((a,x)=>a+x.maxPositionPct,0));
 if(picks.length>=3){const avg=picks.reduce((a,x)=>a+x.quality,0)/picks.length;target=avg>=92?94:avg>=84?82:70;}
 let remain=target;for(const x of picks){x.targetPct=Math.min(x.maxPositionPct,remain);remain-=x.targetPct}
 if(remain>0&&picks.length){for(const x of picks){if(remain<=0)break;const room=x.maxPositionPct-x.targetPct,add=Math.min(room,remain);x.targetPct+=add;remain-=add}}
 const narratives={};for(const x of picks)narratives[x.narrative]=n(narratives[x.narrative])+x.targetPct;
 return {version:'2.20-shadow',timestamp:new Date().toISOString(),signalAgeSec:Number(signalAge.toFixed(1)),trendAgeSec:Number(trendAge.toFixed(1)),eligibleCount:rows.length,maxPositions:3,maxSinglePositionPct:32,maxNarrativePct:45,maxPortfolioPct:94,reserveSol:0.01,targetPortfolioPct:target,picks,narratives,liveExecution:false};
}
const out=plan();atomic(OUT,out);console.log(JSON.stringify(out,null,2));
if(process.argv.includes('--self-test')){
 if(out.maxPositions!==3||out.maxSinglePositionPct!==32||out.maxPortfolioPct!==94)throw new Error('POLICY_SELF_TEST');
 console.log('PORTFOLIO_SHADOW_V220_SELF_TEST=PASS');
}
