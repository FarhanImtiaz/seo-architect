#!/usr/bin/env python3
"""Deterministically match winning-patterns.md cards against full_audit.py evidence.
Adds no new claims: it only points at patterns whose 'Applies when' signal is observed here."""
import json,re,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def load_audit(root):
    p=subprocess.run([sys.executable,str(HERE/'full_audit.py'),str(root),'--snapshot'],capture_output=True,text=True)
    try: return json.loads(p.stdout)
    except json.JSONDecodeError:
        print('ERROR: full_audit.py did not emit JSON',file=sys.stderr); sys.exit(2)

def signals(audit,root):
    checks=audit.get('checks',{})
    routes=checks.get('routes',{}).get('result',{}).get('findings',[])
    pages=audit.get('snapshot',{}).get('result',{}).get('snapshot',{}).get('pages',[])
    types=set()
    for p in pages: types.update(p.get('jsonldTypes',[]))
    config_path=root/'.claude/seo/config.json'
    config={}
    if config_path.exists():
        try: config=json.loads(config_path.read_text())
        except json.JSONDecodeError: pass
    route_paths=[r['route'] for r in routes]
    return {
        'dynamicRoutes':sum(1 for r in route_paths if '[dynamic]' in r),
        'totalRoutes':len(route_paths),
        'blogOrArticleRoutes':any(x in r.lower() for r in route_paths for x in ('blog','article','post')),
        'localBusinessSignals':'LocalBusiness' in types or bool(config.get('businessType')),
        'i18nDetected':bool(config.get('secondaryMarkets')) or bool(config.get('locale')) or any(re.search(r'\[(locale|lang)\]',r) for r in route_paths),
        'jsonldTypes':types,
        'analyticsAuthorized':bool(config.get('tracking',{}).get('analytics')),
        'contentAreaSize':len([r for r in route_paths if any(x in r.lower() for x in ('blog','article','post','guide'))]),
    }

RULES=[
    ('P01',lambda s: s['dynamicRoutes']>=1 and s['analyticsAuthorized']),
    ('P02',lambda s: True),  # rendering-mode risk applies whenever any route exists; presented only as a review-first reminder
    ('P03',lambda s: s['totalRoutes']>0),
    ('P04',lambda s: bool(s['jsonldTypes'])),
    ('P05',lambda s: s['contentAreaSize']>=5),
    ('P06',lambda s: s['blogOrArticleRoutes'] or s['contentAreaSize']>0),
    ('P06b',lambda s: s['contentAreaSize']>=5),
    ('P07',lambda s: s['analyticsAuthorized']),
    ('P08',lambda s: s['totalRoutes']>=3),
    ('P09',lambda s: s['dynamicRoutes']>=1),
    ('P10',lambda s: s['blogOrArticleRoutes']),
    ('P11',lambda s: s['totalRoutes']>0),
    ('P12',lambda s: s['localBusinessSignals']),
    ('P13',lambda s: s['totalRoutes']>0),
    ('P14',lambda s: False),  # only relevant to an active URL-migration request, not a general audit
    ('P15',lambda s: s['i18nDetected']),
]

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    audit=load_audit(root)
    s=signals(audit,root)
    matched=[]
    for pid,rule in RULES:
        try:
            if rule(s): matched.append(pid)
        except Exception: continue
    out={'tool':'pattern-match','signals':{k:(sorted(v) if isinstance(v,set) else v) for k,v in s.items()},'matched':matched,'note':'Deterministic signal match only; read the full pattern card in references/winning-patterns.md before citing it, and confirm the citation form.'}
    print(json.dumps(out,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
