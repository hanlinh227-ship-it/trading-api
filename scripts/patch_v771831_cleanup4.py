from pathlib import Path
p=Path('cloudflare-worker/engine-v77168.js'); s=p.read_text()
s=s.replace('x.push("Δ "+fmtPx(dist)+);','x.push("Δ "+fmtPx(dist));')
p.write_text(s)
print('CLEANUP4_OK')
