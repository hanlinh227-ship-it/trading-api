from pathlib import Path
import re

# PROP risk: activate only after next Hyro UTC reset (07:00 Vietnam)
p=Path('cloudflare-worker/hyro-execution.js')
s=p.read_text()
marker='const RECV_WINDOW="5000";'
if 'RISK_V771822_ACTIVATES_AT' not in s:
    s=s.replace(marker,marker+'\nconst RISK_V771822_ACTIVATES_AT=Date.parse("2026-08-19T00:00:00.000Z");\nconst riskV771822Active=()=>Date.now()>=RISK_V771822_ACTIVATES_AT;',1)
pattern=r'export function hyroDynamicRiskView\(profile,t\)\{.*?\}\nfunction sideOf'
repl='''export function hyroDynamicRiskView(profile,t){
  const equity=Math.max(0,num(t?.equity)||0),legacyBase=Math.max(0,num(profile?.accountSize)||0),i=profile?.internal||{},capitalBasis=equity>0?equity:(num(t?.walletBalance)||legacyBase),dayBase=Math.max(0,num(t?.day?.dayStartEquity)||capitalBasis),dd=Math.max(0,num(t?.day?.drawdownFromPeak)||0),pnl=num(t?.day?.pnlFromDayStart)||0;
  const legacy={singlePct:pctFromLegacy(i.maxSingleWorstLossUsd,legacyBase,.02),aPct:pctFromLegacy(i.aPlusRiskUsd,legacyBase,.011),combinedPct:pctFromLegacy(i.maxCombinedOpenRiskUsd,legacyBase,.035),hardPct:pctFromLegacy(i.dailyHardStopUsd,legacyBase,.025),targetPct:.05};
  const safe=riskV771822Active()?{singlePct:.0055,aPct:.0045,combinedPct:.009,hardPct:.016,targetPct:.012}:legacy;
  let riskScale=1;if(riskV771822Active()){const ddPct=capitalBasis>0?dd/capitalBasis:0,pnlPct=dayBase>0?pnl/dayBase:0;if(ddPct>=.012)riskScale=.30;else if(ddPct>=.008)riskScale=.50;else if(ddPct>=.004)riskScale=.75;if(pnlPct>=.008)riskScale=Math.min(riskScale,.55);}
  const notionalPct=profile?.funded?.internalNotionalCapUsd!=null?pctFromLegacy(profile.funded.internalNotionalCapUsd,legacyBase,1.8):1.8,marginPct=profile?.funded?.internalMarginCapUsd!=null?pctFromLegacy(profile.funded.internalMarginCapUsd,legacyBase,.6):.6;
  return {capitalBasis,dayBase,targetUsd:dayBase*safe.targetPct,maxSingleWorstLossUsd:capitalBasis*safe.singlePct,aPlusRiskUsd:capitalBasis*safe.aPct,maxCombinedOpenRiskUsd:capitalBasis*safe.combinedPct,dailyHardStopUsd:capitalBasis*safe.hardPct,notionalCapUsd:capitalBasis*notionalPct,marginCapUsd:capitalBasis*marginPct,riskScale,policy:riskV771822Active()?"V771822_SAFE_DAILY":"LEGACY_UNTIL_UTC_RESET",activatesAt:RISK_V771822_ACTIVATES_AT,ratios:{singlePct:safe.singlePct,aPct:safe.aPct,combinedPct:safe.combinedPct,hardPct:safe.hardPct,targetPct:safe.targetPct,notionalPct,marginPct},autoScaled:true};
}
function sideOf'''
ns,n=re.subn(pattern,repl,s,flags=re.S)
if n!=1: raise SystemExit(f'hyroDynamicRiskView replace count={n}')
s=ns
old='riskBudget=Math.min(dyn.aPlusRiskUsd*riskMultiplier,dyn.maxSingleWorstLossUsd)'
if old in s:
    s=s.replace(old,'riskBudget=Math.min(dyn.aPlusRiskUsd*riskMultiplier*Number(dyn.riskScale||1),dyn.maxSingleWorstLossUsd)',1)
p.write_text(s)

# Position management: keep structural stop, reduce size/risk and bank profit earlier after reset
p=Path('cloudflare-worker/hyro-position-manager.js')
s=p.read_text()
if 'TP_POLICY_V771822_AT' not in s:
    s=s.replace('const RECV_WINDOW="5000",enc=new TextEncoder(),PREFIX="v771811:hyro:manage:";','const RECV_WINDOW="5000",enc=new TextEncoder(),PREFIX="v771811:hyro:manage:";\nconst TP_POLICY_V771822_AT=Date.parse("2026-08-19T00:00:00.000Z"),tpPolicyActive=()=>Date.now()>=TP_POLICY_V771822_AT;',1)
