#!/usr/bin/env python3
from pathlib import Path
p=Path('scripts/v11_symbol_backtest_4m.py')
s=p.read_text(encoding='utf-8')
s=s.replace('PASS requires >=80% win rate on VALIDATION, OOS and full 4-month window,','PASS requires >80% win rate on VALIDATION, OOS and full 4-month window,')
s=s.replace("if full['winRate'] < REQUIRED_WR: reasons.append('FULL_WR_BELOW_80')","if full['winRate'] <= REQUIRED_WR: reasons.append('FULL_WR_NOT_ABOVE_80')")
s=s.replace("if val['winRate'] < REQUIRED_WR: reasons.append('VALIDATION_WR_BELOW_80')","if val['winRate'] <= REQUIRED_WR: reasons.append('VALIDATION_WR_NOT_ABOVE_80')")
s=s.replace("if oos['winRate'] < REQUIRED_WR: reasons.append('OOS_WR_BELOW_80')","if oos['winRate'] <= REQUIRED_WR: reasons.append('OOS_WR_NOT_ABOVE_80')")
for needle in ["if full['winRate'] <= REQUIRED_WR", "if val['winRate'] <= REQUIRED_WR", "if oos['winRate'] <= REQUIRED_WR"]:
    if needle not in s: raise SystemExit('strict WR patch missing: '+needle)
p.write_text(s,encoding='utf-8')
print('STRICT_WR_PATCH=PASS')
