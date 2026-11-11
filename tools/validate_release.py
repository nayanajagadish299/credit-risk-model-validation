#!/usr/bin/env python3
"""Static release preflight. No model loading and no loan-level data needed."""
from pathlib import Path
import hashlib,json,sys

ROOT=Path(__file__).resolve().parents[1]
TEXT_EXTENSIONS={'.py','.json','.md','.csv','.txt','.gitignore','.yaml','.yml','.toml'}
issues=[]

def digest(p:Path):
    raw=p.read_bytes()
    if p.suffix.lower() in TEXT_EXTENSIONS or p.name=='.gitignore':
        raw=raw.replace(b'\r\n',b'\n')
    return hashlib.sha256(raw).hexdigest(),len(raw)

try:
    manifest=json.loads((ROOT/'results'/'task5e1_manifest.json').read_text(encoding='utf-8'))
except Exception as e:
    sys.exit('FAIL: missing or invalid scientific model-freeze manifest: '+str(e))
if manifest.get('all_expected_checks_pass') is not True: issues.append('Official model freeze QA not passed')
if manifest.get('qa_checks',{}).get('no_loan_level_records_exported') is not True: issues.append('No-row-level QA check failed')
for a in manifest['models']:
    f=ROOT/'models'/a['filename']
    if not f.is_file(): issues.append('Missing model: '+a['filename']);continue
    h=hashlib.sha256(f.read_bytes()).hexdigest()
    if h!=a['sha256']: issues.append('Frozen model SHA-256 mismatch: '+a['filename'])

try:
    publication=json.loads((ROOT/'RELEASE_MANIFEST.json').read_text(encoding='utf-8'))
except Exception as e:
    sys.exit('FAIL: invalid publication manifest: '+str(e))
seen=set()
for entry in publication.get('files',[]):
    rel=entry['path']
    if rel in seen:issues.append('Duplicate release manifest path: '+rel)
    seen.add(rel)
    file=ROOT/rel
    if not file.is_file():issues.append('Missing release path: '+rel);continue
    h,n=digest(file)
    if h!=entry['sha256'] or n!=entry['bytes']:
        issues.append('Publication checksum mismatch (run reviewed manifest refresh): '+rel)
for required in ('scripts/build_sba_cohort_enriched.py','scripts/sba_task5d2_term_free_validation.py','scripts/sba_task5e1_model_freeze.py','docs/MODEL_CARD.md','docs/REPRODUCE.md','tools/refresh_release_manifest.py'):
    if required not in seen:issues.append('Required release path not in manifest: '+required)

for f in ROOT.rglob('*'):
    if not f.is_file():continue
    rel=f.relative_to(ROOT)
    if any(part in {'.git','__pycache__','.venv','venv'} for part in rel.parts):continue
    p=rel.as_posix().lower()
    if f.suffix.lower() in ('.parquet','.feather','.xlsx','.xls','.sqlite','.db'):
        issues.append('Unexpected tabular file: '+p)
    if f.name.lower().startswith(('foia_','strict_train','strict_test','locked_test')):
        issues.append('Potential raw or loan-level data: '+p)
    if f.stat().st_size>5_000_000:issues.append('Unexpected large file: '+p)
print('Project A static release checks:', 'PASS' if not issues else 'FAIL')
for i in issues:print(' - '+i)
if not issues:print('Frozen models and curated release integrity verified; independent end-to-end reproduction still pending.')
sys.exit(1 if issues else 0)