old='const tp1=priceAt(p.avgPrice,risk,p.side,prof.tp1R),tp2=priceAt(p.avgPrice,risk,p.side,prof.tp2R),tp3=priceAt(p.avgPrice,risk,p.side,prof.tp3R);'
new='const r1=tpPolicyActive()?Math.min(Number(prof.tp1R||1),.85):prof.tp1R,r2=tpPolicyActive()?Math.min(Number(prof.tp2R||1.8),1.60):prof.tp2R,r3=tpPolicyActive()?Math.min(Number(prof.tp3R||2.8),2.45):prof.tp3R,tp1=priceAt(p.avgPrice,risk,p.side,r1),tp2=priceAt(p.avgPrice,risk,p.side,r2),tp3=priceAt(p.avgPrice,risk,p.side,r3);'
if old not in s: raise SystemExit('position TP anchor missing')
s=s.replace(old,new,1)
s=s.replace('state.initialQty*.40','state.initialQty*(tpPolicyActive()?.45:.40)',1)
s=s.replace('state.initialQty*.35','state.initialQty*(tpPolicyActive()?.35:.35)',1)
p.write_text(s)

# Signal: modestly relax soft discovery gates only
p=Path('cloudflare-worker/engine-v77168.js')
s=p.read_text()
s=s.replace('version: "V77.16.9"','version: "V77.16.10"',1).replace('service: "Trading V77.16.9 Balanced Entry Signal Engine"','service: "Trading V77.16.10 Balanced Discovery Signal Engine"',1)
s=s.replace('deepNonCryptoCandidates: 6','deepNonCryptoCandidates: 7',1)
s=s.replace('if(mode==="TREND"&&intel.methodFit>=50&&nearEma&&continuation)','if(mode==="TREND"&&intel.methodFit>=48&&nearEma&&continuation)',1)
s=s.replace('if(mode==="RELATIVE"&&intel.methodFit>=49&&Number(context.score||0)>=6&&nearEma&&continuation)','if(mode==="RELATIVE"&&intel.methodFit>=48&&Number(context.score||0)>=6&&nearEma&&continuation)',1)
s=s.replace('if(mode==="TREND"&&intel.methodFit>=52&&impulse','if(mode==="TREND"&&intel.methodFit>=50&&impulse',1)
s=s.replace('if(mode==="RELATIVE"&&intel.methodFit>=52&&Number(context.score||0)>=6&&impulse','if(mode==="RELATIVE"&&intel.methodFit>=50&&Number(context.score||0)>=6&&impulse',1)
s=s.replace('if(side==="NEUTRAL"||Number(intel?.methodFit||0)<55)return null;','if(side==="NEUTRAL"||Number(intel?.methodFit||0)<52)return null;',1)
s=s.replace('if(Number(intel?.methodFit||0)<44)return null;','if(Number(intel?.methodFit||0)<42)return null;',1)
s=s.replace('if(type==="future")x=Math.max(x,1.50);else if(type==="metal")x=Math.max(x,mode==="MEAN_REVERSION"?1.20:1.32);','if(type==="future")x=Math.max(x,1.45);else if(type==="metal")x=Math.max(x,mode==="MEAN_REVERSION"?1.18:1.28);',1)
s=s.replace('else if(type==="forex")x=Math.max(x,mode==="MEAN_REVERSION"?1.12:1.22);','else if(type==="forex")x=Math.max(x,mode==="MEAN_REVERSION"?1.10:1.20);',1)
s=s.replace('return {pass:chase<=.65&&notExtreme','return {pass:chase<=.72&&notExtreme',1)
p.write_text(s)

# Claude temporary overnight 30-minute audit until reset; still review-only
p=Path('cloudflare-worker/claude-reviewer.js')
s=p.read_text()
if 'OVERNIGHT_REVIEW_UNTIL' not in s:
    s=s.replace('const DAILY_AUDIT_KEY="v771821:claude:daily_system_audit";','const DAILY_AUDIT_KEY="v771821:claude:daily_system_audit";\nconst OVERNIGHT_KEY="v771822:claude:overnight";\nconst OVERNIGHT_REVIEW_UNTIL=Date.parse("2026-08-19T00:00:00.000Z");\nconst OVERNIGHT_INTERVAL_MS=30*60*1000;',1)
