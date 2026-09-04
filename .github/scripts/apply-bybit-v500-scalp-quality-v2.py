from pathlib import Path

src_path=Path('.github/scripts/apply-bybit-v500-scalp-quality.py')
src=src_path.read_text()
bad="s = rep(s, \"BYBIT-MULTI-STATEFLOW-4.9.0\", \"BYBIT-MULTI-STATEFLOW-5.0.0\", 'config version')\n"
if bad not in src:
    raise SystemExit('V500_BASE_PATCH_UNEXPECTED')
src=src.replace(bad,'',1)
exec(compile(src,str(src_path),'exec'),{'__name__':'__main__'})
