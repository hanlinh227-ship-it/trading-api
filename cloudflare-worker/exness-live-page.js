// Public read-only UI. No credentials, account details, or order controls are sent to browsers.
export const FOREX_EIGHT_CURRENCIES=['USD','JPY','EUR','GBP','CHF','AUD','CAD','NZD'];
export const FOREX_PAIRS=['USDJPY','EURUSD','GBPUSD','USDCHF','AUDUSD','USDCAD','NZDUSD','EURJPY','GBPJPY','CHFJPY','AUDJPY','CADJPY','NZDJPY','EURGBP','EURCHF','EURAUD','EURCAD','EURNZD','GBPCHF','GBPAUD','GBPCAD','GBPNZD','AUDCHF','CADCHF','NZDCHF','AUDCAD','AUDNZD','NZDCAD'];

export const EXNESS_LIVE_PAGE=`<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Exness · Bảng giá 28 cặp</title><style>
:root{color-scheme:dark;--bg:#07111f;--panel:#101e30;--line:#27405b;--muted:#a5bad1;--text:#f0f6ff;--up:#53e6b0;--down:#ff8690}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 14% 0%,#193b59,var(--bg) 47%);color:var(--text);font:15px system-ui,-apple-system,Segoe UI,sans-serif}main{max-width:1420px;margin:auto;padding:28px 20px}header{display:flex;justify-content:space-between;gap:16px;align-items:center;flex-wrap:wrap}h1{font-size:clamp(23px,3vw,34px);margin:4px 0 7px}p{margin:0;color:var(--muted)}.kicker{font-size:11px;color:#9bc6ff;font-weight:700;letter-spacing:.17em}.badge{border:1px solid var(--line);border-radius:100px;padding:10px 15px;color:var(--muted);font-weight:700}.badge.ok{color:var(--up);border-color:#286b5d}.badge.bad{color:var(--down);border-color:#8c4150}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:22px 0}.stat,.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px}.stat{padding:16px}.stat strong{display:block;font-size:23px;margin-top:5px}.stat span{font-size:12px;color:var(--muted)}.panel{overflow:hidden}table{border-collapse:collapse;width:100%;min-width:700px}th,td{text-align:left;padding:10px 13px;border-bottom:1px solid #24384f;font-variant-numeric:tabular-nums}th{font-size:11px;text-transform:uppercase;color:var(--muted);letter-spacing:.07em}td:first-child{font-weight:750}td.bid{color:var(--up)}td.ask{color:#ffd3a0}.stale{color:var(--down)!important}.fresh{color:var(--up)}.wrap{overflow:auto;max-height:66vh}tr:target{background:#1f3b57}footer{color:var(--muted);font-size:12px;line-height:1.6;margin-top:14px}a{color:#a8d1ff}:focus-visible{outline:2px solid #9bc6ff;outline-offset:3px}@media(max-width:650px){.stats{grid-template-columns:1fr 1fr}td,th{padding:9px 10px}}
</style></head><body><main><header><div><div class="kicker">READ ONLY · EXNESS PUBLIC TRADER API</div><h1>Giá Forex trực tiếp</h1><p>8 tiền tệ · 28 cặp · Bid / Ask từ luồng WebSocket Exness</p></div><div id="status" class="badge" role="status" aria-live="polite">Đang kết nối…</div></header>
<div class="stats"><div class="stat"><span>Cặp có tick</span><strong id="count">0 / 28</strong></div><div class="stat"><span>Tick đã nhận</span><strong id="ticks">0</strong></div><div class="stat"><span>Lần nối lại</span><strong id="reconn">0</strong></div><div class="stat"><span>Dao động kênh*</span><strong id="jitter">—</strong></div><div class="stat"><span>Tick vừa nhận</span><strong id="last">—</strong></div><div class="stat"><span>Trễ nguồn → Worker*</span><strong id="latency">—</strong></div></div>
<div class="panel wrap"><table><thead><tr><th>Cặp</th><th>Bid</th><th>Ask</th><th>Spread</th><th>Giờ nguồn (UTC)</th><th>Tuổi tick*</th><th>Trễ tới Worker*</th></tr></thead><tbody id="prices"></tbody></table></div>
<footer>* <b>Tuổi tick</b> = thời gian kể từ tick nguồn cuối, gồm cả lúc thị trường đứng yên — <b>không phải</b> độ trễ mạng. <b>Trễ tới Worker</b> đo giữa hai đồng hồ hạ tầng (Exness và Cloudflare) nên đáng tin. <b>Dao động kênh</b> là hiệu giữa nhịp đến và nhịp gửi của hai tick liên tiếp, nên triệt tiêu lệch đồng hồ máy và là chỉ số ổn định đáng tin nhất. Nguồn có thể giới hạn cập nhật tới một lần mỗi 500 ms. Tab ẩn sẽ tạm dừng luồng để không tiêu tốn quota dùng chung. Không có chức năng đặt lệnh.</footer></main>
<script>
const pairs=${JSON.stringify(FOREX_PAIRS)}, rows=new Map(), quotes=new Map(), $=id=>document.getElementById(id), N=pairs.length;
for(const pair of pairs){const tr=document.createElement('tr');tr.innerHTML='<td></td><td class="bid">—</td><td class="ask">—</td><td>—</td><td>—</td><td>Chờ</td><td>—</td>';tr.children[0].textContent=pair;$('prices').append(tr);rows.set(pair,tr)}
const fmtCache=new Map();
function fmtFor(pair){let f=fmtCache.get(pair);if(!f){f=new Intl.NumberFormat('en-US',{minimumFractionDigits:pair.endsWith('JPY')?3:5,maximumFractionDigits:8});fmtCache.set(pair,f)}return f}
const format=(n,pair)=>fmtFor(pair).format(n);
const utcTime=iso=>{const t=Date.parse(iso);return isNaN(t)?'—':new Date(t).toISOString().slice(11,23)};
const setText=(id,value)=>{const el=$(id);if(el&&el.textContent!==value)el.textContent=value};
const setStatus=(text,kind)=>{const el=$('status'),cls='badge '+(kind||'');if(el.textContent===text&&el.className===cls)return;el.textContent=text;el.className=cls};
let socket=null,attempt=0,retry=null,raf=0;
const pending=new Map();
const stats={ticks:0,reconnects:0,lastTickMs:0,prevSentAt:null,prevArrival:null,jitterMs:null};
function flush(){
  raf=0;
  for(const pair of pending.keys()){
    const q=pending.get(pair),tr=rows.get(pair),old=quotes.get(pair);
    quotes.set(pair,q);
    if(old&&old.bid===q.bid&&old.ask===q.ask&&old.sourceTimestamp===q.sourceTimestamp)continue;
    tr.children[1].textContent=format(q.bid,pair);
    tr.children[2].textContent=format(q.ask,pair);
    tr.children[3].textContent=format(q.ask-q.bid,pair);
    tr.children[4].textContent=utcTime(q.sourceTimestamp);
    tr.children[6].textContent=(typeof q.sourceToWorkerMs==='number'?q.sourceToWorkerMs+' ms':'—');
    tr.children[1].className='bid '+(old&&q.bid<old.bid?'stale':'');
  }
  pending.clear();
  setText('count',quotes.size+' / '+N);
}
function onTick(q){
  if(!rows.has(q.instrument)||!(q.bid>0&&q.ask>q.bid))return;
  const arrival=performance.now(),now=Date.now();
  stats.ticks++;stats.lastTickMs=now;
  if(typeof q.sentAt==='number'&&stats.prevSentAt!==null){
    const drift=(arrival-stats.prevArrival)-(q.sentAt-stats.prevSentAt);
    stats.jitterMs=Math.round(drift*10)/10;
  }
  if(typeof q.sentAt==='number'){stats.prevSentAt=q.sentAt;stats.prevArrival=arrival}
  pending.set(q.instrument,q);
  if(!raf)raf=requestAnimationFrame(flush);
  setText('ticks',String(stats.ticks));
  setText('jitter',stats.jitterMs===null?'—':stats.jitterMs+' ms');
  setText('last',q.instrument+' · '+new Date(now).toLocaleTimeString('vi-VN',{hour12:false}));
  setText('latency',typeof q.sourceToWorkerMs==='number'?q.sourceToWorkerMs+' ms':'—');
  setStatus('● Đang truyền tick','ok');
}
function connect(){
  clearTimeout(retry);
  if(document.hidden){setStatus('Tạm dừng — tab ẩn','');return}
  setStatus('Đang kết nối…','');
  const scheme=location.protocol==='https:'?'wss:':'ws:';
  try{socket=new WebSocket(scheme+'//'+location.host+'/exness/live/ws')}catch(err){setStatus('Không mở được WebSocket','bad');return}
  socket.onopen=()=>{attempt=0;stats.prevSentAt=null;stats.prevArrival=null;stats.jitterMs=null;setText('jitter','—');setStatus('● Đang truyền tick','ok')};
  socket.onmessage=e=>{
    let q;try{q=JSON.parse(e.data)}catch{return}
    if(q.type==='tick')onTick(q);
    else if(q.type==='stalled'){setStatus('Nguồn im lặng — nối lại','bad');try{socket.close()}catch{}}
    else if(q.type==='error')setStatus('Lỗi luồng: '+q.error,'bad');
  };
  socket.onerror=()=>setStatus('Lỗi kết nối','bad');
  socket.onclose=()=>{
    socket=null;stats.reconnects++;setText('reconn',String(stats.reconnects));
    const wait=Math.min(30000,1000*Math.pow(2,Math.min(attempt++,5)))+Math.round(Math.random()*400);
    setStatus('Mất kết nối — thử lại sau '+Math.round(wait/1000)+'s','bad');
    clearTimeout(retry);retry=setTimeout(connect,wait);
  };
}
document.addEventListener('visibilitychange',()=>{
  if(document.hidden){clearTimeout(retry);if(socket){try{socket.close(1000,'hidden')}catch{}}setStatus('Tạm dừng — tab ẩn','')}
  else{attempt=0;connect()}
});
window.addEventListener('online',()=>{attempt=0;connect()});
connect();
setInterval(()=>{
  if(document.hidden)return;
  const now=Date.now();
  if(socket&&stats.lastTickMs&&now-stats.lastTickMs>15000){setStatus('Im lặng >15s — nối lại','bad');try{socket.close()}catch{}return}
  for(const pair of quotes.keys()){
    const q=quotes.get(pair),cell=rows.get(pair).children[5];
    const age=Math.max(0,now-Date.parse(q.sourceTimestamp)),v=String(age);
    if(cell.dataset.v!==v){cell.dataset.v=v;cell.textContent=v+' ms'}
    const cls=age>10000?'stale':'fresh';
    if(cell.className!==cls)cell.className=cls;
  }
},1000);
</script></body></html>`;
