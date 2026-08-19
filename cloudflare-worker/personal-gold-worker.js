import {scanPersonalGold} from "./personal-gold-engine.js";
import {runPersonalGoldCycle,getPersonalGoldRuntime} from "./personal-gold-runtime.js";
import {getPersonalGoldAccount,getPersonalGoldPositions} from "./personal-gold-execution.js";

const json=(x,status=200)=>new Response(JSON.stringify(x,null,2),{status,headers:{"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
const authorized=(req,env)=>!env.PERSONAL_GOLD_CONTROL_TOKEN||req.headers.get("authorization")===`Bearer ${env.PERSONAL_GOLD_CONTROL_TOKEN}`;
export default {
  async fetch(req,env){
    const u=new URL(req.url);
    if(!authorized(req,env))return json({ok:false,error:"UNAUTHORIZED"},401);
    try{
      if(u.pathname==="/health")return json({ok:true,service:"personal-gold-scalper",live:String(env.PERSONAL_GOLD_AUTO_EXECUTE||"").toLowerCase()==="true"});
      if(u.pathname==="/status")return json(await getPersonalGoldRuntime(env));
      if(u.pathname==="/account")return json(await getPersonalGoldAccount(env));
      if(u.pathname==="/positions")return json(await getPersonalGoldPositions(env));
      if(u.pathname==="/scan")return json(await scanPersonalGold(env));
      if(u.pathname==="/cycle"&&req.method==="POST")return json(await runPersonalGoldCycle(env,{forceScan:true}));
      return json({ok:false,error:"NOT_FOUND"},404);
    }catch(e){return json({ok:false,error:String(e?.message||e)},500);}
  },
  async scheduled(_controller,env,ctx){ctx.waitUntil(runPersonalGoldCycle(env).catch(()=>null));}
};
