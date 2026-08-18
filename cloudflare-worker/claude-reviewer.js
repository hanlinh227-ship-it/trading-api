const API_URL="https://api.anthropic.com/v1/messages";
const DEFAULT_MODEL="claude-sonnet-4-20250514";
const STATE_KEY="v771820:claude:last";
const BUDGET_KEY="v771820:claude:budget";
const RELEASE_KEY="v771820:claude:release";
const HEALTH_KEY="v771817:health:last";
const ERROR_SIG_KEY="v771820:claude:error_sig";
const REPO="hanlinh227-ship-it/trading-api";
const RAW_BASE=`https://raw.githubusercontent.com/${REPO}/main/`;
const GH_API=`https://api.github.com/repos/${REPO}`;
const CRITICAL_FILES=[
  "cloudflare-worker/index.js",
  "cloudflare-worker/hub-v77171.js",
  "cloudflare-worker/system-health.js",
  "cloudflare-worker/hyro-runtime.js",
  "cloudflare-worker/hyro-execution.js",
  "cloudflare-worker/hyro-position-review.js"
];

const now=()=>Date.now();
const num=(v,d=0)=>{const n=Number(v);return Number.isFinite(n)?n:d;};
async function kvGet(env,key,fallback=null){try{return await env.TRADING_STATE?.get(key,"json")??fallback;}catch{return fallback;}}
async function kvPut(env,key,value,ttl){try{if(env.TRADING_STATE)await env.TRADING_STATE.put(key,JSON.stringify(value),ttl?{expirationTtl:ttl}:undefined);}catch{}}
function dayKey(){return new Date().toISOString().slice(0,10);}
function clampText(s,max){s=String(s||"");return s.length>max?s.slice(0,max)+"\n...[truncated]":s;}
function safeHealth(h){if(!h||typeof h!=="object")return null;return {ok:!!h.ok,version:h.version||null,errors:num(h.errors),warnings:num(h.warnings),signature:h.signature||null,issues:(h.issues||[]).filter(x=>x?.level!=="OK").slice(0,12).map(x=>({level:x.level,code:x.code,msg:x.msg})),account:h.account?{configured:!!h.account.configured,connected:!!h.account.connected,equity:num(h.account.equity),positions:num(h.account.positions),orders:num(h.account.orders),autoRequested:!!h.account.autoRequested,paused:!!h.account.paused,runtimeReason:h.account.runtimeReason||null}:null};}
async function tg(env,text){if(!env.TELEGRAM_BOT_TOKEN||!env.TELEGRAM_CHAT_ID)return false;try{const r=await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`,{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({chat_id:env.TELEGRAM_CHAT_ID,text,disable_web_page_preview:true})});const p=await r.json().catch(()=>null);return !!p?.ok;}catch{return false;}}
async function fetchText(url,timeoutMs=6500){const c=new AbortController(),id=setTimeout(()=>c.abort("timeout"),timeoutMs);try{const r=await fetch(url,{headers:{"user-agent":"trading-v77-claude-reviewer","accept":"text/plain,application/json"},signal:c.signal});if(!r.ok)throw new Error(`HTTP ${r.status}`);return await r.text();}finally{clearTimeout(id);}}
async function githubContext(){
  let head=null,commit=null,files=[];
  try{const raw=await fetchText(`${GH_API}/commits/main`);const p=JSON.parse(raw);head=p?.sha||null;commit={sha:head,message:p?.commit?.message||null,date:p?.commit?.committer?.date||null,files:(p?.files||[]).slice(0,12).map(f=>({filename:f.filename,status:f.status,additions:f.additions,deletions:f.deletions,patch:clampText(f.patch||"",1600)}))};}catch{}
  for(const path of CRITICAL_FILES){try{const text=await fetchText(RAW_BASE+path);files.push({path,content:clampText(text,2800)});}catch(e){files.push({path,error:String(e?.message||e)});}}
  return {head,commit,files};
}
function parseClaudeJson(text){
  const raw=String(text||"").trim();
  try{return JSON.parse(raw);}catch{}
  const a=raw.indexOf("{");const b=raw.lastIndexOf("}");if(a>=0&&b>a){try{return JSON.parse(raw.slice(a,b+1));}catch{}}
  return {verdict:"WARN",confidence:0,summary:clampText(raw,1200),findings:[],tuning:[],must_fix:[]};
}
function normalizeReview(x){
  const verdict=["PASS","WARN","FAIL"].includes(String(x?.verdict||"").toUpperCase())?String(x.verdict).toUpperCase():"WARN";
  const findings=Array.isArray(x?.findings)?x.findings.slice(0,8).map(f=>({severity:String(f?.severity||"WARN").toUpperCase(),area:String(f?.area||"GENERAL"),issue:clampText(f?.issue,420),evidence:clampText(f?.evidence,420),recommendation:clampText(f?.recommendation,520)})):[];
  return {verdict,confidence:Math.max(0,Math.min(100,num(x?.confidence))),summary:clampText(x?.summary||"",900),findings,tuning:Array.isArray(x?.tuning)?x.tuning.slice(0,6).map(v=>clampText(typeof v==="string"?v:JSON.stringify(v),520)):[],must_fix:Array.isArray(x?.must_fix)?x.must_fix.slice(0,6).map(v=>clampText(typeof v==="string"?v:JSON.stringify(v),520)):[]};
}
function reviewerPrompt({version,kind,github,health}){
  const system=`You are Claude, the independent reviewer for a production trading software project. ChatGPT is the PRIMARY engineer and final decision maker. You are REVIEW-ONLY. Never assume authority to deploy, mutate KV/state, change secrets, place trades, close trades, or override risk controls. Review software quality, architecture, HUB/Telegram UX, runtime health, scanner over-filtering vs trade quality, state continuity, risk/execution safety, and code conflicts. Prefer concrete evidence from supplied code/diff. Do not recommend weakening hard risk/news/freshness/execution gates merely to increase trade frequency. Output ONLY valid compact JSON with keys: verdict (PASS|WARN|FAIL), confidence (0-100), summary, findings (array of severity,area,issue,evidence,recommendation), tuning (array), must_fix (array).`;
  const payload={version,kind,repo:REPO,github,health};
  return {system,user:`Review this production snapshot. Detect real bugs/conflicts first, then high-value tuning. Do not expose or request secrets.\n${JSON.stringify(payload)}`};
}
async function budgetCheck(env,{force=false}={}){
  const dailyLimit=Math.max(1,Math.min(20,num(env.CLAUDE_REVIEW_DAILY_LIMIT,4))),cooldownMin=Math.max(5,Math.min(720,num(env.CLAUDE_REVIEW_COOLDOWN_MIN,45))),day=dayKey();
  let b=await kvGet(env,BUDGET_KEY,{day,count:0,lastAt:0,inputTokens:0,outputTokens:0});if(b.day!==day)b={day,count:0,lastAt:0,inputTokens:0,outputTokens:0};
  if(b.count>=dailyLimit)return {ok:false,reason:"DAILY_LIMIT",budget:b,dailyLimit,cooldownMin};
  if(!force&&b.lastAt&&now()-Number(b.lastAt)<cooldownMin*60000)return {ok:false,reason:"COOLDOWN",budget:b,dailyLimit,cooldownMin};
  return {ok:true,budget:b,dailyLimit,cooldownMin};
}
async function saveBudget(env,b,usage={}){const next={...b,day:dayKey(),count:num(b.count)+1,lastAt:now(),inputTokens:num(b.inputTokens)+num(usage.input_tokens),outputTokens:num(b.outputTokens)+num(usage.output_tokens)};await kvPut(env,BUDGET_KEY,next,172800);return next;}
async function callClaude(env,{version,kind,github,health}){
  if(!env.ANTHROPIC_API_KEY)throw new Error("ANTHROPIC_API_KEY missing");
  const model=String(env.ANTHROPIC_REVIEW_MODEL||DEFAULT_MODEL),maxTokens=Math.max(400,Math.min(2000,num(env.ANTHROPIC_REVIEW_MAX_TOKENS,1200))),p=reviewerPrompt({version,kind,github,health});
  const r=await fetch(API_URL,{method:"POST",headers:{"content-type":"application/json","x-api-key":env.ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},body:JSON.stringify({model,max_tokens:maxTokens,temperature:0,system:p.system,messages:[{role:"user",content:p.user}]})});
  const body=await r.json().catch(()=>null);if(!r.ok)throw new Error(`Anthropic ${r.status}: ${body?.error?.message||"request failed"}`);
  const text=(body?.content||[]).filter(x=>x?.type==="text").map(x=>x.text).join("\n");return {model,id:body?.id||null,stopReason:body?.stop_reason||null,usage:body?.usage||{},review:normalizeReview(parseClaudeJson(text))};
}
export function formatClaudeReviewText(state){
  if(!state)return "🧠 Claude Reviewer • Chưa có review";
  if(state.skipped)return `🧠 Claude Reviewer • SKIP\n${state.reason||"—"}`;
  if(state.error)return `🧠 Claude Reviewer • ERROR\n${state.error}`;
  const r=state.review||{},icon=r.verdict==="PASS"?"✅":r.verdict==="FAIL"?"❌":"⚠️",must=(r.must_fix||[]).slice(0,3),find=(r.findings||[]).slice(0,3).map(x=>`${x.severity==="FAIL"||x.severity==="ERROR"?"❌":"⚠️"} ${x.area}: ${x.issue}`);
  return [ `${icon} Claude Reviewer • ${r.verdict||"WARN"} ${r.confidence||0}%`, `${state.version||"—"} • ${state.kind||"REVIEW"} • ${state.model||"—"}`, r.summary||"", ...find, ...(must.length?["🔧 Must-fix:",...must.map(x=>`• ${x}`)]:[]), `Usage in/out: ${num(state.usage?.input_tokens)}/${num(state.usage?.output_tokens)}` ].filter(Boolean).join("\n").slice(0,3900);
}
export async function runClaudeReview(env,{version="UNKNOWN",kind="MANUAL",force=false,notify=true,health=null}={}){
  const startedAt=now();if(!env.ANTHROPIC_API_KEY){const out={ok:false,skipped:true,reason:"ANTHROPIC_API_KEY_MISSING",version,kind,startedAt,finishedAt:now()};await kvPut(env,STATE_KEY,out);return out;}
  const gate=await budgetCheck(env,{force});if(!gate.ok){const out={ok:true,skipped:true,reason:gate.reason,version,kind,budget:gate.budget,startedAt,finishedAt:now()};return out;}
  try{
    const h=safeHealth(health||await kvGet(env,HEALTH_KEY,null)),github=await githubContext(),resp=await callClaude(env,{version,kind,github,health:h}),budget=await saveBudget(env,gate.budget,resp.usage),out={ok:true,version,kind,startedAt,finishedAt:now(),githubHead:github.head,model:resp.model,messageId:resp.id,stopReason:resp.stopReason,usage:resp.usage,budget,review:resp.review};
    await kvPut(env,STATE_KEY,out,1209600);if(notify)await tg(env,formatClaudeReviewText(out));return out;
  }catch(e){const out={ok:false,version,kind,startedAt,finishedAt:now(),error:String(e?.message||e)};await kvPut(env,STATE_KEY,out,1209600);if(notify)await tg(env,formatClaudeReviewText(out));return out;}
}
export async function runClaudeAutoReview(env,{version="UNKNOWN",health=null}={}){
  if(!env.ANTHROPIC_API_KEY)return {ok:false,skipped:true,reason:"ANTHROPIC_API_KEY_MISSING"};
  const rel=await kvGet(env,RELEASE_KEY,null);if(rel?.version!==version){const r=await runClaudeReview(env,{version,kind:"RELEASE_REVIEW",force:false,notify:true,health});if(r.ok&&!r.skipped)await kvPut(env,RELEASE_KEY,{version,at:now(),verdict:r.review?.verdict||null},2592000);return r;}
  const h=safeHealth(health||await kvGet(env,HEALTH_KEY,null));if(h?.errors>0){const sig=String(h.signature||"ERROR"),old=await kvGet(env,ERROR_SIG_KEY,null);if(old?.signature!==sig){const r=await runClaudeReview(env,{version,kind:"HEALTH_INCIDENT_REVIEW",force:false,notify:true,health:h});if(r.ok&&!r.skipped)await kvPut(env,ERROR_SIG_KEY,{signature:sig,at:now()},604800);return r;}}
  return {ok:true,skipped:true,reason:"NO_TRIGGER"};
}
export async function getClaudeReviewState(env){return kvGet(env,STATE_KEY,null);}
export async function getClaudeReviewerStatus(env){const [last,budget,release]=await Promise.all([kvGet(env,STATE_KEY,null),kvGet(env,BUDGET_KEY,null),kvGet(env,RELEASE_KEY,null)]);return {configured:!!env.ANTHROPIC_API_KEY,model:String(env.ANTHROPIC_REVIEW_MODEL||DEFAULT_MODEL),dailyLimit:Math.max(1,Math.min(20,num(env.CLAUDE_REVIEW_DAILY_LIMIT,4))),cooldownMin:Math.max(5,Math.min(720,num(env.CLAUDE_REVIEW_COOLDOWN_MIN,45))),last,budget,release,permissions:{trade:false,closePosition:false,deploy:false,kvMutationExceptOwnReviewState:true,reviewOnly:true}};}
