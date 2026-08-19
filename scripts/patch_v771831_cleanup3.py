from pathlib import Path
import re
p=Path('cloudflare-worker/engine-v77168.js'); s=p.read_text()
old='if(type==="index"){const k=INDEX CASH_KNOWLEDGE?.symbols?.[norm(symbol)];if(!k)return {applicable:true,available:false,key:norm(symbol)};return {applicable:true,available:true,key:norm(symbol),source:"INDEX CASH_KNOWLEDGE_V1",timeframe:"MULTI",status:"PRIOR_ONLY_UNCALIBRATED",family:k.profile,families:k.families||[],profile:k.profile,entryMode:"DYNAMIC",rr:null,signalHourUTC:null,riskATR:k.riskATR,newsProfile:{profileDrivers:k.drivers||[]},classification:INDEX CASH_KNOWLEDGE.classification};}'
new='if(type==="index"){const k=INDEX_PRIORS[norm(symbol)];if(!k)return {applicable:true,available:false,key:norm(symbol)};return {applicable:true,available:true,key:norm(symbol),source:"INDEX_CASH_PRIORS_R1",timeframe:"MULTI",status:"RUNTIME_METHOD_PRIOR",family:k.profile,families:k.families||[],profile:k.profile,entryMode:"DYNAMIC",rr:null,signalHourUTC:null,riskATR:k.riskATR,newsProfile:k.newsProfile||{profileDrivers:[]},classification:"INDEX_CASH_RUNTIME_PRIOR"};}'
if old in s:s=s.replace(old,new,1)
# No identifier may contain a space after migration.
s=s.replace('INDEX CASH_KNOWLEDGE','INDEX_PRIORS').replace('INDEX CASH_KNOWLEDGE_V1','INDEX_CASH_PRIORS_R1')
p.write_text(s)
print('CLEANUP3_OK')
