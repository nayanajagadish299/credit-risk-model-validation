#!/usr/bin/env python3
"""Update release checksums after reviewed source/documentation changes.

This tool does not change the scientific freeze manifest, the original cohort checksum,
or model artifacts. It lists only curated release paths, not raw data or Git internals.
"""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
MANIFEST=ROOT/'RELEASE_MANIFEST.json'
TEXT_EXTENSIONS={'.py','.json','.md','.csv','.txt','.gitignore','.yaml','.yml','.toml'}
TOP_FILES=['.gitignore','README.md','requirements.txt']
FOLDERS=['docs','figures','models','results','scripts','tools']

def canonical_bytes(p:Path)->bytes:
    data=p.read_bytes()
    if p.suffix.lower() in TEXT_EXTENSIONS or p.name=='.gitignore':
        return data.replace(b'\r\n',b'\n')
    return data

def safe_file(p:Path)->bool:
    return p.is_file() and not any(part in {'.git','__pycache__','.venv','venv'} for part in p.relative_to(ROOT).parts) and p.suffix.lower() not in {'.pyc','.pyo'}

def main():
    m=json.loads(MANIFEST.read_text(encoding='utf-8'))
    paths=[ROOT/name for name in TOP_FILES]
    for d in FOLDERS:
        folder=ROOT/d
        if folder.exists(): paths += [p for p in folder.rglob('*') if safe_file(p)]
    paths=sorted({p for p in paths if safe_file(p)},key=lambda p:p.relative_to(ROOT).as_posix())
    m['files']=[{
        'path':p.relative_to(ROOT).as_posix(),
        'bytes':len(raw:=canonical_bytes(p)),
        'sha256':hashlib.sha256(raw).hexdigest(),
    } for p in paths]
    m['review_status']='published_research_prototype_reproduction_gaps_disclosed'
    m['manifest_updated_at_utc']=datetime.now(timezone.utc).isoformat()
    m['checksum_policy']='LF-canonicalized text; raw bytes for binary assets'
    MANIFEST.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'Updated release manifest for {len(paths)} files; original model-freeze checksum preserved.')

if __name__=='__main__':main()
