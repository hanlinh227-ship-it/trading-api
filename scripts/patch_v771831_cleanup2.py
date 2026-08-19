from pathlib import Path
import re
p=Path('cloudflare-worker/engine-v77168.js'); s=p.read_text()
# Remove the two remaining micro-futures rendering fragments robustly.
s,n1=re.subn(r';const fs=futureSizing\(w\.symbol,w\.planned\);if\(fs\)\{.*?\}\}if\(w\.method', '}if(w.method', s, count=1, flags=re.S)
s,n2=re.subn(r';const fs=futureSizing\(a\.symbol,a\.planned\);if\(fs\)\{.*?\}if\(a\.basisReference', ';if(a.basisReference', s, count=1, flags=re.S)
# Historical reason labels should not advertise removed Futures branch.
s=s.replace('FUTURE_RISK_LIMIT_REQUIRED:"SL cấu trúc vượt giới hạn risk micro",','').replace('MASSIVE_RATE_OR_DATA_UNAVAILABLE:"Massive đang giới hạn hoặc thiếu dữ liệu",','')
s=s.replace('NQ/MNQ/ES/MES','NAS100/US30/US500/DEX/JP225')
p.write_text(s)
print('CLEANUP2',n1,n2)
# trigger-final
