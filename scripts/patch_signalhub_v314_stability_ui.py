from pathlib import Path

p = Path('signalhub-android/app/src/main/java/com/hanlinh/signalhub/SignalHubActivity.java')
s = p.read_text(encoding='utf-8')

replacements = [
    ('private static final String APP_VERSION="3.13.0";', 'private static final String APP_VERSION="3.14.0";'),
    ('private static final long LIVE_REFRESH_MS=500L; // REST fallback; WebSocket is primary', 'private static final long LIVE_REFRESH_MS=1000L; // stable crypto REST cadence; background monitor is independent'),
    ('CRYPTO ONLY • SCALP ≠ SWING • REALTIME • V3.13', 'CRYPTO ONLY • SCALP ≠ SWING • REALTIME • V3.14'),
    ('subtitle.setText("CRYPTO REALTIME • SCALP / SWING • LIVE / LIMIT / STOP");', 'subtitle.setText("CRYPTO REALTIME • CHỌN SCALP HOẶC SWING • ENTRY / SL / TP");'),
    ('TextView pv=tv(fmt(px),21,CYAN,true);pv.setPadding(0,dp(8),0,0);c.addView(pv);', 'c.addView(tv("GIÁ LIVE",8,MUTED,true));TextView pv=tv(fmt(px),21,CYAN,true);pv.setPadding(0,dp(4),0,0);c.addView(pv);'),
    ('double px=priceFor(s,s.optDouble("entry",0));TextView pv=tv(fmt(px),29,TEXT,true);pv.setPadding(0,dp(10),0,dp(3));c.addView(pv);', 'double px=priceFor(s,s.optDouble("entry",0));c.addView(tv("GIÁ LIVE HIỆN TẠI",8,MUTED,true));TextView pv=tv(fmt(px),29,TEXT,true);pv.setPadding(0,dp(5),0,dp(3));c.addView(pv);'),
]

for old, new in replacements:
    if old not in s:
        raise SystemExit(f'missing expected V3.13 fragment: {old[:100]}')
    s = s.replace(old, new, 1)

# Keep the visual hierarchy explicit: selected style is a hard partition, not a mixed feed.
s = s.replace(
    'summary.addView(tv("SCALP / SWING độc lập • LIVE "+liveRows.size()+" • LIMIT "+limitRows.size()+" • STOP "+stopRows.size(),12,TEXT,true));',
    'summary.addView(tv("ĐANG XEM: "+style+" • KHÔNG TRỘN STYLE",12,CYAN,true));summary.addView(tv("LIVE "+liveRows.size()+" • LIMIT "+limitRows.size()+" • STOP "+stopRows.size(),11,TEXT,true));',
    1,
)

p.write_text(s, encoding='utf-8')
print('SignalHub V3.14 Activity stability/UI patch applied')
