import {createExnessReadonlyClient} from './exness-client.js';
import {exnessShadowConfig,EXNESS_SHADOW_VERSION} from './exness-config.js';

const json=(body,status=200)=>new Response(JSON.stringify(body,null,2),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});

const pickAccount=a=>({
  accountStatus:a?.account_status??null,
  tradeMode:a?.trade_mode??null,
  currency:a?.currency??null,
  leverage:a?.leverage??null,
  balance:a?.balance??null,
  equity:a?.equity??null,
  usedMargin:a?.used_margin??null,
  freeMargin:a?.free_margin??null,
});

export async function handleExnessReadonlyHealth(req,env){
  const u=new URL(req.url);
  if(u.pathname!=='/exness/health')return null;
  if(req.method!=='GET')return json({ok:false,readOnly:true,reason:'METHOD_NOT_ALLOWED'},405);

  const cfg=exnessShadowConfig(env);
  const base={
    exchange:'EXNESS',
    version:EXNESS_SHADOW_VERSION,
    readOnly:true,
    shadow:true,
    mode:cfg.mode,
    enabled:cfg.enabled,
    liveEnabled:cfg.liveEnabled,
    liveAck:cfg.liveAck,
    writesAllowed:false,
    accountIdConfigured:!!cfg.accountId,
    baseUrlConfigured:!!cfg.baseUrl,
  };
  if(!cfg.ready)return json({...base,ok:false,authenticated:null,blockers:cfg.blockers,reason:'EXNESS_SHADOW_CONFIG_BLOCKED'},503);

  const api=createExnessReadonlyClient(env);
  const [accountResult,instrumentsResult,limitsResult]=await Promise.allSettled([
    api.account(),api.instruments(),api.limits()
  ]);
  const failures=[accountResult,instrumentsResult,limitsResult].filter(x=>x.status==='rejected');
  if(failures.length){
    const first=failures[0].reason?.exness||{};
    const authFailed=[401,403].includes(Number(first.httpStatus||0));
    return json({
      ...base,
      ok:false,
      authenticated:authFailed?false:null,
      reason:'EXNESS_READONLY_HEALTH_FAILED',
      blockers:['EXNESS_READONLY_HEALTH_FAILED'],
      upstream:{
        httpStatus:first.httpStatus??null,
        errorCode:first.errorCode??null,
        errorMessage:first.errorMessage||String(failures[0].reason?.message||'').slice(0,180),
      },
      checks:{
        account:accountResult.status,
        instruments:instrumentsResult.status,
        limits:limitsResult.status,
      },
      checkedAt:new Date().toISOString(),
    },503);
  }

  const account=accountResult.value||{};
  const instrumentBody=instrumentsResult.value||{};
  const instruments=Array.isArray(instrumentBody.instruments)?instrumentBody.instruments:[];
  return json({
    ...base,
    ok:true,
    authenticated:true,
    blockers:[],
    account:pickAccount(account),
    instruments:{count:instruments.length,preview:instruments.slice(0,20)},
    limits:{available:true},
    guarantees:[
      'GET_ONLY_CONFIGURATION_ENDPOINTS',
      'NO_ORDER_CREATE_UPDATE_CANCEL',
      'NO_POSITION_OPEN_CLOSE',
      'LIVE_FLAGS_MUST_REMAIN_FALSE',
      'SECRETS_NEVER_RETURNED',
    ],
    checkedAt:new Date().toISOString(),
  });
}
