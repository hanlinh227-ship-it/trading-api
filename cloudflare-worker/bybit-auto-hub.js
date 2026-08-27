import {telegramApiRequest} from "./providers/telegram-client.js";
import {getBybitAutoV1State} from "./bybit-auto-v1.js";
import {getBybitLearningState} from "./bybit-learning-engine.js";
import {recoverBybitCanonicalLearning,getBybitLearningRecoveryState} from "./bybit-learning-recovery.js";
import {probeBybitAiBridge} from "./bybit-ai-scalp-gate.js";
import {bybitExecutionMode,BYBIT_AUTO_VERSION,bybitAutoConfig} from "./bybit-auto-config.js";
import {bybitV5} from "./bybit-v5-client.js";
import {MEME_AUTO_VERSION,MEME_AUTO_MODE,MEME_AUTO_DESIGN,getMemeAutoDesignStatus} from "./meme-auto-design.js";
import {getMemePaperState,runMemePaperCycle} from "./meme-paper-engine.js";
import {FOREX_AUTO_VERSION,forexAutoConfig} from "./forex-auto-config.js";
const json=(b,s=200)=>new Response(JSON.stringify(b,null,2),{status:s,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}}),fmt=(v,d=2)=>Number.isFinite(Number(v))?Number(v).toFixed(d):"—",money=v=>Number.isFinite(Number(v))?`${Number(v)>=0?"+":""}$${Number(v).toFixed(2)}`:"—",px=v=>Number.isFinite(Number(v))?Number(v).toPrecision(7).replace(/0+$/,'').replace(/\.$/,''):"—";
const auth=(u,e)=>{const g=String(u?.callback_query?.from?.id??u?.message?.from?.id??""),w=String(e.TELEGRAM_ALLOWED_USER_ID||e.TELEGRAM_CHAT_ID||"");return !w||g===w;};

// ─── MENUS ───────────────────────────────────────────────────────────────────
const rootMenu=()=>({inline_keyboard:[
  [{text:"🪙 BYBIT",callback_data:"hub:bybit"},{text:"💱 FOREX",callback_data:"hub:forex"}],
  [{text:"🟣 MEME",callback_data:"hub:meme"},{text:"🔄 REFRESH",callback_data:"hub:home"}]
]});
const bybitMenu=()=>({inline_keyboard:[
  [{text:"📊 DASHBOARD",callback_data:"auto:dashboard"}],
  [{text:"📌 POSITIONS",callback_data:"auto:positions"},{text:"🧠 AI",callback_data:"auto:ai"}],
  [{text:"🔍 SCAN",callback_data:"auto:scan"}],
  [{text:"🏠 HUB",callback_data:"hub:home"},{text:"🔄 REFRESH",callback_data:"auto:dashboard"}]
]});
const memeMenu=()=>({inline_keyboard:[[{text:"🤖 PAPER DASHBOARD",callback_data:"meme:dashboard"}],[{text:"🔎 SCAN NOW",callback_data:"meme:scan"},{text:"📌 PAPER POSITIONS",callback_data:"meme:positions"}],[{text:"👀 WATCH",callback_data:"meme:watch"},{text:"📈 PNL",callback_data:"meme:pnl"}],[{text:"🛡️ SAFETY",callback_data:"meme:safety"},{text:"💰 CAPITAL",callback_data:"meme:capital"}],[{text:"🎯 ENTRY / EXIT",callback_data:"meme:trade"},{text:"📚 LEARNING",callback_data:"meme:learning"}],[{text:"⬅️ HUB",callback_data:"hub:home"},{text:"🔄 REFRESH",callback_data:"meme:dashboard"}]]});
async function send(e,id,t,m=rootMenu()){return telegramApiRequest(e,"sendMessage",{chat_id:id||e.TELEGRAM_CHAT_ID,text:t,reply_markup:m,disable_web_page_preview:true});}

