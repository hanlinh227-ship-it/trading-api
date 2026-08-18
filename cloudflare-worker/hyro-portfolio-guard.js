const MAX_SLOTS=3;
const MAX_SAME_DIRECTION=2;
const ENTRY_SPACING_MS=180000;
const STATE_KEY="v771814:hyro:portfolio";

const GROUPS={
  BTC:new Set(["BTC"]),
  ETH_BETA:new Set(["ETH","LDO","ARB","OP","STRK","ENA"]),
  L1:new Set(["SOL","AVAX","SUI","APT","SEI","NEAR","ATOM","INJ","TIA","ADA","DOT"]),
  DEFI:new Set(["AAVE","UNI","CRV","MKR","COMP","SNX","PENDLE","JUP","RUNE"]),
  MEME:new Set(["DOGE","SHIB","PEPE","WIF","BONK","FLOKI","BRETT"]),
  PAYMENTS:new Set(["XRP","XLM","HBAR","ALGO","LTC","BCH"]),
  EXCHANGE:new Set(["BNB","OKB","GT","CRO"]),
  AI:new Set(["FET","RENDER","TAO","WLD","ARKM","AI","AIXBT"]),
  RWA:new Set(["ONDO","OM","POLYX","CFG"])
};
function base(symbol){return String(symbol||"").toUpperCase().replace(/USDT$/,"-").split("-")[0];}
export function hyroCluster(symbol){const b=base(symbol);for(const [g,set] of Object.entries(GROUPS))if(set.has(b))return g;return `OTHER:${b}`;}
function side(x){const s=String(x?.side||"").toUpperCase();return s==="BUY"||s==="LONG"?"BUY":s==="SELL"||s==="SHORT"?"SELL":s;}
function existingItems(t){return [...(t?.positions||[]).map(x=>({symbol:x.symbol,side:side(x),kind:"POSITION"})),...(t?.openOrders||[]).map(x=>({symbol:x.symbol,side:side(x),kind:"ORDER"}))];}
async function getState(env){try{return await env.TRADING_STATE?.get(STATE_KEY,"json")||{};}catch{return {};}}
export async function markHyroPortfolioEntry(env,order){if(!env.TRADING_STATE)return;const old=await getState(env);await env.TRADING_STATE.put(STATE_KEY,JSON.stringify({...old,lastEntryAt:Date.now(),lastSymbol:order?.symbol||null,lastSide:side(order),updatedAt:Date.now()}));}
export async function evaluateHyroPortfolio(env,plan,telemetry,{ignoreSpacing=false}={}){
  const items=existingItems(telemetry),symbol=String(plan?.symbol||"").toUpperCase(),pSide=side(plan),cluster=hyroCluster(symbol),state=await getState(env);
  if(items.length>=MAX_SLOTS)return {ok:false,reason:"MAX_PORTFOLIO_SLOTS",maxSlots:MAX_SLOTS};
  if(items.some(x=>String(x.symbol).toUpperCase()===symbol))return {ok:false,reason:"SYMBOL_ALREADY_ACTIVE"};
  if(!ignoreSpacing&&Number(state.lastEntryAt)>0&&Date.now()-Number(state.lastEntryAt)<ENTRY_SPACING_MS)return {ok:false,reason:"ENTRY_SPACING",retryAfterMs:ENTRY_SPACING_MS-(Date.now()-Number(state.lastEntryAt))};
  const sameDir=items.filter(x=>x.side===pSide).length;
  if(sameDir>=MAX_SAME_DIRECTION)return {ok:false,reason:"SAME_DIRECTION_CAP",sameDirection:sameDir,maxSameDirection:MAX_SAME_DIRECTION};
  const sameCluster=items.filter(x=>x.side===pSide&&hyroCluster(x.symbol)===cluster);
  if(sameCluster.length)return {ok:false,reason:"CLUSTER_DUPLICATION",cluster,conflicts:sameCluster.map(x=>x.symbol)};
  const diversityBonus=items.length===0?1:items.every(x=>hyroCluster(x.symbol)!==cluster)?.08:0;
  return {ok:true,cluster,maxSlots:MAX_SLOTS,sameDirection:sameDir,diversityBonus,items};
}
export function portfolioQuality(plan,guard){const tier=plan?.tier==="A"?3:plan?.tier==="B"?2:1,micro=Number(plan?.context?.microstructure?.score??.5),rr=Number(plan?.rr||0),turn=Math.log10(Math.max(1,Number(plan?.context?.turnover24h||1)));return tier*100+micro*30+Math.min(rr,4)*10+turn+(guard?.diversityBonus||0)*25;}
export const HYRO_PORTFOLIO_POLICY={maxSlots:MAX_SLOTS,maxSameDirection:MAX_SAME_DIRECTION,entrySpacingMs:ENTRY_SPACING_MS};