old='const dailyLimit=Math.max(1,Math.min(20,num(env.CLAUDE_REVIEW_DAILY_LIMIT,4))),cooldownMin=Math.max(5,Math.min(720,num(env.CLAUDE_REVIEW_COOLDOWN_MIN,45))),day=dayKey();'
new='const overnight=now()<OVERNIGHT_REVIEW_UNTIL,dailyLimit=Math.max(1,Math.min(20,num(env.CLAUDE_REVIEW_DAILY_LIMIT,overnight?16:4))),cooldownMin=Math.max(5,Math.min(720,num(env.CLAUDE_REVIEW_COOLDOWN_MIN,overnight?25:45))),day=dayKey();'
if old not in s: raise SystemExit('Claude budget anchor missing')
s=s.replace(old,new,1)
trigger='  const daily=await kvGet(env,DAILY_AUDIT_KEY,null),dailyHours=Math.max(12,Math.min(72,num(env.CLAUDE_SYSTEM_AUDIT_HOURS,24)));'
insert='  if(now()<OVERNIGHT_REVIEW_UNTIL){const ov=await kvGet(env,OVERNIGHT_KEY,null);if(!ov?.at||now()-Number(ov.at)>=OVERNIGHT_INTERVAL_MS){const r=await runClaudeReview(env,{version,kind:"OVERNIGHT_30M_SYSTEM_REVIEW",force:true,notify:true,health:h});if(r.ok&&!r.skipped)await kvPut(env,OVERNIGHT_KEY,{at:now(),version,verdict:r.review?.verdict||null},172800);return r;}}\n'+trigger
if trigger not in s: raise SystemExit('Claude auto trigger anchor missing')
s=s.replace(trigger,insert,1)
p.write_text(s)

# Cleaner Hub
p=Path('cloudflare-worker/hub-v77171.js')
s=p.read_text().replace('const VERSION="V77.18.20";','const VERSION="V77.18.22";',1).replace('const SERVICE="Trading V77.18.20 ChatGPT Primary + Claude Reviewer Hub";','const SERVICE="Trading V77.18.22 Safe Risk + Balanced Discovery Hub";',1)
old='function baseKeyboard(){return {inline_keyboard:[[{text:"📡 Signal",callback_data:"signal"},{text:"🏦 Prop",callback_data:"prop"}],[{text:"👤 Cá nhân",callback_data:"personal"},{text:"🔎 Symbol",callback_data:"symbols"}],[{text:"📊 Status",callback_data:"status"},{text:"📚 Orders",callback_data:"books"}],[{text:"🧠 Claude Reviewer",callback_data:"claude:status"}]]};}'
new='function baseKeyboard(){return {inline_keyboard:[[{text:"📡 Signal",callback_data:"signal"},{text:"🏦 PROP",callback_data:"prop"}],[{text:"👤 Personal",callback_data:"personal"},{text:"🔎 Symbol",callback_data:"symbols"}],[{text:"📚 Lệnh",callback_data:"books"},{text:"🩺 Hệ thống",callback_data:"status"}],[{text:"🧠 AI Review",callback_data:"claude:status"}]]};}'
if old not in s: raise SystemExit('Hub keyboard anchor missing')
s=s.replace(old,new,1)
p.write_text(s)

# Runtime version
p=Path('cloudflare-worker/index.js')
s=p.read_text().replace('const VERSION="V77.18.20",SERVICE="Trading V77.18.20 ChatGPT Primary + Claude Reviewer";','const VERSION="V77.18.22",SERVICE="Trading V77.18.22 Safe Daily Risk + Balanced Discovery";',1).replace('const RELEASE_NAME="Claude Reviewer Integration";','const RELEASE_NAME="Safe Daily Risk + Balanced Discovery";',1)
p.write_text(s)

# Validator locks
p=Path('.github/workflows/validate-cloudflare-v77.yml')
s=p.read_text().replace("['V77.18.20','Claude Reviewer Integration'","['V77.18.22','Safe Daily Risk + Balanced Discovery'",1).replace("throw new Error('V77.18.20 index lock missing: '+x)","throw new Error('V77.18.22 index lock missing: '+x)",1).replace("hub.includes('V77.18.20')","hub.includes('V77.18.22')",1).replace("'V77.16.9'","'V77.16.10'",1).replace("Canonical V77.18.20 Claude reviewer validation PASS","Canonical V77.18.22 safe-risk balanced-discovery validation PASS",1)
p.write_text(s)

# Checkpoint
Path('docs/checkpoints/V771822_SAFE_RISK_BALANCED_DISCOVERY.md').write_text('''# V77.18.22 — SAFE DAILY RISK + BALANCED DISCOVERY

Risk policy activates 2026-08-19 00:00 UTC / 07:00 Vietnam, after Hyro daily reset. A base risk 0.45%, single cap 0.55%, combined cap 0.90%, internal daily hard stop 1.60%, target lock ~1.20%. Structural SL remains authoritative; size is reduced rather than tightening SL. TP1 ~0.85R 45%, TP2 ~1.60R 35%, runner ~2.45R 20%.

Signal V77.16.10 modestly relaxes soft discovery gates only. Hard news/freshness/structure/execution-authority/futures-risk gates remain.

Claude remains review-only. Temporary overnight review cadence is 30 minutes until 00:00 UTC, bounded by temporary budget. Normal policy returns afterwards. Never reset TRADING_STATE or v775:books.
''')
print('V77.18.22 migration patch complete')