// ─── DATA ─────────────────────────────────────────────────────────────────────
async function snap(e){
  const state=await getBybitAutoV1State(e),api=bybitV5(e),cfg=bybitAutoConfig(e),
    [w,p,o,ai,l,rec]=await Promise.allSettled([api.wallet(),api.positions(),api.openOrders(),probeBybitAiBridge(e),getBybitLearningState(e),getBybitLearningRecoveryState(e)]),
    acct=w.status==="fulfilled"?(w.value?.result?.list?.[0]||{}):{},
    coin=(acct.coin||[]).find(x=>x.coin==="USDT")||{};
  return {state,cfg,mode:bybitExecutionMode(e),
    account:{equity:Number(acct.totalEquity||coin.equity||0),wallet:Number(acct.totalWalletBalance||coin.walletBalance||0),available:Number(acct.totalAvailableBalance||coin.availableToWithdraw||0),initialMargin:Number(acct.totalInitialMargin||0),imRate:Number(acct.accountIMRate||0)},
    positions:p.status==="fulfilled"?(p.value?.result?.list||[]).filter(x=>Number(x.size||0)>0):[],
    orders:o.status==="fulfilled"?(o.value?.result?.list||[]).filter(x=>!["Filled","Cancelled","Rejected","Deactivated"].includes(String(x.orderStatus))):[],
    ai:ai.status==="fulfilled"?ai.value:{ok:false,error:String(ai.reason||"AI_HEALTH_UNAVAILABLE")},
    learning:l.status==="fulfilled"?l.value:{summary:{}},
    recovery:rec.status==="fulfilled"?rec.value:null};}

function bybitIntegrityState(s){const lr=s.learning||{},rec=s.state?.lastLiveOutcomeReconcile||{},rows=Array.isArray(rec.results)?rec.results:[],pending=rows.filter(x=>x?.reconciled===false),truncated=!!s.state?.lastPnlReconcile?.truncated,authority=lr.outcomeAuthority==="NET_PNL_AFTER_FEES",clean=lr.cleanNamespace===true,version=lr.dataIntegrityVersion==="BYBIT_LEARNING_NET_PNL_V2",ok=authority&&clean&&version&&!truncated&&!pending.length;return {ok,status:ok?"SYNC":"REVIEW",pending:pending.map(x=>x.symbol),truncated,authority:lr.outcomeAuthority||"UNKNOWN",dataIntegrityVersion:lr.dataIntegrityVersion||"UNKNOWN",legacyV1Quarantined:!!lr.legacyV1Quarantined,lastReconcileAt:rec.at||s.state?.lastPnlReconcile?.at||null};}

// ─── AI HEALTH ────────────────────────────────────────────────────────────────
// FIX: ok+allRequiredOnline===false → DEGRADED, not WARMING
function aiHealthState(a={}){
  const ps=a.providers||{},states=["claude","codex"].map(p=>String(ps[p]?.state||"UNKNOWN").toUpperCase());
  if(a.allRequiredConfigured===false||a.requiredQuorum!==2||/MISSING|NOT_CONFIGURED|QUORUM_MISMATCH/.test(String(a.error||"")))return "BLOCKED";
  if(a.allRequiredOnline===true&&states.every(x=>["ONLINE","PASS","RUNNING"].includes(x)))return "READY";
  if(!a.ok)return "DEGRADED";
  if(a.allRequiredOnline===false)return "DEGRADED";
  if(states.some(x=>["ONLINE","PASS","RUNNING"].includes(x))&&states.some(x=>!["ONLINE","PASS","RUNNING"].includes(x)))return "DEGRADED";
  if(a.ok&&states.every(x=>["UNKNOWN","ONLINE","PASS","RUNNING"].includes(x)))return "WARMING";
  return "DEGRADED";}

