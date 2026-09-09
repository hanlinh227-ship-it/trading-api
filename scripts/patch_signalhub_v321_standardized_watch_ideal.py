from pathlib import Path
final_patch=Path('scripts/patch_signalhub_v321_final.py')
if not final_patch.exists():
    raise SystemExit('missing finalized V3.21 patch')
exec(compile(final_patch.read_text(),str(final_patch),'exec'))
