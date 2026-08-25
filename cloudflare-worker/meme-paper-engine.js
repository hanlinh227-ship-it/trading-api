import {MEME_AUTO_DESIGN,computeMemeCapitalPlan} from "./meme-auto-design.js";

export const MEME_PAPER_VERSION="MEME-AUTO-0.3.0-PAPER";
const DEX="https://api.dexscreener.com";
const JUP="https://lite-api.jup.ag";
const SOL="So11111111111111111111111111111111111111112";
const USDC="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const STATE_KEY="meme:paper:state:v1";
const n=(x,d=0)=>Number.isFinite(Number(x))?Number(x):d;
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const now=()=>Date.now();
async function j(url,init){const r=await fetch(url,init);if(!r.ok)throw new Error(`HTTP_${r.status}`);return r.json();}
function store(env){return env.TRADING_STATE||env.BYBIT_AUTO_STATE||null;}
function empty(){return {version:MEME_PAPER_VERSION,mode:"PAPER",startingEquityUsd:30,cashUsd:30,equityUsd:30,peakEquityUsd:30,positions:{},closed:[],watch:[],lastScan:null,realizedUsd:0,trades:0,wins:0,losses:0};}
export async function getMemePaperState(env){const kv=store(env);if(!kv)return empty();try{return {...empty(),...JSON.parse(await kv.get(STATE_KEY)||"{}")};}catch{return empty();}}
async function save(env,s){const kv=store(env);if(kv)await kv.put(STATE_KEY,JSON.stringify(s));return s;}

async function discover(){
 const out=[];
 for(const path of ["/token-profiles/latest/v1","/token-boosts/top/v1","/token-boosts/latest/v1"]){try{const a=await j(DEX+path);for(const x of (Array.isArray(a)?a:[]))if(x.chainId==="solana"&&x.tokenAddress)out.push(x.tokenAddress);}catch{}}
 return [...new Set(out)].slice(0,40);
}
async function pairsFor(mint){try{const d=await j(`${DEX}/token-pairs/v1/solana/${mint}`);return Array.isArray(d)?d:[];}catch{return [];}}
function bestPair(ps){return ps.filter(p=>n(p.liquidity?.usd)>0&&n(p.priceUsd)>0).sort((a,b)=>n(b.liquidity?.usd)-n(a.liquidity?.usd))[0]||null;}
async function sellRoute(mint,usd){try{const amount=Math.max(1,Math.floor((usd/Math.max(.000000001,n((await price(mint))?.usdPrice)))*1e6));const q=await j(`${JUP}/swap/v1/quote?inputMint=${encodeURIComponent(mint)}&outputMint=${USDC}&amount=${amount}&slippageBps=300&restrictIntermediateTokens=true`);return {ok:!!q?.outAmount,priceImpactPct:n(q?.priceImpactPct),route:q};}catch{return {ok:false};}}
async function price(mint){try{return await j(`${JUP}/price/v3?ids=${encodeURIComponent(mint)}`).then(x=>x?.[mint]||null);}catch{return null;}}
function score(p){
 const liq=n(p.liquidity?.usd),v5=n(p.volume?.m5),v1=n(p.volume?.h1),b=n(p.txns?.m5?.buys),s=n(p.txns?.m5?.sells),chg=n(p.priceChange?.m5),h=n(p.priceChange?.h1);
 const liquidity=clamp((Math.log10(Math.max(1,liq))-4)*10,0,15);
 const flow=clamp(8+(b-s)*.25+(v5>0&&v1>0?Math.min(8,(v5/(v1/12||1))*2):0),0,20);
 const momentum=clamp(6+chg*.35+(h>0?3:0)-(chg>25?6:0),0,15);
 const safety=liq>=50000?27:liq>=30000?24:0;
 const holders=15; // conservative neutral until RPC holder intelligence adapter is enabled
 return {total:Math.round(safety+holders+liquidity+flow+momentum),parts:{safety,holders,liquidity,flow,momentum}};
}
function regime(p){const m=n(p.priceChange?.m5),h=n(p.priceChange?.h1),b=n(p.txns?.m5?.buys),s=n(p.txns?.m5?.sells);if(m>25)return "EUPHORIA";if(m<-10||b<s*.7)return "DISTRIBUTION";if(m>4&&h>8&&b>s)return "BREAKOUT_EXPANSION";if(m>0&&h>3&&b>=s)return "MOMENTUM_BUILD";if(m>-4&&h>5&&b>=s)return "HEALTHY_PULLBACK";return "EARLY_DISCOVERY";}
async function evaluate(mint){const p=bestPair(await pairsFor(mint));if(!p)return null;const liq=n(p.liquidity?.usd);if(liq<MEME_AUTO_DESIGN.hardSafety.minLiquidityUsd)return null;const sc=score(p),rg=regime(p);const route=await sellRoute(mint,5);const eligible=route.ok&&route.priceImpactPct<=MEME_AUTO_DESIGN.executionDesign.hardMaxPriceImpactPct&&MEME_AUTO_DESIGN.allowedEntryRegimes.includes(rg)&&sc.total>=MEME_AUTO_DESIGN.qualityScore.entryScore;return {mint,symbol:p.baseToken?.symbol||mint.slice(0,6),name:p.baseToken?.name||"",pairAddress:p.pairAddress,priceUsd:n(p.priceUsd),liquidityUsd:liq,volumeM5:n(p.volume?.m5),buysM5:n(p.txns?.m5?.buys),sellsM5:n(p.txns?.m5?.sells),priceChangeM5:n(p.priceChange?.m5),score:sc.total,scoreParts:sc.parts,regime:rg,sellRoute:route.ok,priceImpactPct:route.priceImpactPct,eligible,checkedAt:new Date().toISOString()};}
function markPnl(pos,px){return (px-pos.entryPrice)*pos.qty;}
async function manage(env,s){for(const [mint,pos] of Object.entries(s.positions||{})){const ps=bestPair(await pairsFor(mint));if(!ps)continue;const px=n(ps.priceUsd),gain=(px/pos.entryPrice-1)*100;pos.markPrice=px;pos.unrealizedUsd=markPnl(pos,px);pos.maxGainPct=Math.max(n(pos.maxGainPct),gain);let sellPct=0,reason="";if(gain<=-MEME_AUTO_DESIGN.exits.hardLossPct){sellPct=100;reason="HARD_STOP";}else if(gain<=-10){sellPct=100;reason="SMART_CUT";}else if(!pos.tp1&&gain>=MEME_AUTO_DESIGN.exits.tp1.gainPct){sellPct=25;reason="TP1";pos.tp1=true;}else if(!pos.tp2&&gain>=MEME_AUTO_DESIGN.exits.tp2.gainPct){sellPct=25;reason="TP2";pos.tp2=true;}else if(pos.maxGainPct>=20&&gain<=Math.max(8,pos.maxGainPct*.55)){sellPct=100;reason="TRAIL";}
 if(sellPct){const qty=pos.qty*sellPct/100,pnl=(px-pos.entryPrice)*qty,proceeds=px*qty;s.cashUsd+=proceeds;s.realizedUsd+=pnl;pos.qty-=qty;pos.costUsd-=pos.entryPrice*qty;if(pos.qty<=1e-12){delete s.positions[mint];s.trades++;if(pnl>=0)s.wins++;else s.losses++;}s.closed.unshift({mint,symbol:pos.symbol,reason,pnlUsd:pnl,price:px,at:new Date().toISOString(),partial:sellPct<100});s.closed=s.closed.slice(0,200);}}
 s.equityUsd=s.cashUsd+Object.values(s.positions).reduce((a,p)=>a+n(p.markPrice,p.entryPrice)*p.qty,0);s.peakEquityUsd=Math.max(s.peakEquityUsd,s.equityUsd);return s;}