function providerIcon(state=""){const s=String(state||"").toUpperCase();if(["ONLINE","PASS","RUNNING"].includes(s))return "✅";if(s==="UNKNOWN"||s==="WARMING")return "⚠️";return "❌";}
function aiAccuracy(x={}){const v=x?.directionalAccuracy,s=Number(x?.samples||0);return s>0&&v!==null&&v!==undefined&&Number.isFinite(Number(v))?`${fmt(Number(v)*100,1)}% • n=${s}`:"—";}

// ─── STATUS BADGE ─────────────────────────────────────────────────────────────
function bybitStatusLine(s,aiState){
  if(s.mode!=="LIVE")return `Status: PAPER ⚪`;
  if(aiState==="BLOCKED")return `Status: ❌ BLOCKED — AI_QUORUM_FAILED`;
  if(aiState==="DEGRADED")return `Status: ⚠️ DEGRADED — AI_PROVIDER_ISSUE`;
  if(aiState==="WARMING")return `Status: ⚠️ WARMING — AI_INITIALIZING`;
  if(s.positions.length===0&&!(s.state?.lastScan?.best))return `Status: 🟢 READY — IDLE (no candidate)`;
  return `Status: 🟢 READY`;}

// ─── SCAN SUMMARY ─────────────────────────────────────────────────────────────
function scanSummary(state){
  const sc=state?.lastScan||{};
  if(!sc.scannedAt)return "—";
  const best=sc.best,coins=Number(sc.universe||0),qual=Number(sc.qualified||0);
  if(!best)return `${coins} coins • 0 candidates`;
  return `${coins} coins • ${qual} candidate${qual!==1?"s":""} • Best: ${best.symbol} ${best.side} score ${best.score}`;}

// ─── OPEN RISK ────────────────────────────────────────────────────────────────
function openRiskPct(state,equity){
  const plans=state?.openPlans||{},eq=Number(equity||0);
  if(!(eq>0))return null;
  let risk=0;
  for(const p of Object.values(plans)){const r=Number(p?.riskUsd||0);if(r>0)risk+=r;}
  return eq>0?risk/eq*100:null;}

// ─── BYBIT DASHBOARD ──────────────────────────────────────────────────────────
function bybitDash(s){
  const aiState=aiHealthState(s.ai),ps=s.ai?.providers||{},
    riskPct=openRiskPct(s.state,s.account.equity),
    riskLine=riskPct!=null?`⚠️ Open risk: ${fmt(riskPct,1)}%`:null;
  return [
    `🪙 BYBIT — ${s.mode==="LIVE"?"LIVE ✅":"PAPER ⚪"}`,
    `${BYBIT_AUTO_VERSION}`,
    "",
    `💰 Equity: $${fmt(s.account.equity)}`,
    `💵 Available: $${fmt(s.account.available)}`,
    `📊 Positions: ${s.positions.length}  •  Today P&L: ${money(s.state?.realizedUsd||0)}`,
    riskLine,
    "",
    `🧠 AI: Claude ${providerIcon(ps.claude?.state)} | Codex ${providerIcon(ps.codex?.state)}`,
    `🔍 Scan: ${scanSummary(s.state)}`,
    "",
    bybitStatusLine(s,aiState)
  ].filter(x=>x!=null).join("\n");}

// ─── BYBIT POSITIONS ──────────────────────────────────────────────────────────
function bybitPositions(s){
  if(!s.positions.length)return "📌 POSITIONS — LIVE\n\n⚪ Không có vị thế LIVE.";
  return ["📌 POSITIONS — LIVE","",...s.positions.map(x=>{
    const p=s.state?.openPlans?.[x.symbol]||{};
    const ph=p.managementPhase;
    const phaseBadge=ph&&ph!=="INITIAL"&&ph!=="HOLD"?` • ${ph}`:"";
    return [
      `${String(x.side).toLowerCase()==="buy"?"🟢":"🔴"} ${x.symbol} ${String(x.side).toUpperCase()}${phaseBadge}`,
      `   Entry ${px(x.avgPrice||p.entry)}  →  Mark ${px(x.markPrice)}`,
      `   SL ${px(x.stopLoss||p.managedSl||p.sl)}  •  TP ${px(x.takeProfit||p.tp)}`,
      `   PnL ${money(x.unrealisedPnl)}  •  Risk $${fmt(p.riskUsd)}`
    ].join("\n");})].join("\n\n");}

