const SOL="So11111111111111111111111111111111111111112";
const USDC="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v";
const BASES=["https://lite-api.jup.ag","https://api.jup.ag"];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function quote(env,inputMint,outputMint,amount){
  const errors=[];
  for(const base of env.JUPITER_API_KEY?["https://api.jup.ag"]:BASES){
    for(let attempt=0;attempt<2;attempt++){
      try{
        const headers={accept:"application/json","user-agent":"MEME-AUTO-QUOTE-HEALTH/1.0"};
        if(env.JUPITER_API_KEY)headers["x-api-key"]=String(env.JUPITER_API_KEY);
        const url=`${base}/swap/v1/quote?inputMint=${encodeURIComponent(inputMint)}&outputMint=${encodeURIComponent(outputMint)}&amount=${amount}&slippageBps=100&restrictIntermediateTokens=true`;
        const r=await fetch(url,{headers});
        if(r.status===429&&attempt===0){await sleep(2200);continue;}
        if(!r.ok)throw new Error(`HTTP_${r.status}`);
        const j=await r.json();
        if(j?.outAmount)return {ok:true,source:base,outAmount:String(j.outAmount),priceImpactPct:Number(j.priceImpactPct||0),routePlanCount:Array.isArray(j.routePlan)?j.routePlan.length:0};
        throw new Error("QUOTE_EMPTY");
      }catch(e){errors.push(`${base}:${String(e?.message||e)}`);}
    }
    await sleep(2200);
  }
  return {ok:false,errors};
}
export async function getMemeJupiterQuoteHealth(env){
  const solToUsdc=await quote(env,SOL,USDC,10_000_000); // 0.01 SOL
  await sleep(2200);
  const usdcToSol=await quote(env,USDC,SOL,1_000_000); // 1 USDC
  return {ok:solToUsdc.ok&&usdcToSol.ok,service:"MEME_JUPITER_QUOTE_HEALTH",readOnly:true,noSigning:true,noExecution:true,solToUsdc,usdcToSol,checkedAt:new Date().toISOString()};
}
