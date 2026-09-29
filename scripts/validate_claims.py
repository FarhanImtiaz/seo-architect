#!/usr/bin/env python3
"""Scans .claude/seo/ markdown and generated reports for outcome language ("increased traffic",
"will rank", a bare percentage near clicks/traffic/rankings, "guarantee") that isn't backed by a
citation to an impact/ result or an evidence-ledger entry. Advisory only -- surfaced as guardian
context, never a block; see scripts/guardian_hook.py."""
import argparse,json,re,sys
from pathlib import Path

OUTCOME_PATTERNS=[
    re.compile(r'\b(increase[sd]?|improve[sd]?|boost(?:ed|s)?|grow|grew|drove|driving)\b[^.\n]{0,40}\b(traffic|clicks|impressions|rankings?|conversions?|revenue|sales)\b',re.I),
    re.compile(r'\bwill\s+(rank|increase|improve|boost|drive)\b',re.I),
    re.compile(r'\bguarantee[ds]?\b',re.I),
    re.compile(r'\b\d+(\.\d+)?%\s*(more|increase|higher|lift|gain)\b',re.I),
    re.compile(r'\b(traffic|clicks|impressions|rankings?)\b[^.\n]{0,20}\bup\s+\d+(\.\d+)?%',re.I),
]
CITATION_PATTERN=re.compile(r'\bimpact/[\w.\-]+\.json\b|\bevidence(?:-ledger)?\b[^.\n]{0,30}#?\d+|\bsee\s+impact\b',re.I)

def scan_text(text):
    findings=[]
    for pattern in OUTCOME_PATTERNS:
        for m in pattern.finditer(text):
            window=text[max(0,m.start()-150):m.end()+150]
            if not CITATION_PATTERN.search(window): findings.append({'match':m.group(0),'context':window.strip()})
    return findings

def scan_paths(root,paths):
    results=[]
    for rel in paths:
        p=root/rel
        if not p.exists() or not p.is_file(): continue
        findings=scan_text(p.read_text(errors='ignore'))
        if findings: results.append({'file':str(p.relative_to(root)),'findings':findings})
    return results

def main():
    q=argparse.ArgumentParser(); q.add_argument('project',nargs='?',default='.'); q.add_argument('--file',action='append',default=[]); a=q.parse_args()
    root=Path(a.project).resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    targets=a.file or [str(p.relative_to(root)) for p in (root/'.claude/seo').glob('*.md')] if (root/'.claude/seo').exists() else a.file
    results=scan_paths(root,targets)
    print(json.dumps({'tool':'validate-claims','filesFlagged':len(results),'results':results,'note':'Advisory: outcome language without a nearby citation to an impact/ result or evidence-ledger entry. Not proof anything is wrong -- confirm the claim is backed by real data or soften the language.'},indent=2))
    return 1 if results else 0
if __name__=='__main__': raise SystemExit(main())
