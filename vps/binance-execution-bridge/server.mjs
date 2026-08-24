import http from 'node:http';
import crypto from 'node:crypto';

const HOST=process.env.BINANCE_BRIDGE_HOST||'127.0.0.1';
const PORT=Number(process.env.BINANCE_BRIDGE_PORT||8790);
const BASE=String(process.env.BINANCE_FUTURES_BASE_URL||'https://fapi.binance.com').replace(/\/$/,'');
const KEY=String(process.env.BINANCE_FUTURES_API_KEY||'');
const SECRET=String(process.env.BINANCE_FUTURES_API_SECRET||'');
const BRIDGE_SECRET=String(process.env.BINANCE_BRIDGE_SECRET||'');

function json(res,status,body){const s=JSON.stringify(body);res.writeHead(status,{'content-type':'application/json; charset=utf-8','cache-control':'no-store','content-length':Buffer.byteLength(s)});res.end(s);}
function auth(req){if(!BRIDGE_SECRET)return false;const h=String(req.headers.authorization||'');const want='Bearer '+BRIDGE_SECRET;return crypto.timingSafeEqual(Buffer.from(h.padEnd(want.length,'\0').slice(0,want.length)),Buffer.from(want));}
function sign(q){return crypto.createHmac('sha256',SECRET).update(q).digest('hex');}
function upstreamError(kind,status,body){const err=new Error(kind);err.kind=kind;err.upstreamStatus=Number(status)||null;err.binanceCode=typeof body?.code==='number'?body.code:null;err.binanceMessage=typeof body?.msg==='string'?body.msg.slice(0,300):null;return err;}
async function signed(path,params={}){if(!KEY||!SECRET)throw new Error('BINANCE_CREDENTIALS_MISSING');const usp=new URLSearchParams({...params,timestamp:String(Date.now()),recvWindow:'5000'});const q=usp.toString();const r=await fetch(`${BASE}${path}?${q}&signature=${sign(q)}`,{headers:{'X-MBX-APIKEY':KEY,accept:'application/json'}});const text=await r.text();let body;try{body=JSON.parse(text)}catch{body={}}if(!r.ok)throw upstreamError('BINANCE_SIGNED_REQUEST_FAILED',r.status,body);return body;}
async function pub(path,params={}){const usp=new URLSearchParams(params);const r=await fetch(`${BASE}${path}?${usp.toString()}`,{headers:{accept:'application/json'}});const text=await r.text();let body;try{body=JSON.parse(text)}catch{body={}}if(!r.ok)throw upstreamError('BINANCE_PUBLIC_REQUEST_FAILED',r.status,body);return body;}

const server=http.createServer(async(req,res)=>{
  try{
    if(req.url==='/health'&&req.method==='GET')return json(res,200,{ok:true,service:'BINANCE_EXECUTION_BRIDGE',mode:'READ_ONLY',credentialsPresent:Boolean(KEY&&SECRET),base:BASE,ts:Date.now()});
    if(!auth(req))return json(res,401,{ok:false,readOnly:true,authenticated:false,reason:'BINANCE_BRIDGE_UNAUTHORIZED'});
    if(req.url==='/binance/health'&&req.method==='GET'){
      const [account,positions,orders,book]=await Promise.all([
        signed('/fapi/v2/account'),signed('/fapi/v2/positionRisk'),signed('/fapi/v1/openOrders'),pub('/fapi/v1/ticker/bookTicker',{symbol:'BTCUSDT'})
      ]);
      const open=(Array.isArray(positions)?positions:[]).filter(x=>Math.abs(Number(x.positionAmt||0))>0).map(x=>({symbol:x.symbol,positionAmt:Number(x.positionAmt),entryPrice:Number(x.entryPrice),markPrice:Number(x.markPrice),unrealizedProfit:Number(x.unRealizedProfit??x.unrealizedProfit),leverage:Number(x.leverage),marginType:x.marginType}));
      return json(res,200,{ok:true,readOnly:true,authenticated:true,via:'VPS',base:BASE,account:{totalWalletBalance:Number(account?.totalWalletBalance),totalMarginBalance:Number(account?.totalMarginBalance),availableBalance:Number(account?.availableBalance),totalUnrealizedProfit:Number(account?.totalUnrealizedProfit)},positions:{openCount:open.length,items:open.slice(0,20)},openOrdersCount:Array.isArray(orders)?orders.length:null,btcusdt:{bid:Number(book?.bidPrice),ask:Number(book?.askPrice)},checkedAt:new Date().toISOString(),guarantees:['NO_ORDER_SUBMISSION','NO_LEVERAGE_CHANGE','NO_MARGIN_CHANGE','NO_CANCEL']});
    }
    return json(res,404,{ok:false,reason:'NOT_FOUND'});
  }catch(e){return json(res,502,{ok:false,readOnly:true,authenticated:false,reason:String(e?.kind||e?.message||'BINANCE_BRIDGE_ERROR'),upstreamStatus:Number.isFinite(e?.upstreamStatus)?e.upstreamStatus:null,binanceCode:Number.isFinite(e?.binanceCode)?e.binanceCode:null,binanceMessage:e?.binanceMessage||null,checkedAt:new Date().toISOString()});}
});
server.listen(PORT,HOST,()=>console.log(`BINANCE_EXECUTION_BRIDGE listening ${HOST}:${PORT} READ_ONLY`));
