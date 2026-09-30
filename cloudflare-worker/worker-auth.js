export function authState(req,env){
  const action=String(env.GPT_5AI_ACTION_KEY||''),bridge=String(env.V11_AI_BRIDGE_SECRET||env.BYBIT_VPS_BRIDGE_SECRET||'');
  const raw=String(req.headers.get('x-action-key')||req.headers.get('authorization')||''),got=raw.replace(/^Bearer\s+/i,'');
  const source=got&&action&&got===action?'ACTION_KEY':got&&bridge&&got===bridge?'VPS_BRIDGE_SECRET':null;
  return {ok:!!source,source,actionKeyPresent:!!action,bridgeKeyPresent:!!bridge,requestKeyPresent:!!got};
}
