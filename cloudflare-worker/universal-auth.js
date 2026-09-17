import {UNIVERSAL_ADAPTERS} from './generated/universal-adapters.js';

const CLIENTS=Object.freeze(Object.fromEntries((UNIVERSAL_ADAPTERS.adapters||[]).map(row=>[
  row.id,
  Object.freeze({binding:row.token_binding,principalType:row.principal_type||'user',scopes:Object.freeze([...(row.scopes||[])])}),
])));

const encoder=new TextEncoder();

function constantTimeEqual(a,b){
  const left=encoder.encode(String(a||''));
  const right=encoder.encode(String(b||''));
  const length=Math.max(left.length,right.length,1);
  let diff=left.length^right.length;
  for(let i=0;i<length;i++)diff|=(left[i%Math.max(left.length,1)]||0)^(right[i%Math.max(right.length,1)]||0);
  return diff===0;
}

function bearer(request){
  const value=String(request?.headers?.get?.('authorization')||'');
  const match=value.match(/^Bearer\s+(.+)$/i);
  return match?match[1]:'';
}

export function requiredScopeForPath(pathname,method='GET'){
  const methodUpper=String(method||'GET').toUpperCase();
  if(pathname==='/brain/universal/route'&&methodUpper==='POST')return 'brain.route';
  if((pathname==='/brain/universal/health'||pathname==='/brain/universal/capabilities')&&methodUpper==='GET')return 'brain.read_runtime_health';
  if(pathname==='/brain/memory/candidates'&&methodUpper==='POST')return 'brain.submit_candidate_memory';
  if(pathname==='/brain/memory/review'&&methodUpper==='POST')return 'brain.review_candidate_memory';
  if(pathname==='/brain/context/query'&&methodUpper==='POST')return 'brain.read_context';
  if(pathname==='/brain/bootstrap'&&methodUpper==='GET')return 'brain.bootstrap';
  if(pathname==='/brain/project/state'&&methodUpper==='GET')return 'brain.read_project_state';
  if(pathname==='/brain/project/state'&&methodUpper==='PUT')return 'brain.write_project_state';
  return null;
}

export async function authenticateAdapter(request,env={},requiredScope='brain.route'){
  const clientId=String(request?.headers?.get?.('x-brain-client')||'').trim().toLowerCase();
  const client=CLIENTS[clientId];
  if(!client)return {ok:false,status:401,error:'adapter_auth_required'};
  const configured=String(env?.[client.binding]||'');
  if(!configured)return {ok:false,status:503,error:'adapter_not_configured'};
  const supplied=bearer(request);
  if(!supplied||!constantTimeEqual(supplied,configured))return {ok:false,status:401,error:'adapter_auth_required'};
  if(typeof requiredScope!=='string'||!requiredScope||!client.scopes.includes(requiredScope))return {ok:false,status:403,error:'scope_denied'};
  return {
    ok:true,
    status:200,
    principal:{clientId,principalType:client.principalType,scopes:[...client.scopes]},
  };
}

export const UNIVERSAL_CLIENT_IDS=Object.freeze(Object.keys(CLIENTS));
export const UNIVERSAL_USER_CLIENT_IDS=Object.freeze(Object.keys(CLIENTS).filter(id=>CLIENTS[id].principalType==='user'));
export const UNIVERSAL_INTERNAL_CLIENT_IDS=Object.freeze(Object.keys(CLIENTS).filter(id=>CLIENTS[id].principalType==='internal'));
export const UNIVERSAL_ADAPTER_SOURCE_SHA=UNIVERSAL_ADAPTERS.source_sha;
