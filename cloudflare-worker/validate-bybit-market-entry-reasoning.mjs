import fs from 'node:fs';
import path from 'node:path';

const root=process.cwd();
const read=f=>fs.readFileSync(path.join(root,f),'utf8');
const errors=[];
const need=(txt,arr,label)=>{for(const x of arr)if(!txt.includes(x))errors.push(`${label} missing ${x}`);};

const reasoning=read('bybit-market-entry-reasoning.js');
const runtime=read('bybit-runtime-contract.js');
const profiles=read('binance-symbol-profiles.js');
const engine=read('bybit-scalp-engine.js');
const auto=read('bybit-auto-v1.js');
const risk=read('bybit-risk-guard.js');
const gate=read('bybit-ai-scalp-gate.js');
const manager=read('bybit-position-manager.js');
const cfg=read('bybit-auto-config.js');

need(reasoning,[
  'BYBIT_MARKET_ENTRY_REASONING_V1',
  'provenance:"CLAUDE_COARCHITECT_GPT_PRIMARY_ENGINEER_FUSION"',
  'signalTimeframe:"5m"',
  'contextTimeframe:"15m"',
  'closedCandlesOnly:true',
  'm1DecisionAuthority:false',
  'liveQuoteRequired:true',
  'staleQuoteAllowed:false',
  'noNewEntryFilters:true',
  'noHiddenSizingRejects:true',
  'spreadDoublePenalty:false',
  'softCorrelationPolicy:"SIZE_ONLY"',
  'hardCorrelationPolicy:"REJECT"',
  'candidateFallbackSameCycle:true',
  'sameDirectionPreflight:true',
  'postAiQuoteRevalidation:true',
  'designPriorities:["REAL_EDGE","TAIL_RISK_REDUCTION","FREQUENCY_PRESERVATION","EXECUTION_ROBUSTNESS"]',
  'rejectComplexityWithoutEdge:true',
  'noFabricatedPrice:true',
  'autoPromoteLearning:false'
],'REASONING_CONTRACT');

need(runtime,[
  'BYBIT-AUTO-1.9.7',
  'BYBIT_MARKET_ENTRY_REASONING',
  'marketEntryReasoning:BYBIT_MARKET_ENTRY_REASONING'
],'RUNTIME_CONTRACT');

need(profiles,[
  'BYBIT_SIGNAL_TIMEFRAME="5m"',
  'BYBIT_CONTEXT_TIMEFRAME="15m"',
  'BYBIT_M1_SIGNAL_DISABLED=true'
],'TIMEFRAME_AUTHORITY');

need(engine,[
  'closedCandleSignal:true',
  'm1SignalAuthority:false',
  'correlationSoftPolicy:"SIZE_ONLY"',
  'TREND_CONTINUATION',
  'setupTypes:["TREND_PULLBACK","TREND_CONTINUATION","BREAKOUT"]',
  'autoPromote:false'
],'SCALP_ENGINE');

need(auto,[
  'BYBIT_CANDIDATE_FALLBACK_MAX',
  'candidateQueue=',
  'candidateSide:setup.side',
  'CANDIDATE_QUEUE_EXHAUSTED',
  'revalidateBybitScalpAfterAi'
],'AUTO_FALLBACK_EXECUTION');

need(risk,['SAME_DIRECTION_EXPOSURE_CAP'],'RISK_PREFLIGHT');
need(gate,['revalidateBybitScalpAfterAi','STRICT_2AI_FINAL_ENTRY_REVIEW'],'AI_REVALIDATION');
need(manager,['SIGNAL_INTERVAL="5"','CONTEXT_INTERVAL="15"','m1Authority:false'],'POSITION_MANAGER');
need(cfg,[
  'maxRiskPctOfEquity:4.5',
  'maxTotalOpenRiskPct:18',
  'maxPortfolioMarginPct:75',
  'minFreeReservePct:15',
  'minRR:1.5',
  'maxSameDirectionPositions:3',
  'autoPromote:false'
],'RISK_AUTHORITY');

if(errors.length){
  console.error(`BYBIT_MARKET_ENTRY_REASONING=FAIL (${errors.length})`);
  for(const e of errors)console.error('- '+e);
  process.exit(1);
}
console.log('BYBIT_MARKET_ENTRY_REASONING=PASS: Claude+GPT fusion provenance locked; runtime exposes V1 contract; closed 5m/15m authority; M1 disabled; pullback/continuation/breakout setup family; soft correlation size-only; same-cycle fallback; same-direction preflight; post-AI quote revalidation; hard risk caps retained.');