// ─── BYBIT AI ─────────────────────────────────────────────────────────────────
function bybitAi(s){
  const a=s.ai||{},ps=a.providers||{},m=s.learning?.summary||{},h=aiHealthState(a);
  const claudeState=String(ps.claude?.state||"—").toUpperCase();
  const codexState=String(ps.codex?.state||"—").toUpperCase();
  const lines=[
    "🧠 AI COUNCIL — BYBIT",
    "",
    `Claude: ${providerIcon(claudeState)} ${claudeState}`,
    `  Accuracy: ${aiAccuracy(m.providers?.claude)}`,
    "",
    `Codex:  ${providerIcon(codexState)} ${codexState}`,
    `  Accuracy: ${aiAccuracy(m.providers?.codex)}`,
    "",
    `Quorum: 2/2 ${h==="READY"?"✅":"❌"}  Fail-closed`,
  ];
  if(s.state?.lastAiReview)lines.push(`Last review: ${s.state.lastAiReview.symbol} ${s.state.lastAiReview.side} — ${s.state.lastAiReview.reason||"—"}`);
  lines.push("","Accuracy = net outcome sau phí • — = chưa đủ mẫu");
  return lines.join("\n");}

// ─── BYBIT SCAN ───────────────────────────────────────────────────────────────
function bybitScan(s){
  const sc=s.state?.lastScan||{};
  if(!sc.scannedAt)return "🔍 SCAN\n\n⚪ Chưa có dữ liệu scan.";
  const best=sc.best,lines=[
    "🔍 SCAN",
    "",
    `Universe: ${sc.universe||"—"}`,
    `Analyzed: ${sc.analyzed||"—"}`,
    `Qualified: ${sc.qualified||0}`,
  ];
  if(best){lines.push("","Best candidate:",`${best.side==="Buy"?"🟢":"🔴"} ${best.symbol} ${best.side}`,`Score: ${best.score}  •  RR: ${fmt(best.rr,2)}  •  Regime: ${best.regime||"—"}`);}
  else lines.push("","⚪ Chưa có setup đạt chuẩn");
  if(sc.reason)lines.push("",`ℹ️ ${sc.reason}`);
  return lines.join("\n");}

