import {applyAdaptiveTuning,getAdaptiveTuningState} from "./adaptive-tuning.js";

const KEY="v771823:dual_ai:intervention";
const MODEL="claude-sonnet-5";
const REPO="hanlinh227-ship-it/trading-api";
const FILES=["cloudflare-worker/index.js","cloudflare-worker/hub-v77171.js","cloudflare-worker/engine-v77168.js","cloudflare-worker/hyro-scanner.js","cloudflare-worker/hyro-runtime.js","cloudflare-worker/hyro-execution.js","cloudflare-worker/hyro-market-context.js","cloudflare-worker/hyro-portfolio-guard.js","cloudflare-worker/hyro-position-manager.js","cloudflare-worker/hyro-position-review.js","cloudflare-worker/system-health.js","cloudflare-worker/claude-reviewer.js"];
const now=()=>Date.now();
const num=v=>{const n=Number(v);return Number.isFinite(n)?n:0;};
const cut=(s,n=1600)=>String(s||"").slice(0,n);
async function kvGet(env,k,f=null){try{return await env.TRADING_STATE?.get(k,"json")??f;}catch{return f;}}
async function kvPut(env,k,v,ttl=2592000){try{await env.TRADING_STATE?.put(k,JSON.stringify(v),{expirationTtl:ttl});}catch{}}
async function tg(env,text){if(!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID)return;try{await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true})});}catch{}}
async function ft(url){const c=new AbortController(),id=setTimeout(()=>c.abort(),6500);try{const r=await fetch(url,{headers:{"user-agent":"trading-dual-ai-v771823"},signal:c.signal});if(!r.ok)throw new Error(`HTTP ${r.status}`);return await r.text();}finally{clearTimeout(id);}}
async function snapshot(env){const files=[];for(const path of FILES){try{files.push({path,content:cut(await ft(`https://raw.githubusercontent.com/${REPO}/main/${path}`),1600)});}catch(e){files.push({path,error:String(e?.message||e)});}}const [health,runtime,books,tuning]=await Promise.all([kvGet(env,"v771817:health:last",null),kvGet(env,"v7718:hyro:runtime",null),kvGet(env,"v775:books",null),getAdaptiveTuningState(env)]);return {files,health:health?{ok:health.ok,errors:health.errors,warnings:health.warnings,signature:health.signature,issues:(health.issues||[]).slice(0,10)}:null,runtime:runtime?{reason:runtime.reason,executed:runtime.executed,scanSummary:runtime.scanSummary,preview:(runtime.preview||[]).slice(0,5),dynamicRisk:runtime.dynamicRisk}:null,books:books?{groups:Object.keys(books),updatedAt:books.updatedAt}:null,tuning};}
function parse(text){const raw=String(text||"").trim();try{return JSON.parse(raw);}catch{}const a=raw.indexOf("{"),b=raw.lastIndexOf("}");if(a>=0&&b>a){try{return JSON.parse(raw.slice(a,b+1));}catch{}}return {verdict:"WARN",summary:cut(raw,1200),findings:[],runtime_tuning:null};}
export async function ensureDualAiIntervention(env,{version="V77.18.23"}={}){
  const old=await kvGet(env,KEY,null);if(old?.completed&&old?.version===version)return old;
  if(!env.ANTHROPIC_API_KEY){const x={completed:false,version,reason:"ANTHROPIC_API_KEY_MISSING",at:now()};await kvPut(env,KEY,x,86400);return x;}
  const startedAt=now();
  try{
    const snap=await snapshot(env);
    const system=`You are Claude Sonnet 5 acting once as a bounded co-engineer for a production trading system. ChatGPT remains PRIMARY. Audit code/config conflicts, Telegram HUB UX, Signal entry discovery for Forex/Metals/Futures/Crypto, and Hyro PROP scanner/management. Your goal is more valid opportunities without loose analysis. You MAY propose and return bounded soft tuning, but must NOT alter hard news/freshness/execution-authority/structural-SL gates, Hyro daily risk caps, order authority, secrets, or deployment. Output only compact JSON: {verdict,confidence,summary,findings:[{area,issue,recommendation}],runtime_tuning:{signal:{locationTrendFit,locationRelativeFit,triggerTrendFit,triggerRelativeFit,conditionalFit,fallbackFit,forexMinRR,metalMinRR,futureMinRR,marketChaseAtr},hyro:{maxDeep,minTurnover,bMicroMin,bDistMult,bMinRR}}}. Stay conservative and use null runtime_tuning if current defaults are already better.`;
    const r=await fetch("https://api.anthropic.com/v1/messages",{method:"POST",headers:{"content-type":"application/json","x-api-key":env.ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},body:JSON.stringify({model:String(env.ANTHROPIC_REVIEW_MODEL||MODEL),max_tokens:1800,system,messages:[{role:"user",content:`Review this sanitized snapshot. Never request secrets. ${JSON.stringify(snap)}`}]})});
    const body=await r.json().catch(()=>null);if(!r.ok)throw new Error(`Anthropic ${r.status}: ${body?.error?.message||"request failed"}`);
    const text=(body?.content||[]).filter(x=>x?.type==="text").map(x=>x.text).join("\n"),review=parse(text),usage=body?.usage||{};
    const applied=review?.runtime_tuning?await applyAdaptiveTuning(env,review.runtime_tuning,{source:"CLAUDE_ONE_TIME_BOUNDED",reviewId:body?.id||null}):await getAdaptiveTuningState(env);
    const estimatedCostUsd=Number(((num(usage.input_tokens)*2+num(usage.output_tokens)*10)/1000000).toFixed(4));
    const out={completed:true,version,startedAt,finishedAt:now(),model:String(env.ANTHROPIC_REVIEW_MODEL||MODEL),messageId:body?.id||null,usage,estimatedCostUsd,verdict:String(review?.verdict||"WARN").toUpperCase(),confidence:num(review?.confidence),summary:cut(review?.summary,1600),findings:Array.isArray(review?.findings)?review.findings.slice(0,8):[],appliedTuning:applied?.values||applied,guardrails:{chatgptPrimary:true,softTuningOnly:true,trade:false,close:false,deploy:false,secrets:false,hardRiskImmutable:true}};
    await kvPut(env,KEY,out);
    await tg(env,["🧠 DUAL AI • HOÀN TẤT 1 LƯỢT",`Claude ${out.verdict} ${out.confidence||0}% | cost ~$${estimatedCostUsd.toFixed(4)}`,`Signal: ChatGPT V77.16.10 | PROP adaptive: ${out.appliedTuning?.hyro?"APPLIED":"DEFAULT"}`,"Hard risk/news/execution: giữ nguyên"].join("\n"));
    return out;
  }catch(e){const out={completed:false,version,startedAt,finishedAt:now(),error:String(e?.message||e),guardrails:{trade:false,deploy:false}};await kvPut(env,KEY,out,86400);return out;}
}
export async function getDualAiInterventionState(env){return kvGet(env,KEY,null);}
