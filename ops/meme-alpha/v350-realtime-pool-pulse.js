import fs from 'node:fs';
const APP='/opt/meme-alpha/app';
const RADAR=`${APP}/runtime-status/new-listing-radar.json`;
const OUT=`${APP}/runtime-status/realtime-pool-pulse.json`;
const read=(p,d={})=>{try{return JSON.parse(fs.readFileSync(p,'utf8'))}catch{return d}};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const atomic=(p,x)=>{const t=p+'.tmp';try{fs.writeFileSync(t,JSON.stringify(x,null,2));fs.renameSync(t,p)}catch{try{fs.writeFileSync(p,JSON.stringify(x,null,2))}catch{}}};
function wsUrl(){const c=read(`${APP}/config/runtime.json`,{});if(c.wss)return String(c.wss);const u=String(c.rpc||'');return u.replace(/^https:/,'wss:').replace(/^http:/,'ws:')}
function topPairs(){return (read(RADAR,{candidates:[]}).candidates||[]).filter(x=>x.pairAddress&&x.mint).sort((a,b)=>(Number(b.preScore)||0)-(Number(a.preScore)||0)).slice(0,32).map(x=>({mint:x.mint,symbol:x.symbol||null,pair:x.pairAddress,preScore:Number(x.preScore)||0}))}
const events=new Map();let ws=null,open=false,subs=new Map(),pending=new Map(),lastSet='',lastConnectAt=0,lastError=null;
function note(mint){const now=Date.now(),a=events.get(mint)||[];a.push(now);while(a.length&&now-a[0]>30000)a.shift();events.set(mint,a)}
function snapshot(){const now=Date.now(),pairs=topPairs(),rows=pairs.map(p=>{const a=events.get(p.mint)||[];const c1=a.filter(t=>now-t<=1000).length,c5=a.filter(t=>now-t<=5000).length,c15=a.filter(t=>now-t<=15000).length,last=a.length?a[a.length-1]:0;const r5=c5/5,r15=Math.max(.05,c15/15),momentum=Math.min(6,r5/r15);return {...p,events1s:c1,events5s:c5,events15s:c15,eventRate5s:Number(r5.toFixed(3)),eventMomentum:Number(momentum.toFixed(3)),lastEventAgeMs:last?now-last:null}});atomic(OUT,{version:'3.50.0',updatedAt:new Date().toISOString(),status:open&&subs.size?'HEALTHY':(open?'CONNECTING':'DEGRADED'),websocketOpen:open,subscriptions:subs.size,lastConnectAt:lastConnectAt?new Date(lastConnectAt).toISOString():null,lastError,rows})}
function connect(){const url=wsUrl();if(!url){lastError='WSS_MISSING';return}try{ws=new WebSocket(url);lastConnectAt=Date.now()}catch(e){lastError=String(e.message||e);return}
  const reqs=[];ws.onopen=()=>{open=true;lastError=null;subs.clear();pending.clear();let id=1000;for(const p of topPairs()){id++;pending.set(id,p.mint);reqs.push(id);ws.send(JSON.stringify({jsonrpc:'2.0',id,method:'accountSubscribe',params:[p.pair,{encoding:'base64',commitment:'processed'}]}))}};
  ws.onmessage=e=>{try{const j=JSON.parse(String(e.data));if(j.id&&pending.has(j.id)&&Number.isFinite(Number(j.result))){subs.set(Number(j.result),pending.get(j.id));pending.delete(j.id);return}const sid=Number(j?.params?.subscription);if(Number.isFinite(sid)&&subs.has(sid))note(subs.get(sid))}catch{}};
  ws.onerror=e=>{lastError='WEBSOCKET_ERROR'};ws.onclose=()=>{open=false;subs.clear();pending.clear();ws=null};
}
async function main(){if(process.argv.includes('--self-test')){if(wsUrl().startsWith('http'))throw new Error('WSS_DERIVE');console.log('V350_REALTIME_POOL_PULSE_SELF_TEST=PASS');return}while(true){const sig=topPairs().map(x=>x.pair).sort().join('|');if(!ws||!open){connect()}else if(sig!==lastSet&&lastSet){try{ws.close()}catch{}}lastSet=sig;snapshot();await sleep(500)}}
main().catch(e=>{console.error(e);process.exit(1)});
