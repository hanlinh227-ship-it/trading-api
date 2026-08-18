const fs=require('fs');
const p='cloudflare-worker/index.js';
let s=fs.readFileSync(p,'utf8');
s=s.replaceAll('async function setNewsClearance(symbol,env){async function setNewsClearance(symbol,env){','async function setNewsClearance(symbol,env){');
s=s.replaceAll('function groupKeyboard(function groupKeyboard(group,run){','function groupKeyboard(group,run){');
s=s.replaceAll('async function sendGroup(group,env,chatId)async function sendGroup(group,env,chatId){','async function sendGroup(group,env,chatId){');
fs.writeFileSync(p,s);
console.log('Fixed V77.14 boundary marker duplication');
