#!/usr/bin/env python3
"""Per-page content freshness from git history: flags a page whose declared/visible "last
updated" date is newer than its actual last significant (non-whitespace-only, non-year-only)
change. Skipped entirely, with a note, when the project isn't a git repository."""
import json,re,subprocess,sys
from datetime import date,datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from seo_tools import files, rel

def _has_git(root):
    return (root/'.git').exists() or subprocess.run(['git','-C',str(root),'rev-parse','--is-inside-work-tree'],capture_output=True,text=True).returncode==0

def _last_significant_change(root,relpath):
    """Walks commit history for this file newest-first; the first commit whose diff has a
    non-trivial content change (not just whitespace, not just a bare 4-digit year swap) is the
    last significant change. Returns None if history/diff can't be read."""
    log=subprocess.run(['git','-C',str(root),'log','--follow','--format=%H %cI','--',relpath],capture_output=True,text=True)
    if log.returncode!=0 or not log.stdout.strip(): return None
    commits=[l.split(' ',1) for l in log.stdout.strip().splitlines()]
    for sha,when in commits:
        d=subprocess.run(['git','-C',str(root),'show',f'{sha}','--format=','--',relpath],capture_output=True,text=True)
        added=[l[1:] for l in d.stdout.splitlines() if l.startswith('+') and not l.startswith('+++')]
        removed=[l[1:] for l in d.stdout.splitlines() if l.startswith('-') and not l.startswith('---')]
        changed=[l for l in added+removed if l.strip()]
        non_trivial=[l for l in changed if not re.fullmatch(r'\s*\W*(19|20)\d{2}\W*\s*',l)]
        if non_trivial: return when
    return commits[-1][1] if commits else None

DATE_PATTERNS=[r'"dateModified"\s*:\s*"([^"]+)"',r'datetime=["\']([0-9]{4}-[0-9]{2}-[0-9]{2}[^"\']*)["\']',r'[Uu]pdated[:\s]+([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})']

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    if not _has_git(root):
        print(json.dumps({'tool':'scan-freshness','findings':[],'notes':['Not a git repository; freshness comparison needs commit history and was skipped.']},indent=2)); return 0
    fs=[]; checked=0
    for p in files(root):
        s=rel(p,root)
        if 'page.' not in s and '/pages/' not in s: continue
        text=p.read_text(errors='ignore')
        declared=None
        for pat in DATE_PATTERNS:
            m=re.search(pat,text)
            if m: declared=m.group(1); break
        if not declared: continue
        try:
            dt=datetime.fromisoformat(declared[:10])
        except ValueError: continue
        actual=_last_significant_change(root,s)
        checked+=1
        if actual is None: continue
        try: actual_dt=datetime.fromisoformat(actual[:10])
        except ValueError: continue
        if dt.date()>actual_dt.date():
            fs.append({'severity':'MEDIUM','issue':f'Declared "updated" date ({dt.date()}) is newer than the last significant content change found in git history ({actual_dt.date()}).','file':s,'rule':'freshness-date-mismatch'})
    print(json.dumps({'tool':'scan-freshness','findings':fs,'notes':[f'Checked {checked} page(s) with a declared update date against git history.']},indent=2))
    return 1 if any(f['severity'] in ('CRITICAL','HIGH') for f in fs) else 0
if __name__=='__main__': raise SystemExit(main())
