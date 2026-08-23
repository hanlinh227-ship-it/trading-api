#!/usr/bin/env python3
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
N=ROOT/'cloudflare-worker/v11/native-runtime.js'
H=ROOT/'cloudflare-worker/hub-v11.js'

n=N.read_text(encoding='utf-8')
if 'export async function analyzeSingleSymbolV11' not in n:
    marker='async function lifecycleQuote(symbol,market,env){return getLiveQuote(symbol,market,env);}'
    insert="""export async function analyzeSingleSymbolV11(env,market,symbol){
 if(isWeekendClosed(market))return {ok:false,status:'MARKET_CLOSED_WEEKEND',market,symbol};
 try{
  const [analysis,quote]=await Promise.all([engine(`/analyze?symbol=${encodeURIComponent(symbol)}`,env),getLiveQuote(symbol,market,env)]);
  if(!analysis)throw new Error('V11_ANALYSIS_UNAVAILABLE');
  if(!(Number(quote?.price)>0)||quote?.fresh!==true)throw new Error('V11_QUOTE_NOT_VERIFIED_FRESH');
  const upstreamStatus=String(analysis?.status||'').toUpperCase(),base=normalizeCandidate(analysis,quote),eligible=evaluateEntryEligibility(symbol,market,upstreamStatus,base,quote),c={...base,entry:Number(quote.price),price:Number(quote.price)},plan=buildEntryPlan(market,c);
  let gate={pass:false,reasons:['NOT_ENTRY_READY'],softWarnings:[]};
  if(eligible.ready&&plan.ok&&plan.executable){const candidate={...c,symbol:plan.symbol,entry:Number(quote.price),sl:plan.sl,tp:plan.tp,rr:plan.rr,setup:plan.setup,upstreamStatus,quote,symbolPolicy:eligible.policy,promotionMode:eligible.mode};gate=evaluateMarketCandidate(market,candidate);}
  const marketReady=Boolean(eligible.ready&&plan.ok&&plan.executable&&gate.pass);
  return {ok:true,status:marketReady?'MARKET':'WATCH',market,symbol,upstreamStatus,quote,eligibility:eligible,plan,gate,marketReady,qualityScore:base.qualityScore,side:String(plan?.side||base?.side||'').toUpperCase(),analysis};
 }catch(e){return {ok:false,status:'ERROR',market,symbol,error:String(e?.message||e)};}
}
"""
    if marker not in n: raise SystemExit('native marker missing')
    n=n.replace(marker,insert+marker)
    N.write_text(n,encoding='utf-8')

h=H.read_text(encoding='utf-8')
h=h.replace("import {scanMarketV11,scheduledNativeV11} from './v11/native-runtime.js';","import {scanMarketV11,scheduledNativeV11,analyzeSingleSymbolV11} from './v11/native-runtime.js';")

if 'function distanceText(' not in h:
    marker="const pnlText=p=>p==null?'⚪ —':p>=0?`🟢 +${p.toFixed(2)}%`:`🔴 ${p.toFixed(2)}%`;"
    add=r"""
function distanceText(m,e,sl,tp){const E=Number(e),S=Number(sl),T=Number(tp);if(!(E>0)||!(S>0)||!(T>0))return 'SL — • TP —';const sd=Math.abs(E-S),td=Math.abs(T-E);if(m==='forex'){const pip=E>=20?.01:.0001;return `SL ${fmt(S)} (${(sd/pip).toFixed(1)} pip) • TP ${fmt(T)} (${(td/pip).toFixed(1)} pip)`;}if(m==='metal')return `SL ${fmt(S)} ($${sd.toFixed(2)}) • TP ${fmt(T)} ($${td.toFixed(2)})`;if(m==='index')return `SL ${fmt(S)} (${sd.toFixed(1)} điểm) • TP ${fmt(T)} (${td.toFixed(1)} điểm)`;return `SL ${fmt(S)} (${(sd/E*100).toFixed(2)}%) • TP ${fmt(T)} (${(td/E*100).toFixed(2)}%)`;}
"""
    if marker not in h: raise SystemExit('pnl marker missing')
    h=h.replace(marker,marker+add)