export async function runMemePaperCycle(env){let s=await getMemePaperState(env);s=await manage(env,s);const mints=await discover(),cand=[];for(const mint of mints.slice(0,20)){try{const x=await evaluate(mint);if(x)cand.push(x);}catch{}}cand.sort((a,b)=>b.score-a.score);s.watch=cand.slice(0,12);const plan=computeMemeCapitalPlan({equityUsd:s.equityUsd,peakEquityUsd:s.peakEquityUsd,availableUsd:s.cashUsd,qualityScore:cand[0]?.score||85,liquidityUsd:cand[0]?.liquidityUsd});const slots=plan.ok?Math.max(0,plan.maxOpenPositions-Object.keys(s.positions).length):0;for(const c of cand.filter(x=>x.eligible).slice(0,slots)){if(s.positions[c.mint])continue;const cp=computeMemeCapitalPlan({equityUsd:s.equityUsd,peakEquityUsd:s.peakEquityUsd,availableUsd:s.cashUsd,liquidityUsd:c.liquidityUsd,qualityScore:c.score});if(!cp.ok||cp.positionUsd>s.cashUsd)continue;const qty=cp.positionUsd/c.priceUsd;s.cashUsd-=cp.positionUsd;s.positions[c.mint]={mint:c.mint,symbol:c.symbol,entryPrice:c.priceUsd,markPrice:c.priceUsd,qty,costUsd:cp.positionUsd,score:c.score,regime:c.regime,openedAt:new Date().toISOString(),tp1:false,tp2:false,maxGainPct:0};}
s.equityUsd=s.cashUsd+Object.values(s.positions).reduce((a,p)=>a+n(p.markPrice,p.entryPrice)*p.qty,0);s.lastScan={at:new Date().toISOString(),discovered:mints.length,evaluated:cand.length,eligible:cand.filter(x=>x.eligible).length,data:"DEXSCREENER_FREE",quote:"JUPITER_LITE_FREE"};await save(env,s);return {ok:true,version:MEME_PAPER_VERSION,mode:"PAPER",noWallet:true,noSigning:true,noRealExecution:true,state:s};}
export async function resetMemePaper(env){return save(env,empty());}
