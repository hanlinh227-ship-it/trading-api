import fs from 'node:fs';
const FILE='/var/lib/meme-alpha/data/paper/scanner-latest.json';
const OUT='/opt/meme-alpha/app/runtime-status/universe.json';
const CFG='/opt/meme-alpha/app/config/runtime.json';
if(!fs.existsSync(FILE)) throw new Error('SCANNER_STATE_MISSING');
const scan=JSON.parse(fs.readFileSync(FILE,'utf8')); const cfg=JSON.parse(fs.readFileSync(CFG,'utf8'));
const uniq=x=>[...new Set(x)];
const NON_MEME_SYMBOLS=new Set(['SOL','WSOL','USDC','USDT','USD1','PYUSD','USDS','DAI','PYTH','HNT','MOBILE','TRX','CBBTC','WBTC','JUPUSD','USDUC','JITOSOL','MSOL','BSOL','STSOL','JUPSOL','JSOL','HSOL','INF','JUP','JTO','RAY','ORCA','DRIFT','MNDE','KMNO','RENDER','RNDR','TNSR','IO','W','WORMHOLE']);
const NON_MEME_MINTS=new Set(['So11111111111111111111111111111111111111112','J1toso1uCk3RLmjorhTtrVwY9HJ7X8V9yYac6Y7kGCPn','EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v']);
const NON_MEME_NAMES=[/\bwrapped\s+(sol|bitcoin|btc)\b/i,/\bcoinbase\s+wrapped\b/i,/\busd\s+coin\b/i,/\btether\b/i,/\bliquid\s+stak/i,/\bstaked\s+sol\b/i,/\bpyth\s+network\b/i,/\bhelium\b/i,/\bwormhole\b/i,/\bjupiter\s+(exchange|governance)\b/i,/\braydium\b/i,/\borca\s+protocol\b/i,/\bdrift\s+protocol\b/i];
const MEME_TERMS=/\b(meme|memecoin|doge|shib|pepe|bonk|wif|cat|kitty|kitten|dog|doggo|frog|goat|monkey|ape|pnut|peanut|popcat|chillguy|fart|moo|pengu|pudgy|wojak|mog|brett|floki|inu|hamster|capy|hippo|sigma|gigachad|chad)\b/i;
function classify(c){
 const symbol=String(c.symbol||'').trim().toUpperCase(); const mint=String(c.mint||'').trim(); const name=String(c.name||c.tokenName||c.metadata?.name||'').trim(); const text=`${symbol} ${name}`;
 const reasons=[]; if(NON_MEME_MINTS.has(mint)) reasons.push('CANONICAL_NON_MEME_MINT'); if(NON_MEME_SYMBOLS.has(symbol)) reasons.push('KNOWN_NON_MEME_SYMBOL'); if(name&&NON_MEME_NAMES.some(r=>r.test(name))) reasons.push('KNOWN_NON_MEME_NAME');
 if(reasons.length) return {universeClass:'NON_MEME',universeConfidence:'HIGH',reasons};
 const sourceCount=new Set(c.sources||[]).size; const organic=Number(c.organicRatio5m||0); const liq=Number(c.liquidityUsd||0); const launchpadPump=mint.toLowerCase().endsWith('pump'); const memeText=MEME_TERMS.test(text);
 if(launchpadPump) return {universeClass:'MEME_CONFIRMED',universeConfidence:'HIGH',reasons:['PUMPFUN_MINT_SUFFIX']};
 if(memeText&&sourceCount>=3&&organic>=0.35&&liq>=Math.max(50000,Number(cfg.minLiquidityUsd||25000))) return {universeClass:'MEME_CONFIRMED',universeConfidence:'MEDIUM',reasons:['MEME_SEMANTIC_SIGNAL','MULTISOURCE_ORGANIC_CONFIRMATION']};
 if(memeText&&sourceCount>=2&&organic>=0.15&&liq>=Number(cfg.minLiquidityUsd||25000)) return {universeClass:'MEME_PROBABLE',universeConfidence:'MEDIUM',reasons:['MEME_SEMANTIC_SIGNAL','ORGANIC_FLOW_SUPPORT']};
 return {universeClass:'UNCLASSIFIED',universeConfidence:'LOW',reasons:['POSITIVE_MEME_EVIDENCE_INSUFFICIENT']};
}
let nonMeme=0,confirmed=0,probable=0,unclassified=0;
for(const c of scan.candidates||[]){ const u=classify(c); c.universeClass=u.universeClass; c.universeConfidence=u.universeConfidence; c.universeReasons=u.reasons;
 if(u.universeClass==='NON_MEME'){nonMeme++;c.decision='IGNORE';c.hardReject=uniq([...(c.hardReject||[]),'NON_MEME_UNIVERSE']);}
 else if(u.universeClass==='UNCLASSIFIED'){unclassified++;c.decision='IGNORE';c.hardReject=uniq([...(c.hardReject||[]),'MEME_EVIDENCE_INSUFFICIENT']);}
 else if(u.universeClass==='MEME_CONFIRMED') confirmed++; else probable++;
 c.reasons=uniq([...(c.reasons||[]),...u.reasons]);
}
scan.universe={version:'1.6',filteredAt:new Date().toISOString(),policy:'POSITIVE_MEME_EVIDENCE_FAIL_CLOSED',memeConfirmed:confirmed,memeProbable:probable,nonMemeBlocked:nonMeme,unclassifiedBlocked:unclassified,unknownEntryEligible:false};
const tmp=`${FILE}.tmp-${process.pid}`; fs.writeFileSync(tmp,JSON.stringify(scan,null,2)); fs.renameSync(tmp,FILE);
fs.writeFileSync(`${OUT}.tmp`,JSON.stringify(scan.universe,null,2)); fs.renameSync(`${OUT}.tmp`,OUT); try{fs.chmodSync(OUT,0o664)}catch{}
console.log('=== MEME ALPHA UNIVERSE v1.6 ==='); console.log(`MEME_CONFIRMED=${confirmed}`); console.log(`MEME_PROBABLE=${probable}`); console.log(`NON_MEME_BLOCKED=${nonMeme}`); console.log(`UNCLASSIFIED_BLOCKED=${unclassified}`); console.log('UNKNOWN_ENTRY_ELIGIBLE=false'); console.log('UNIVERSE_STATUS=PASS');
