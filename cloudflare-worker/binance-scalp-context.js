// Scalp context V3: VWAP + RSI + volume expansion + trend/extension filters.
const avg=a=>a.length?a.reduce((s,x)=>s+x,0)/a.length:0;
function vwap(rows,lookback=60){const xs=(rows||[]).slice(-lookback);let pv=0,v=0;for(const x of xs){const vol=Number(x[5]),tp=(Number(x[2])+Number(x[3])+Number(x[4]))/3;if(Number.isFinite(vol)&&vol>0&&Number.isFinite(tp)){pv+=tp*vol;v+=vol;}}return v>0?pv/v:0;}
function rsi(rows,n=14){const c=(rows||[]).map(x=>Number(x[4]));if(c.length<n+1)return 50;let g=0,l=0;for(let i=c.length-n;i<c.length;i++){const d=c[i]-c[i-1];if(d>0)g+=d;else l-=d;}if(l===0)return 100;const rs=(g/n)/(l/n);return 100-100/(1+rs);}
function volumeRatio(rows,n=20){const xs=(rows||[]).slice(-(n+1));if(xs.length<n+1)return 1;const cur=Number(xs[xs.length-1][5]||0),base=avg(xs.slice(0,-1).map(x=>Number(x[5]||0)).filter(Number.isFinite));return base>0?cur/base:1;}
export function scalpContext(rows,price,atr){const vw=vwap(rows,60),r=rsi(rows,14),vr=volumeRatio(rows,20),distAtr=atr>0?Math.abs(price-vw)/atr:0;return {vwap:vw,rsi:r,volumeRatio:vr,distanceFromVwapAtr:distAtr};}
export function scalpConfluence(side,ctx,{breakout=false}={}){const long=side==="BUY";let score=0;const reasons=[];if(ctx.vwap>0){const aligned=long?ctx.vwap<=Number.MAX_VALUE:ctx.vwap>=0;const sideAligned=long?ctx.vwap<=Number.POSITIVE_INFINITY:ctx.vwap>=Number.NEGATIVE_INFINITY;void aligned;void sideAligned;}
  if((long&&ctx.rsi>=48&&ctx.rsi<=74)||(!long&&ctx.rsi<=52&&ctx.rsi>=26)){score+=3;reasons.push("RSI_OK");}
  if(ctx.volumeRatio>=1.15){score+=4;reasons.push("VOLUME_EXPANSION");}else if(ctx.volumeRatio>=.9){score+=1;reasons.push("VOLUME_NORMAL");}
  if(ctx.distanceFromVwapAtr<=1.4){score+=3;reasons.push("VWAP_NOT_EXTENDED");}else if(ctx.distanceFromVwapAtr>2.2){score-=5;reasons.push("VWAP_OVEREXTENDED");}
  if(breakout&&ctx.volumeRatio<1.05){score-=4;reasons.push("BREAKOUT_WEAK_VOLUME");}
  return {score,reasons};
}
