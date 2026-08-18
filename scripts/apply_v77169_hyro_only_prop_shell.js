const fs=require('fs');
const p='cloudflare-worker/index.js';
let s=fs.readFileSync(p,'utf8');
function must(a,b,label){if(!s.includes(a))throw new Error('Missing '+label);s=s.replace(a,b);}
if(!s.includes('version: "V77.16.8"'))throw new Error('Expected V77.16.8');
s=s.replaceAll('V77.16.8','V77.16.9');
s=s.replace('Trading V77.16.9 Role Navigation Hub','Trading V77.16.9 Hyro-Only Prop Shell');

must(
'function propKeyboard(){return {inline_keyboard:[[{text:"🟣 HYROTRADER",callback_data:"prop:hyro"},{text:"🔵 BREAKOUT",callback_data:"prop:breakout"}],[{text:"📚 LỆNH PROP",callback_data:"prop:orders"},{text:"🛡️ RISK PROP",callback_data:"prop:risk"}],[{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]]};}',
'function propKeyboard(){return {inline_keyboard:[[{text:"🟣 HYROTRADER",callback_data:"prop:hyro"}],[{text:"📚 LỆNH HYRO",callback_data:"prop:orders"},{text:"🛡️ RISK HYRO",callback_data:"prop:risk"}],[{text:"🔌 KẾT NỐI HYRO",callback_data:"prop:connect"}],[{text:"⬅️ MENU CHÍNH",callback_data:"menu"}]]};}',
'prop keyboard');

must(
'  else if(cb==="prop")await sendText(env,"🏦 PROP\\\n\\\nTheo dõi các tài khoản quỹ được tích hợp. Kết nối execution sẽ được bật riêng cho từng quỹ sau khi xác nhận API/rule.",chatId,propKeyboard());',
'  else if(cb==="prop")await sendText(env,"🏦 PROP • HYROTRADER\\\n\\\nGiai đoạn hiện tại: gom toàn bộ phần theo dõi HyroTrader vào một khu riêng. Signal vẫn độc lập. AUTO TRADE: OFF. Chưa có API/account connection nên chưa gửi lệnh vào quỹ.",chatId,propKeyboard());',
'prop intro');

must(
'  else if(cb==="prop:hyro")await sendText(env,"🟣 HYROTRADER\\\n\\\nTrạng thái: CHƯA KẾT NỐI TÀI KHOẢN/API.\\\nSignal engine vẫn hoạt động độc lập; chưa tự gửi lệnh vào quỹ.",chatId,propKeyboard());',
'  else if(cb==="prop:hyro")await sendText(env,"🟣 HYROTRADER • TỔNG QUAN\\\n\\\nKết nối account/API: CHƯA\\\nTheo dõi balance/equity: CHƯA\\\nTheo dõi positions: CHƯA\\\nRisk firewall: SHELL READY\\\nAuto trade: OFF\\\n\\\nSignal Hub vẫn quét độc lập; chưa route bất kỳ MARKET/LIMIT nào sang HyroTrader.",chatId,propKeyboard());',
'hyro overview');

const breakout='  else if(cb==="prop:breakout")await sendText(env,"🔵 BREAKOUT\\\n\\\nTrạng thái: CHƯA KẾT NỐI TÀI KHOẢN/API.\\\nChưa bật auto-execution cho tới khi quyền bot/API được xác nhận.",chatId,propKeyboard());\n';
if(!s.includes(breakout))throw new Error('Missing breakout handler');
s=s.replace(breakout,'');

must(
'  else if(cb==="prop:orders"||cb==="prop:risk")await sendText(env,"🏦 PROP\\\n\\\nChưa có account telemetry. Phần này sẽ hiển thị positions, pending orders, equity, daily P/L và risk sau khi kết nối.",chatId,propKeyboard());',
'  else if(cb==="prop:orders")await sendText(env,"📚 HYROTRADER • LỆNH\\\n\\\nChưa kết nối account nên chưa có positions/pending orders thật từ HyroTrader. LIVE ORDERS của Signal Hub hiện không được coi là lệnh HyroTrader cho tới khi có execution/account reconciliation.",chatId,propKeyboard());\n  else if(cb==="prop:risk")await sendText(env,"🛡️ HYROTRADER • RISK\\\n\\\nRisk shell đã tách riêng nhưng chưa có balance/equity/account limits thật. Chưa áp dụng auto-execution. Khi kết nối, đây sẽ là nơi kiểm daily loss, max loss, exposure, position risk và kill switch trước khi gửi lệnh.",chatId,propKeyboard());\n  else if(cb==="prop:connect")await sendText(env,"🔌 HYROTRADER • KẾT NỐI\\\n\\\nTrạng thái: NOT CONNECTED\\\nAuto trade: OFF\\\nBước sau mới nghiên cứu phương thức API/execution chính thức, xác nhận rule quỹ, credentials/secrets và account telemetry. Không nhập API key trực tiếp vào Telegram.",chatId,propKeyboard());',
'prop order risk handlers');

// status wording: make prop scope explicit without claiming connection
s=s.replace('Hub: ADAPTIVE + FRESH SCAN\\nCrypto: 61 symbol', 'Hub: ADAPTIVE + FRESH SCAN\\nProp: HYROTRADER ONLY • NOT CONNECTED • AUTO OFF\\nCrypto: 61 symbol');

fs.writeFileSync(p,s);
console.log('Applied V77.16.9 Hyro-only prop shell');