const PROFILE_RANK=Object.freeze({FAST:0,STANDARD:1,DEEP:2});
const DATA_CLASSES=new Set(['PUBLIC','INTERNAL','CONFIDENTIAL','SECRET']);
const FRESHNESS=new Set(['none','normal','current','live']);
const DEEP_ACTIONS=new Set(['live_or_trading','deployment_or_runtime_claim','credential_sensitive','financial','destructive','permission_change']);
const STANDARD_ACTIONS=new Set(['ordinary_research','artifact_creation','project_context','external_tool']);
const ACTIONS=new Set(['informational',...STANDARD_ACTIONS,...DEEP_ACTIONS]);

const DEEP_TERMS=Object.freeze([
  ['credential_sensitive',['credential','api key','private key','mật khẩu',' secret']],
  ['financial',['thanh toán','chuyển tiền','withdraw','rút tiền','financial action','wallet signing']],
  ['destructive',['xóa dữ liệu','delete production','destroy','destructive']],
  ['permission_change',['permission','phân quyền','cấp quyền','revoke scope']],
  ['deployment_or_runtime_claim',['deploy','production','runtime','triển khai']],
  ['live_or_trading',[' live','realtime','real-time','trading','giao dịch','market entry','tìm entry','quét giá','giá hiện tại']],
]);
const STANDARD_TERMS=Object.freeze([
  ['ordinary_research',['nghiên cứu','tìm nguồn','research']],
  ['artifact_creation',['tạo file','tạo báo cáo','artifact','docx','pdf','pptx','spreadsheet']],
  ['project_context',['project','dự án','repo','repository']],
  ['external_tool',['dùng công cụ','tool','connector','plugin']],
]);

function boundedStrings(value,maxItems=32,maxChars=80){
  if(value===undefined||value===null)return [];
  if(!Array.isArray(value)||value.length>maxItems)throw new Error('invalid_string_list');
  const out=[];
  const seen=new Set();
  for(const item of value){
    if(typeof item!=='string')throw new Error('invalid_string_list_item');
    const text=item.trim();
    if(!text||text.length>maxChars)throw new Error('invalid_string_list_item');
    if(!seen.has(text)){seen.add(text);out.push(text);}
  }
  return out;
}

function inferAction(text,freshness,toolClasses){
  const lower=` ${String(text||'').toLocaleLowerCase('und')}`;
  if(freshness==='live')return 'live_or_trading';
  for(const [action,terms] of DEEP_TERMS)if(terms.some(term=>lower.includes(term)))return action;
  if(toolClasses.includes('artifact_creation'))return 'artifact_creation';
  if(toolClasses.length)return 'external_tool';
  for(const [action,terms] of STANDARD_TERMS)if(terms.some(term=>lower.includes(term)))return action;
  return 'informational';
}

export function normalizeUniversalRequest(payload,clientId,adapterVersion='1.0'){
  if(!payload||typeof payload!=='object'||Array.isArray(payload))throw new Error('invalid_request');
  const text=payload.text;
  if(typeof text!=='string'||!text.trim()||text.length>20_000)throw new Error('invalid_text');
  const requestId=payload.request_id;
  const sessionId=payload.session_id;
  if(typeof requestId!=='string'||!requestId.trim()||requestId.length>160)throw new Error('invalid_request_id');
  if(typeof sessionId!=='string'||!sessionId.trim()||sessionId.length>160)throw new Error('invalid_session_id');
  const client=String(clientId||'').trim().toLowerCase();
  if(!client||client.length>64)throw new Error('invalid_client_id');
  const freshnessRaw=String(payload.freshness||'none').trim().toLowerCase();
  const freshness=FRESHNESS.has(freshnessRaw)?freshnessRaw:'current';
  const rawClass=String(payload.data_class||'PUBLIC').trim().toUpperCase();
  const dataClass=DATA_CLASSES.has(rawClass)?rawClass:'SECRET';
  const toolClasses=boundedStrings(payload.tool_classes);
  const declaredCapabilities=boundedStrings(payload.declared_capabilities);
  const explicit=String(payload.requested_action_class||'').trim().toLowerCase();
  const action=ACTIONS.has(explicit)?explicit:inferAction(text,freshness,toolClasses);
  let projectHint=payload.project_hint??null;
  if(projectHint!==null){
    if(typeof projectHint!=='string'||projectHint.length>160)throw new Error('invalid_project_hint');
    projectHint=projectHint.trim()||null;
  }
  return Object.freeze({
    client_id:client,
    adapter_version:String(adapterVersion||'1.0'),
    session_id:sessionId.trim(),
    request_id:requestId.trim(),
    text:text.trim(),
    project_hint:projectHint,
    freshness,
    declared_capabilities:declaredCapabilities,
    tool_classes:toolClasses,
    data_class:dataClass,
    requested_action_class:action,
  });
}

export function classifyEntrySafety(normalized){
  const action=String(normalized?.requested_action_class||'informational');
  const dataClass=String(normalized?.data_class||'SECRET').toUpperCase();
  const freshness=String(normalized?.freshness||'none').toLowerCase();
  const highImpact=DEEP_ACTIONS.has(action)||dataClass==='SECRET';
  let profileFloor='FAST';
  if(highImpact||freshness==='live')profileFloor='DEEP';
  else if(STANDARD_ACTIONS.has(action)||freshness==='current')profileFloor='STANDARD';
  return Object.freeze({
    profileFloor,
    highImpact,
    requiresOnlineBrain:profileFloor!=='FAST',
    safeDegradedAllowed:!highImpact&&!DEEP_ACTIONS.has(action)&&dataClass!=='SECRET',
    reason:dataClass==='SECRET'?'secret_or_unknown_data_class':action,
  });
}

export function effectiveProfile(canonicalProfile,safetyFloor){
  const canonical=PROFILE_RANK[canonicalProfile]===undefined?'DEEP':canonicalProfile;
  const floor=PROFILE_RANK[safetyFloor]===undefined?'DEEP':safetyFloor;
  return PROFILE_RANK[canonical]>=PROFILE_RANK[floor]?canonical:floor;
}

export const UNIVERSAL_ENTRY_PROFILE_RANK=PROFILE_RANK;
