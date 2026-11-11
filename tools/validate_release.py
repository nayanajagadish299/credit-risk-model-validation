#!/usr/bin/env python3
"""Static repository release preflight: no model loading, no loan-level data needed."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1]
MANIFEST=json.loads((ROOT/'results'/'task5e1_manifest.json').read_text(encoding='utf-8'))
issues=[]
if MANIFEST.get('all_expected_checks_pass') is not True:issues.append('Official model freeze QA not passed')
if MANIFEST.get('qa_checks',{}).get('no_loan_level_records_exported') is not True:issues.append('No-row-level check failed')
for a in MANIFEST['models']:
    f=ROOT/'models'/a['filename']
    if not f.is_file():issues.append('Missing model: '+a['filename']);continue
    actual=hashlib.sha256(f.read_bytes()).hexdigest()
    if actual!=a['sha256']:issues.append('Checksum mismatch: '+a['filename'])
for file in ROOT.rglob('*'):
    if not file.is_file():continue
    p=str(file.relative_to(ROOT)).lower().replace('\\','/')
    if file.suffix.lower() in ('.parquet','.feather','.xlsx','.xls','.sqlite','.db'):
        issues.append('Unexpected tabular/data file: '+p)
    if file.name.lower().startswith(('foia_','strict_train','strict_test','locked_test')):
        issues.append('Potential raw/cohort data: '+p)
    if file.stat().st_size>5_000_000:issues.append('Unexpected large file: '+p)
for needed in ('scripts/sba_task5d2_term_free_validation.py','scripts/sba_task5e1_model_freeze.py','docs/MODEL_CARD.md','docs/REPRODUCE.md'):
    if not (ROOT/needed).is_file():issues.append('Missing release file: '+needed)
print('Project A static release checks:', 'PASS' if not issues else 'FAIL')
for i in issues:print(' - '+i)
if not issues:print('Curated aggregate release and two frozen model files verified; human review still required.')
sys.exit(1 if issues else 0)