// ─── BYBIT STATS / RUNTIME (logic unchanged, label cleanup only) ──────────────
function worstEdge(map={}){const rows=Object.entries(map).map(([k,v])=>({k,n:Number(v?.trades||0),r:Number(v?.avgNetR)})).filter(x=>x.n>=3&&Number.isFinite(x.r)).sort((a,b)=>a.r-b.r);return rows[0]||null;}
function bestEdge(map={}){const rows=Object.entries(map).map(([k,v])=>({k,n:Number(v?.trades||0),r:Number(v?.avgNetR)})).filter(x=>x.n>=3&&Number.isFinite(x.r)).sort((a,b)=>b.r-a.r);return rows[0]||null;}
function bybitStats(s){const m=s.learning?.summary||{},rec=s.recovery||{},worst=worstEdge(m.bySymbolStrategyRegime||{}),best=bestEdge(m.bySymbolStrategyRegime||{}),exchangeRows=Number(s.state?.exchangeClosedTrades||0),sample=Number(m.sampleSize||0);return ["📈 BYBIT PNL / LEARNING","💵 EXCHANGE — TODAY",`Realized ${money(s.state?.realizedUsd||0)} • Closed rows ${exchangeRows} • Loss streak ${Number(s.state?.lossStreak||0)}`,"🧠 CANONICAL BOT LEARNING — ALL RETAINED V2",`Matched lifecycle outcomes ${sample} • W ${Number(m.wins||0)} / L ${Number(m.losses||0)} / BE ${Number(m.breakevens||0)}`,`Net win ${Number.isFinite(Number(m.netWinRate))?fmt(Number(m.netWinRate)*100,1)+"%":"—"} • Avg net R ${fmt(m.avgNetR,2)} • Sum net R ${fmt(m.sumNetR,2)}`,`Recovery ${rec?.at?`30d rows ${Number(rec.exchangeRows||0)} • recovered ${Number(rec.recoveredLifecycles||0)} • unattributed ${Number(rec.unattributedRows||0)}`:"chưa chạy"}`,worst?`🔻 Weak edge ${worst.k} • ${worst.n} trades • ${fmt(worst.r,2)}R`:"🔻 Weak edge: chưa đủ mẫu",best?`🔺 Strong edge ${best.k} • ${best.n} trades • ${fmt(best.r,2)}R`:"🔺 Strong edge: chưa đủ mẫu","Adaptive threshold / exit profile đã dùng toàn bộ canonical outcomes theo symbol + strategy + regime.",exchangeRows>0&&sample===0?"⚠️ Exchange có lịch sử nhưng chưa có lifecycle đủ metadata; không gán bừa vào AI/strategy.":"✅ Learning chỉ nhận outcome có NET PnL + risk/lifecycle hợp lệ.","Auto-promote OFF • history recovery không được tự đổi strategy."].join("\n");}
function bybitRuntime(s){const i=bybitIntegrityState(s);return ["⚙️ AUTO RUNTIME",`${BYBIT_AUTO_VERSION} • ${s.mode}`,"Adaptive Edge Engine • ACTIVE","Continuous Capital Allocation • Daily target OFF","Smart CUT ON",`Balance $${fmt(s.account.wallet)} • Equity $${fmt(s.account.equity)} • Available $${fmt(s.account.available)}`,`Initial Margin $${fmt(s.account.initialMargin)}`,`Leverage cap ${s.cfg.maxLeverage}x`,`Learning ${s.learning?.dataIntegrityVersion||"—"} • ${i.ok?"SYNC":"REVIEW"}`,`Last recovery ${s.recovery?.at||"—"}`,`Last AI ${s.state?.lastAiReview?.at||"—"}`,`Last quote ${s.state?.lastPostAiQuote?.at||"—"}`].join("\n");}

// ─── HUB ROOT TEXT ────────────────────────────────────────────────────────────
const hubText=e=>{const fxMode=forexAutoConfig(e).execution.liveEnabled?"LIVE ✅":"PAPER ⚪",byMode=bybitExecutionMode(e)==="LIVE"?"LIVE ✅":"PAPER ⚪";return [
  "🏠 TRADING HUB","",
  `🪙 Bybit  ${byMode}`,
  `💱 Forex  ${fxMode}`,
  `🟣 Meme   PAPER ⚪`
].join("\n");};

