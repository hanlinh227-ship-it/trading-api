// V78-012 — shared ATR primitive only.
// EMA and RSI intentionally remain local: their current implementations are not semantically equivalent.
export function atrFromHLC(c,n=14){if(c.length<n+1)return null;const tr=[];for(let i=1;i<c.length;i++){const hi=c[i].high??c[i].h,lo=c[i].low??c[i].l,pc=c[i-1].close??c[i-1].c;tr.push(Math.max(hi-lo,Math.abs(hi-pc),Math.abs(lo-pc)));}return tr.slice(-n).reduce((a,b)=>a+b,0)/n;}
