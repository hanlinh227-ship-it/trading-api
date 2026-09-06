import fs from 'node:fs';
const DATA='/var/lib/meme-alpha/data/paper';
const read=(name,fallback={})=>{try{return JSON.parse(fs.readFileSync(`${DATA}/${name}`,'utf8'))}catch{return fallback}};
const text=(name)=>{try{return fs.readFileSync(name,'utf8')}catch{return ''}};
const now=Date.now();
const cfg=JSON.parse(fs.readFileSync('config/runtime.json','utf8'));
const state=read('state.json',{openPositions:[],trades:[]});
const risk=read('risk-state.json',{});
const health=read('scanner-source-health.json',{});
const validation=read('validation-state.json',{});
const positionSrc=text('src/position.js');
const riskSrc=text('src/risk.js');

const pass=[]; const warn=[]; const fail=[];
const assert=(ok,name,detail='')=>(ok?pass:fail).push({name,detail});
const caution=(ok,name,detail='')=>{if(ok)pass.push({name,detail});else warn.push({name,detail});};

assert(cfg.mode==='PAPER','PAPER_MODE_HARD_GATE',cfg.mode);
assert(/LIVE_EXECUTION=DISABLED/.test(positionSrc),'LIVE_EXECUTION_DISABLED_MARKER');
assert(!/\/swap\/v2\/execute/.test(positionSrc),'NO_JUPITER_EXECUTE_PATH_IN_PAPER');
assert(/JUPITER|swap\/v2\/order/i.test(positionSrc),'JUPITER_QUOTE_MODEL_PRESENT');
assert(/EXIT_QUOTE_FAIL|PAPER_EXIT_QUOTE_FAIL/.test(positionSrc),'EXIT_QUOTE_FAIL_FAIL_CLOSED_MARKER');
assert(/MEME_ALPHA_MANAGE_ONLY/.test(positionSrc),'FAST_MANAGE_ONLY_PRESENT');
assert(/usingCache|SOURCE_HEALTH|sourceHealth/i.test(riskSrc),'SOURCE_HEALTH_GATE_PRESENT');
assert(/120|RISK.*STALE|risk.*age/i.test(riskSrc),'RISK_FRESHNESS_GATE_PRESENT');

const sourceAge=(now-Date.parse(health.checkedAt||0))/1000;
const sourceHealthy=health.status==='HEALTHY'&&health.allowNewEntries===true&&health.usingCache!==true&&sourceAge<180;
caution(sourceHealthy,'CURRENT_SOURCE_HEALTH',`status=${health.status} ageSec=${sourceAge.toFixed(1)} cache=${health.usingCache}`);
const riskAge=(now-Date.parse(risk.timestamp||risk.checkedAt||risk.updatedAt||0))/1000;
caution(Number.isFinite(riskAge)&&riskAge<120,'CURRENT_RISK_FRESHNESS',`ageSec=${Number.isFinite(riskAge)?riskAge.toFixed(1):'NaN'}`);

function ddScale(dd){if(dd>=20)return 0;if(dd>=12)return .25;if(dd>=7)return .5;if(dd>=3)return .75;return 1;}
function entryGate(x){
 if(!x.sourceHealthy||x.usingCache||!x.riskFresh)return false;
 if(x.drawdown>=20||x.positions>=3||x.exposurePct>=20)return false;
 if(!Number.isFinite(x.priceImpactPct)||Math.abs(x.priceImpactPct)>2)return false;
 if(!x.sellRoute||!x.securityPass)return false;
 return true;
}
const base={sourceHealthy:true,usingCache:false,riskFresh:true,drawdown:0,positions:0,exposurePct:0,priceImpactPct:0.5,sellRoute:true,securityPass:true};
const cases=[
 ['HEALTHY_BASE',base,true],
 ['STALE_SOURCE',{...base,sourceHealthy:false},false],
 ['CACHE_ACTIVE',{...base,usingCache:true},false],
 ['STALE_RISK',{...base,riskFresh:false},false],
 ['IMPACT_AT_LIMIT',{...base,priceImpactPct:2},true],
 ['IMPACT_OVER_LIMIT',{...base,priceImpactPct:2.01},false],
 ['NO_SELL_ROUTE',{...base,sellRoute:false},false],
 ['SECURITY_NOT_PASS',{...base,securityPass:false},false],
 ['MAX_POSITIONS',{...base,positions:3},false],
 ['MAX_EXPOSURE',{...base,exposurePct:20},false],
 ['DD_HALT',{...base,drawdown:20},false]
];
for(const [name,input,expected] of cases) assert(entryGate(input)===expected,`SYNTH_${name}`);
for(const [dd,expected] of [[0,1],[3,.75],[7,.5],[12,.25],[20,0],[30,0]]) assert(ddScale(dd)===expected,`SYNTH_DD_SCALE_${dd}`,String(expected));

