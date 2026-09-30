import assert from 'node:assert/strict';
import vm from 'node:vm';
import {EXNESS_LIVE_PAGE} from './exness-live-page.js';

const elements=new Map(),listeners={};
const element=id=>{if(!elements.has(id))elements.set(id,{textContent:'',className:'',dataset:{},append(){}});return elements.get(id)};
const document={hidden:false,getElementById:element,createElement:()=>({set innerHTML(_){this.children=Array.from({length:7},()=>({textContent:'',className:'',dataset:{}}))}}),addEventListener:(name,fn)=>{listeners[name]=fn}};
const sockets=[];
class FakeWebSocket{
  constructor(url){this.url=url;this.readyState=0;sockets.push(this)}
  close(){this.readyState=3;this.onclose?.({code:1006})}
}
const context={document,window:{addEventListener:(name,fn)=>{listeners[name]=fn}},location:{protocol:'https:',host:'example.test'},localStorage:{getItem:()=>null,setItem(){}},WebSocket:FakeWebSocket,performance:{now:()=>0},setInterval(){},setTimeout(){return 1},clearTimeout(){},requestAnimationFrame(){},Date,Intl,Map,Math,JSON,Number,String,Set};
const script=EXNESS_LIVE_PAGE.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(script);
vm.runInNewContext(script,context);
assert.equal(sockets.length,1,'initial page load opens one stream');
sockets[0].readyState=1;sockets[0].onopen?.();
listeners.online();
assert.equal(sockets.length,1,'online while an existing socket is open must not open a second upstream');

listeners.visibilitychange();
assert.equal(sockets.length,1,'visible event while socket is open must not open another upstream');

const old=sockets[0];
old.readyState=3;
listeners.online();
assert.equal(sockets.length,2,'after the first socket dies, online can start one replacement');
const newest=sockets[1];
old.onclose?.({code:1006});
listeners.online();
assert.equal(sockets.length,2,'late close from the old socket must not erase the replacement');
newest.close();
assert.match(element('status').textContent,/Mất kết nối/);
console.log('Exness live reconnect single-socket contract PASS');
