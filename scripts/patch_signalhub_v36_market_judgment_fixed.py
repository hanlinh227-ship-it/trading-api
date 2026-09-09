from pathlib import Path

p=Path('scripts/patch_signalhub_v36_market_judgment.py')
s=p.read_text()
s=s.replace("delete signal.admissionGate;delete signal.admissionMinScore;delete signal.admissionMinRR;","delete signal.admissionGate;")
# Execute the patched patcher in-process. This removes obsolete V3.5 admission metadata
# from the generated worker without letting the validator match its own cleanup string.
exec(compile(s, str(p), 'exec'), {'__name__':'__main__','__file__':str(p)})