// ─── MEME (unchanged) ─────────────────────────────────────────────────────────
function paperDash(s){return ["🟣 MEME AUTO PAPER",`${MEME_AUTO_VERSION} • ${MEME_AUTO_MODE}`,"🔒 NO WALLET • NO SIGNING • NO EXECUTION • NO REAL BUY/SELL",`💰 Paper Equity $${fmt(s.equityUsd)} • Cash $${fmt(s.cashUsd)}`,`📌 Positions ${Object.keys(s.positions||{}).length} • Closed ${s.trades||0}`,`📈 Realized ${money(s.realizedUsd||0)} • Win ${s.trades?fmt((s.wins||0)/s.trades*100,1)+"%":"—"}`,`🔎 Scan ${s.lastScan?.evaluated??0} • Eligible ${s.lastScan?.eligible??0}`,`📡 ${s.lastScan?.data||"DexScreener FREE + Solana RPC FREE"} + Jupiter FREE quote`,`🕒 ${s.lastScan?.at||"chưa scan"}`].join("\n");}
function paperPositions(s){const a=Object.values(s.positions||{});return ["📌 MEME PAPER POSITIONS",...(a.length?a.map(p=>`🟣 ${p.symbol} • $${fmt(p.costUsd)}\nE ${px(p.entryPrice)} • Mark ${px(p.markPrice)}\nPnL ${money(p.unrealizedUsd||0)} • Score ${p.score} • ${p.regime}`):["⚪ Chưa có paper position."])].join("\n\n");}
function watch(s){return ["👀 MEME WATCH",...(s.watch?.length?s.watch.slice(0,8).map((x,i)=>`${i+1}. ${x.symbol} • ${x.score} • ${x.regime}\nLiq $${Math.round(x.liquidityUsd)} • 5m ${fmt(x.priceChangeM5,1)}% • Sell ${x.sellRoute?"OK":"NO"} • Top10 ${fmt(x.onchain?.top10Pct,1)}%`):["Chưa có candidate."])].join("\n");}
function safety(){const d=MEME_AUTO_DESIGN;return ["🛡️ MEME SAFETY",`Liquidity ≥$${Math.round(d.hardSafety.minLiquidityUsd/1000)}k`,`Mint authority NULL • Freeze authority NULL`,`Top10 holder ≤${d.hardSafety.maxTop10HolderPct}%`,`Jupiter SELL route bắt buộc • impact ≤${d.executionDesign.hardMaxPriceImpactPct}%`,`ENTRY ≥${d.qualityScore.entryScore} • PREMIUM ≥${d.qualityScore.premiumScore}`,"Blind sniper OFF • DCA OFF • martingale OFF","LIVE vẫn khóa cho tới khi holder-label/dev-insider layer và wallet phase hoàn tất."].join("\n");}
function capital(s){return ["💰 MEME CAPITAL",`Equity $${fmt(s?.equityUsd||30)}`,"< $30: max 1 position","$30–<$100: max 3 positions","≥$100: max 5 positions","Reserve ≥$5 hoặc 15%","Sizing tự giảm theo drawdown + liquidity","Spot only • leverage OFF"].join("\n");}
function trade(){const d=MEME_AUTO_DESIGN;return ["🎯 MEME ENTRY / EXIT","MOMENTUM_RETEST > FRESH_BREAKOUT > EARLY_ROTATION",`Smart CUT ~${d.exits.initialCutPctRange[0]}–${d.exits.initialCutPctRange[1]}% • hard ${d.exits.hardLossPct}%`,`TP1 +${d.exits.tp1.gainPct}% sell ${d.exits.tp1.sellPct}%`,`TP2 +${d.exits.tp2.gainPct}% sell ${d.exits.tp2.sellPct}%`,`Runner + trailing`,`Bad regime = NO_ENTRY`].join("\n");}
function learning(){const d=MEME_AUTO_DESIGN;return ["📚 MEME LEARNING","Paper outcomes: token + regime + setup + liquidity","Metrics: net PnL/R • MFE/MAE • hold • impact • fees • exit reason",`Score bounds ${d.qualityScore.learningBounds.minEntryScore}–${d.qualityScore.learningBounds.maxEntryScore}`,`No influence before ${d.qualityScore.learningBounds.minClosedSamples} closed samples`,`Auto-promote OFF`].join("\n");}

