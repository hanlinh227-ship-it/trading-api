from pathlib import Path
p=Path('cloudflare-worker/engine-v77168.js'); s=p.read_text()
s=s.replace('if(mt)L.push(`Geometry: ${mt}`)if(a.basisReference)','if(mt)L.push(`Geometry: ${mt}`);if(a.basisReference)')
p.write_text(s)
print('CLEANUP5_OK')