h=re.sub(r"const line=x=>\{.*?\};\nasync function send", "const line=x=>{const c=x.candidate||{},p=pnlPct(c.side,c.entry,x.currentPrice),q=x.currentQuote||{},age=Number.isFinite(Number(q.quoteAgeSec))?`${Math.round(Number(q.quoteAgeSec))}s`:'—';return `${c.side==='LONG'?'🟢':'🔴'} ${x.symbol} ${c.side==='LONG'?'BUY':'SELL'} | ${pnlText(p)}\\nE ${fmt(c.entry)} • N ${fmt(x.currentPrice)}\\n${distanceText(x.market,c.entry,c.sl,c.tp)}\\n📡 ${q.source||'NO LIVE'} ${age} • AI CUT ${x.lastAiCutVotes||0}/5`;};\nasync function send", h, flags=re.S)

h=re.sub(r"function hunterText\(r\)\{.*?\}\nfunction watchRows", "function hunterText(r){if(!r?.best)return `🧠 5 AI MARKET\\n⚪ Chưa có entry đủ chuẩn\\n${r?.reason||r?.status||'NO_CANDIDATE'}`;const x=r.best,c=x.candidate||{},ai=x.ai||{};return [`🧠 5 AI MARKET`,`${c.side==='LONG'?'🟢 BUY':'🔴 SELL'} ${x.symbol} • ${String(x.market||'').toUpperCase()}`,`E ${fmt(c.entry)}`,distanceText(x.market,c.entry,c.sl,c.tp),`AI ${Number(x.consensusCount||0)}/5 ${x.consensus?'✅':'⚠️'} • C:${aiText(ai.claude)} • X:${aiText(ai.codex)}`,`D:${aiText(ai.deepseek)} • Q:${aiText(ai.qwen)} • O:${aiText(ai.openrouter)}`].join('\\n');}\nfunction watchRows", h, flags=re.S)

new_detail=r"""async function symbolDetailText(env,m,s){const x=await analyzeSingleSymbolV11(env,m,s),q=x?.quote||{},live=q?.fresh===true&&Number(q?.price)>0?Number(q.price):null,age=Number(q?.quoteAgeSec),cross=Number(q?.crossSourceCount||0),src=q?.source||'NO_FRESH_LIVE';const L=[`🎯 ${displaySymbol(s,m)} • ${String(m).toUpperCase()}`,`💵 LIVE ${fmt(live)} • ${src}${Number.isFinite(age)?` • ${Math.round(age)}s`:''}${cross?` • x${cross}`:''}`];if(!x?.ok||!live){L.push(`⛔ ${x?.error||x?.status||'Không có giá LIVE đủ mới'}`);return L.join('\n');}const p=x.plan||{},side=String(p.side||x.side||'').toUpperCase(),ready=x.marketReady===true,sideText=side==='LONG'?'🟢 BUY':side==='SHORT'?'🔴 SELL':'⚪ WAIT';L.push(`${ready?'⚡':'👀'} ${sideText} ${ready?'MARKET':'WATCH'}${Number.isFinite(Number(x.qualityScore))?` • Q ${Math.round(Number(x.qualityScore))}/100`:''}`);if(p.entry&&p.sl&&p.tp){L.push(`E ${fmt(p.entry)}`,distanceText(m,p.entry,p.sl,p.tp));}if(p.setup)L.push(`🧠 ${p.setup}${p.symbolPolicy?.backtestEligible?' • 4M calibrated':''}`);if(!ready)L.push(`↳ ${x.eligibility?.reason||p.reason||(x.gate?.reasons||[]).join('|')||'WAIT'}`);L.push('🔄 REFRESH LIVE = đánh giá lại bằng cùng engine phát lệnh.');return L.join('\n');}
"""
h,repl=re.subn(r"async function symbolDetailText\(env,m,s\)\{.*?\}\nfunction symbolsPageText",new_detail+"function symbolsPageText",h,flags=re.S)
if repl!=1: raise SystemExit(f'symbolDetail replacement count={repl}')

H.write_text(h,encoding='utf-8')
print('PATCH_V11_HUB_CONSISTENCY=PASS')