// ─── FETCH HANDLER ────────────────────────────────────────────────────────────
export default {async fetch(req,e){
  const u=new URL(req.url);
  if(u.pathname==="/meme-auto/design")return json(getMemeAutoDesignStatus());
  if(u.pathname==="/auto-hub/status"){
    const l=await getBybitLearningState(e),st=await getBybitAutoV1State(e),i=bybitIntegrityState({learning:l,state:st});
    return json({ok:true,service:"UNIFIED_TRADING_HUB",branches:["BYBIT","FOREX","MEME"],bybit:{version:BYBIT_AUTO_VERSION,mode:bybitExecutionMode(e),executionAuthority:true,learningAuthority:l.outcomeAuthority,dataIntegrityVersion:l.dataIntegrityVersion,integrity:i.status},forex:{version:FOREX_AUTO_VERSION,mode:forexAutoConfig(e).execution.liveEnabled?"LIVE":"PAPER",mt5Windows:true,ai:"CODEX_CLAUDE_2AI",canonicalHandler:"forex-telegram-hub"},meme:{version:MEME_AUTO_VERSION,mode:MEME_AUTO_MODE,paper:true,executionEnabled:false,walletConnected:false,signingEnabled:false},continuousTrading:true,dailyTarget:false});}
  if(u.pathname==="/telegram/webhook"&&req.method==="POST"){
    let x;try{x=await req.json();}catch{return json({ok:false,error:"BAD_JSON"},400);}
    if(!auth(x,e))return json({ok:false,error:"FORBIDDEN"},403);
    const cb=String(x?.callback_query?.data||""),msg=String(x?.message?.text||""),id=x?.callback_query?.message?.chat?.id??x?.message?.chat?.id??e.TELEGRAM_CHAT_ID;
    if(cb==="hub:home"||(!cb&&["/start","/auto","/hub"].includes(msg))){await send(e,id,hubText(e),rootMenu());return json({ok:true,branch:"HOME"});}
    if(cb==="hub:forex"||cb.startsWith("forex:"))return null;
    if(cb==="hub:meme"||cb.startsWith("meme:")){
      let s=cb==="meme:scan"?(await runMemePaperCycle(e)).state:await getMemePaperState(e),t=paperDash(s);
      if(cb==="meme:positions")t=paperPositions(s);
      else if(cb==="meme:watch")t=watch(s);
      else if(cb==="meme:pnl")t=["📈 MEME PAPER PNL",`Equity $${fmt(s.equityUsd)} • Realized ${money(s.realizedUsd)}`,`Trades ${s.trades||0} • W ${s.wins||0} / L ${s.losses||0}`].join("\n");
      else if(cb==="meme:safety")t=safety();
      else if(cb==="meme:capital")t=capital(s);
      else if(cb==="meme:trade")t=trade();
      else if(cb==="meme:learning")t=learning();
      await send(e,id,t,memeMenu());
      return json({ok:true,branch:"MEME",paper:true,noWallet:true,noSigning:true,noExecution:true});}
    let s=await snap(e);
    let t=bybitDash(s);
    if(cb==="auto:positions")t=bybitPositions(s);
    else if(cb==="auto:ai")t=bybitAi(s);
    else if(cb==="auto:scan")t=bybitScan(s);
    else if(cb==="auto:stats"){
      const stale=!s.recovery?.at||Date.now()-Date.parse(s.recovery.at)>6*3600000;
      if(stale){try{await recoverBybitCanonicalLearning(e,s.state,{days:30});s=await snap(e);}catch(err){s.recovery={...(s.recovery||{}),error:String(err?.message||err),at:new Date().toISOString()};}}t=bybitStats(s);}
    else if(cb==="auto:runtime")t=bybitRuntime(s);
    else if(["auto:risk","auto:history","auto:integrity"].includes(cb))t=bybitDash(s);
    await send(e,id,t,bybitMenu());
    return json({ok:true,branch:"BYBIT",version:BYBIT_AUTO_VERSION,mode:s.mode,integrity:bybitIntegrityState(s).status,aiHealth:aiHealthState(s.ai)});}
  if(u.pathname==="/"||u.pathname==="/hub"||u.pathname==="/auto-hub")return json({ok:true,service:"UNIFIED_TRADING_HUB",telegram:"/telegram/webhook",bybit:BYBIT_AUTO_VERSION,forex:FOREX_AUTO_VERSION,meme:MEME_AUTO_VERSION});
  return null;}};