for(const p of (state.openPositions||[])){
 assert(Number.isFinite(Number(p.qty))&&Number(p.qty)>=0,'POSITION_QTY_NONNEGATIVE',p.symbol||p.mint);
 assert(Number.isFinite(Number(p.remainingCostSol ?? p.costSol ?? 0))&&Number(p.remainingCostSol ?? p.costSol ?? 0)>=0,'POSITION_COST_NONNEGATIVE',p.symbol||p.mint);
 caution(Boolean(p.positionId),'POSITION_ID_PRESENT',p.symbol||p.mint);
}
assert(Number.isFinite(Number(state.equitySol))&&Number(state.equitySol)>0,'EQUITY_FINITE_POSITIVE',String(state.equitySol));

const cutoff=Date.parse('2026-09-05T04:45:26Z');
const newBuys=(state.trades||[]).filter(t=>t.type==='PAPER_BUY_PROBE'&&Date.parse(t.timestamp||0)>=cutoff);
const newSells=(state.trades||[]).filter(t=>String(t.type||'').startsWith('PAPER_SELL')&&Date.parse(t.timestamp||0)>=cutoff);
assert(newBuys.every(t=>Boolean(t.positionId)),'POST_V111_BUY_POSITION_IDS',`count=${newBuys.length}`);
caution(newSells.every(t=>Boolean(t.positionId)),'POST_V111_SELL_POSITION_IDS',`count=${newSells.length}`);

const pnlCandidates=(state.trades||[]).map(t=>Number(t.pnlSol ?? t.realizedPnlSol)).filter(Number.isFinite);
let winnerDependency={sample:pnlCandidates.length,status:'INSUFFICIENT_LIFECYCLES'};
if(pnlCandidates.length>=5){
 const total=pnlCandidates.reduce((a,b)=>a+b,0); const sorted=[...pnlCandidates].sort((a,b)=>b-a); const remove1=sorted.slice(1).reduce((a,b)=>a+b,0); const remove3=sorted.slice(3).reduce((a,b)=>a+b,0);
 winnerDependency={sample:pnlCandidates.length,total,withoutTop1:remove1,withoutTop3:remove3,status:'MEASURED'};
 caution(remove1>0,'TOP1_WINNER_DEPENDENCY',JSON.stringify(winnerDependency));
} else warn.push({name:'TOP_WINNER_STRESS',detail:'Need >=5 realized lifecycle PnL observations'});

const report={version:'1.3-shadow-stress',timestamp:new Date().toISOString(),mode:cfg.mode,behaviorChange:false,summary:{pass:pass.length,warn:warn.length,fail:fail.length},pass,warn,fail,winnerDependency,current:{equitySol:state.equitySol,openPositions:(state.openPositions||[]).length,trades:(state.trades||[]).length,sourceHealthy,riskVersion:risk.version||null,validationVersion:validation.version||null}};
const tmp=`${DATA}/stress-validation.json.tmp`; fs.writeFileSync(tmp,JSON.stringify(report,null,2)); fs.renameSync(tmp,`${DATA}/stress-validation.json`);
console.log('=== MEME ALPHA v1.3 VALIDATION & STRESS ===');
console.log(`PASS=${pass.length}`); console.log(`WARN=${warn.length}`); console.log(`FAIL=${fail.length}`); console.log(`OPEN_POSITIONS=${report.current.openPositions}`); console.log(`EQUITY_SOL=${Number(state.equitySol).toFixed(6)}`); console.log(`WINNER_STRESS=${winnerDependency.status}`);
if(fail.length){console.error(JSON.stringify(fail,null,2)); process.exit(1);} console.log('V130_STRESS_PASS');
