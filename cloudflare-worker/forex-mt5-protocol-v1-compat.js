import {handleForexAutonomousMt5Bridge} from "./forex-autonomous-mt5-bridge.js";

function n(v,d=0){return Number.isFinite(Number(v))?Number(v):d;}
function normalizeBar(r={}){
  return {
    time:r.time??r.t??null,
    open:n(r.open??r.o),
    high:n(r.high??r.h),
    low:n(r.low??r.l),
    close:n(r.close??r.c),
    volume:n(r.volume??r.v)
  };
}
function normalizeBars(rows){return Array.isArray(rows)?rows.map(normalizeBar):[];}
function normalizeSnapshot(s={}){
  const bars=s?.bars&&typeof s.bars==="object"?s.bars:{};
  return {...s,bars:{M5:normalizeBars(bars.M5),M15:normalizeBars(bars.M15),H1:normalizeBars(bars.H1),H4:normalizeBars(bars.H4)}};
}
function compactJson(body,status=200,headers={}){
  const h=new Headers(headers);
  h.set("content-type","application/json; charset=utf-8");
  h.set("cache-control","no-store");
  return new Response(JSON.stringify(body),{status,headers:h});
}

export async function handleForexMt5ProtocolV1(req,env){
  const u=new URL(req.url);
  if(!u.pathname.startsWith("/forex/"))return null;

  if(u.pathname!=="/forex/mt5/pulse"||req.method!=="POST"){
    return handleForexAutonomousMt5Bridge(req,env);
  }

  let raw;
  try{raw=await req.clone().json();}catch{
    return compactJson({ok:false,error:"INVALID_JSON"},400);
  }
  const protocol=Number(raw?.protocolVersion||req.headers.get("x-forex-protocol")||1);
  const normalized={...raw,protocolVersion:protocol,snapshots:Array.isArray(raw?.snapshots)?raw.snapshots.map(normalizeSnapshot):[]};
  const headers=new Headers(req.headers);
  headers.set("content-type","application/json");
  const forwarded=new Request(req.url,{method:"POST",headers,body:JSON.stringify(normalized)});
  const res=await handleForexAutonomousMt5Bridge(forwarded,env);
  if(!res)return null;
  let body;
  try{body=await res.clone().json();}catch{return res;}
  return compactJson(body,res.status,res.headers);
}
