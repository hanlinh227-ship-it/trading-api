import fs from 'node:fs';

const APP='/opt/meme-alpha/app';
const SIGNAL=`${APP}/runtime-status/signal-snapshot.json`;
const OUT=`${APP}/runtime-status/trend-pulse.json`;
const POLL_MS=3000;
const DEX='https://api.dexscreener.com/tokens/v1/solana';

const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const n=(v,d=0)=>Number.isFinite(Number(v))?Number(v):d;
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
const atomic=(p,x)=>{const t=p+'.tmp';fs.mkdirSync(new URL('.',`file://${p}`).pathname,{recursive:true});fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p)};

function narrative(text=''){
  const s=String(text).toLowerCase();
  if(/\b(cat|kitty|kitten|nyan|feline|purr|meow|cate|solcat)\b/.test(s))return 'CAT';
  if(/\b(troll|useless|no ?value|novalue|stonkless|rich debt|buttcoin|bullshit|worthless|zero value)\b/.test(s))return 'ABSURD_ANTI_VALUE';
  if(/\b(ai|artificial|intelligence|agent|gpt|llm|anthropic|claude|chatgpt|gooner intelligence|chain of thought|bot)\b/.test(s))return 'AI_TECH_PARODY';
  if(/\b(dog|doge|wif|pup|puppy|inu|pom|pomeranian|bonk)\b/.test(s))return 'DOG_WIF';
  if(/\b(ape|monkey|gorilla)\b/.test(s))return 'APE_PRIMATE';
  if(/\b(trump|maga|kirk|president|senator|politic|election)\b/.test(s))return 'POLITICAL';
  if(/\b(frog|pepe|toad|penguin|raccoon|goat|squirrel|hamster|horse|duck|bear|bull)\b/.test(s))return 'OTHER_ANIMAL';
  if(/\b(phone|fone|helmet|dress|wifhat|wif dress|onfone)\b/.test(s))return 'REMIX_PROP';
  if(/\b(solana|bitcoin|btc|eth|crypto|defi|pump|jupiter|raydium)\b/.test(s))return 'CRYPTO_META';
  return 'OTHER';
}

function choosePair(pairs,mint){
  const xs=(pairs||[]).filter(p=>p?.chainId==='solana'&&(p?.baseToken?.address===mint||p?.quoteToken?.address===mint));
  return xs.sort((a,b)=>n(b?.liquidity?.usd)-n(a?.liquidity?.usd))[0]||null;
}

function calc(pair,mint,meta={}){
  if(!pair)return {mint,symbol:meta.symbol||'',name:meta.name||'',status:'NO_PAIR',pulseScore:0,narrative:narrative(`${meta.symbol||''} ${meta.name||''}`)};
  const t5=pair.txns?.m5||{},t1=pair.txns?.h1||{};
  const buys5=n(t5.buys),sells5=n(t5.sells),buys1=n(t1.buys),sells1=n(t1.sells);
  const tx5=buys5+sells5,tx1=buys1+sells1;
  const v5=n(pair.volume?.m5),v1=n(pair.volume?.h1);
  const prev55Vol=Math.max(1,v1-v5),prev55Tx=Math.max(1,tx1-tx5);
  const expected5Vol=prev55Vol/11,expected5Tx=prev55Tx/11;
  const volumeAcceleration=clamp(v5/Math.max(1,expected5Vol),0,20);
  const txnAcceleration=clamp(tx5/Math.max(1,expected5Tx),0,20);
  const buySellRatio=clamp((buys5+1)/(sells5+1),0,20);
  const buyPressure=tx5>0?(buys5-sells5)/tx5:0;
  const price5m=n(pair.priceChange?.m5,0),price1h=n(pair.priceChange?.h1,0);
  const liquidityUsd=n(pair.liquidity?.usd,0),volume5mUsd=v5;
  const activeBoosts=n(pair.boosts?.active,0);
  const pairAgeMin=pair.pairCreatedAt?Math.max(0,(Date.now()-n(pair.pairCreatedAt))/60000):null;
  let pulseScore=0;
  pulseScore+=clamp(volumeAcceleration/2,0,1)*30;
  pulseScore+=clamp(txnAcceleration/2,0,1)*22;
  pulseScore+=clamp((buySellRatio-0.8)/1.2,0,1)*20;
  pulseScore+=(price5m>=0.05&&price5m<=12)?14:(price5m>12&&price5m<=18?6:0);
  pulseScore+=clamp(Math.log10(Math.max(1,liquidityUsd))/6,0,1)*14;
  const weakOrganic=volumeAcceleration<1.15||txnAcceleration<1.10||buySellRatio<1.05;
  if(activeBoosts>0&&weakOrganic)pulseScore-=12;
  if(price5m>18)pulseScore-=18;
  if(price5m<-6)pulseScore-=20;
  pulseScore=clamp(Math.round(pulseScore),0,100);
  let status='NEUTRAL';
  if(price5m>18||(price5m<0&&buySellRatio<0.85))status='EXHAUSTED';
  else if(liquidityUsd>=50000&&volumeAcceleration>=1.45&&txnAcceleration>=1.30&&buySellRatio>=1.20&&price5m>=0.05&&price5m<=15)status='BREAKOUT';
  else if(liquidityUsd>=50000&&volumeAcceleration>=1.05&&txnAcceleration>=1.0&&buySellRatio>=1.0&&price5m>=-0.5)status='WARMING';
  return {mint,symbol:meta.symbol||pair.baseToken?.symbol||'',name:meta.name||pair.baseToken?.name||'',pairAddress:pair.pairAddress||null,dexId:pair.dexId||null,narrative:narrative(`${meta.symbol||''} ${meta.name||''} ${pair.baseToken?.symbol||''} ${pair.baseToken?.name||''}`),status,pulseScore,price5m,price1h,buys5,sells5,tx5,volume5mUsd,volume1hUsd:v1,volumeAcceleration:Number(volumeAcceleration.toFixed(3)),txnAcceleration:Number(txnAcceleration.toFixed(3)),buySellRatio:Number(buySellRatio.toFixed(3)),buyPressure:Number(buyPressure.toFixed(3)),liquidityUsd,activeBoosts,promotionFlag:activeBoosts>0,pairAgeMin:pairAgeMin===null?null:Number(pairAgeMin.toFixed(1))};
}

