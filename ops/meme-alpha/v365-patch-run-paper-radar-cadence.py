from pathlib import Path
import sys
p=Path(sys.argv[1]);s=p.read_text()
needle='/usr/bin/node /opt/meme-alpha/app/src/new-listing-radar.js >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1 || echo "NEW_LISTING_RADAR_CYCLE_FAILED rc=$?" >> /opt/meme-alpha/app/runtime-status/new-listing-radar-runtime.log 2>&1'
pos=s.find(needle)
if pos<0: raise SystemExit('RADAR_COMMAND_NOT_FOUND')
start=pos+len(needle)
segment=s[start:start+120]
if 'sleep 6' in segment:
    print('V365_RADAR_CADENCE_ALREADY_6S=TRUE')
else:
    for old in ('sleep 1','sleep 3','sleep 5'):
        j=s.find(old,start,start+120)
        if j>=0:
            s=s[:j]+'sleep 6'+s[j+len(old):]
            p.write_text(s)
            print('V365_RADAR_CADENCE_PATCHED=TRUE')
            break
    else: raise SystemExit('RADAR_SLEEP_PATTERN_NOT_FOUND')
