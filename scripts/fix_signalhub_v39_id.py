from pathlib import Path
p=Path('signalhub-worker/gateway-v3.js')
s=p.read_text()
old="id=`V38-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`"
new="id=`V39-${market}-${style}-${setup.symbol}-${Date.now().toString(36)}`"
if old not in s:
    raise SystemExit('V3.8 signal ID template not found after V3.9 patch')
s=s.replace(old,new,1)
p.write_text(s)
print('fixed SignalHub V3.9 signal ID template')