function themeBoard(rows){
  const m=new Map();
  for(const r of rows){
    if(r.narrative==='OTHER'||r.status==='NO_PAIR')continue;
    const x=m.get(r.narrative)||{narrative:r.narrative,count:0,breakouts:0,warming:0,avgPulse:0,avgVolAccel:0,totalVolume5mUsd:0,promoted:0,symbols:[]};
    x.count++; if(r.status==='BREAKOUT')x.breakouts++; if(r.status==='WARMING')x.warming++; x.avgPulse+=r.pulseScore; x.avgVolAccel+=r.volumeAcceleration||0; x.totalVolume5mUsd+=r.volume5mUsd||0; if(r.promotionFlag)x.promoted++; if(r.symbol&&x.symbols.length<8)x.symbols.push(r.symbol); m.set(r.narrative,x);
  }
  return [...m.values()].map(x=>{x.avgPulse=Number((x.avgPulse/Math.max(1,x.count)).toFixed(1));x.avgVolAccel=Number((x.avgVolAccel/Math.max(1,x.count)).toFixed(2));const breadth=Math.min(1,x.count/3),breakout=Math.min(1,x.breakouts/2),flow=Math.min(1,x.avgPulse/80);x.strength=Math.round((0.35*breadth+0.40*breakout+0.25*flow)*100);return x}).sort((a,b)=>b.strength-a.strength||b.totalVolume5mUsd-a.totalVolume5mUsd);
}

async function fetchPairs(mints){
  if(!mints.length)return [];
  const u=`${DEX}/${mints.join(',')}`;
  const r=await fetch(u,{headers:{accept:'application/json','user-agent':'meme-alpha-v290-trend-pulse'},signal:AbortSignal.timeout(8000)});
  if(!r.ok)throw new Error(`DEX_HTTP_${r.status}`);
  const j=await r.json();
  return Array.isArray(j)?j:[];
}

async function once(){
  const s=read(SIGNAL,{candidates:[]}),cs=(s.candidates||[]).filter(c=>c.mint).slice(0,30);
  const mints=[...new Set(cs.map(c=>c.mint))].slice(0,30),pairs=await fetchPairs(mints),rows=[];
  for(const c of cs)rows.push(calc(choosePair(pairs,c.mint),c.mint,c));
  const themes=themeBoard(rows);
  const out={version:'2.9.0',timestamp:new Date().toISOString(),source:'DEXSCREENER_TOKENS_V1',pollMs:POLL_MS,signalTimestamp:s.timestamp||null,candidateCount:cs.length,pairRows:pairs.length,rows:rows.sort((a,b)=>b.pulseScore-a.pulseScore),themes};
  atomic(OUT,out);
  console.log(`TREND_PULSE_V290_OK candidates=${cs.length} pairs=${pairs.length} topTheme=${themes[0]?.narrative||'NONE'} strength=${themes[0]?.strength||0}`);
  for(const t of themes.slice(0,5))console.log(`THEME ${t.narrative} strength=${t.strength} count=${t.count} breakout=${t.breakouts} pulse=${t.avgPulse} volAccel=${t.avgVolAccel} symbols=${t.symbols.join(',')}`);
  return out;
}

async function main(){
  console.log('TREND_PULSE_V290=STARTED');
  while(true){try{await once()}catch(e){console.error('TREND_PULSE_ERROR',String(e.message||e).slice(0,180))}await sleep(POLL_MS)}
}

if(process.argv.includes('--self-test')){
  const a=narrative('USELESS TROLL'),b=narrative('Anonymous Cat'),c=narrative('Artificial Intelligence Agent');
  if(a!=='ABSURD_ANTI_VALUE'||b!=='CAT'||c!=='AI_TECH_PARODY')throw new Error('NARRATIVE_SELFTEST');
  const p={chainId:'solana',baseToken:{address:'X',symbol:'CAT',name:'Cat'},txns:{m5:{buys:30,sells:10},h1:{buys:70,sells:50}},volume:{m5:12000,h1:30000},priceChange:{m5:2,h1:8},liquidity:{usd:100000},boosts:{active:0},pairCreatedAt:Date.now()-3600000};
  const r=calc(p,'X',{symbol:'CAT',name:'Cat'});if(r.status!=='BREAKOUT'||r.pulseScore<60)throw new Error('PULSE_SELFTEST');
  console.log('TREND_PULSE_V290_SELF_TEST=PASS');console.log('POLL_INTERVAL_MS=3000');console.log('DEX_BATCH_MAX_TOKENS=30');console.log('PAID_BOOSTS_NOT_USED_AS_POSITIVE_SIGNAL=TRUE');console.log('NETWORK_EXECUTION=NOT_CALLED');
}else if(process.argv.includes('--once')){once().catch(e=>{console.error(e);process.exit(1)})}
else if(import.meta.url===`file://${process.argv[1]}`)main();
