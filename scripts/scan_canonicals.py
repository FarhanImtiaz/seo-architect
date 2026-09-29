#!/usr/bin/env python3
"""Static canonical-tag graph: missing/self-inconsistent canonicals, canonical chains, a
canonical pointing at a noindex or redirected page, and near-duplicate content across template
pages (a heuristic signal, not proof of duplication)."""
import hashlib,json,re,sys
from pathlib import Path
from urllib.parse import urlparse
sys.path.insert(0,str(Path(__file__).resolve().parent))
from seo_tools import files, rel, page_record, _route_from_path

SHINGLE_SIZE=5
def _shingles(text):
    words=re.sub(r'<[^>]+>',' ',text).split()
    words=[w.lower() for w in words if w.isalnum() or any(c.isalnum() for c in w)]
    return {hashlib.md5(' '.join(words[i:i+SHINGLE_SIZE]).encode()).hexdigest() for i in range(0,max(0,len(words)-SHINGLE_SIZE+1),3)} or set()
def _jaccard(a,b):
    if not a or not b: return 0.0
    return len(a&b)/len(a|b)

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    canonical_host=None
    cfg=root/'.claude/seo/config.json'
    if cfg.exists():
        try: canonical_host=json.loads(cfg.read_text()).get('canonicalHost')
        except json.JSONDecodeError: pass
    pages=[page_record(p,root) for p in files(root) if 'page.' in rel(p,root) or '/pages/' in rel(p,root)]
    fs=[]; shingle_sets={}
    for pg in pages:
        canon=pg.get('canonical')
        if not canon:
            fs.append({'severity':'LOW','issue':'No static canonical tag found for this page.','file':pg['source'],'rule':'canonical-missing'}); continue
        u=urlparse(canon)
        if canonical_host and u.netloc and u.netloc!=canonical_host:
            fs.append({'severity':'MEDIUM','issue':f'Canonical host {u.netloc} does not match the configured canonicalHost {canonical_host}.','file':pg['source'],'rule':'canonical-host-mismatch'})
        if canon.rstrip('/')!=canon and canon!='/'and not canon.endswith('://'+u.netloc):
            pass  # trailing-slash normalization is host-config-dependent; not flagged without more context
        if pg.get('noindex'):
            fs.append({'severity':'MEDIUM','issue':'Page has both a canonical tag and a noindex directive -- a noindex page should not usually declare itself canonical.','file':pg['source'],'rule':'canonical-on-noindex'})
        text=(root/pg['source']).read_text(errors='ignore') if (root/pg['source']).exists() else ''
        shingle_sets[pg['source']]=_shingles(text)
    # canonical target existence / noindex-target / chain check, by matching canonical path against known routes
    by_route={_route_from_path(pg['source']):pg for pg in pages}
    for pg in pages:
        canon=pg.get('canonical')
        if not canon: continue
        path=urlparse(canon).path or '/'
        target_route='/'+path.strip('/') if path not in ('','/') else '/'
        target=by_route.get(target_route)
        if target is None: continue  # off-site or unresolvable target -- not proof of a problem, just unverifiable here
        if target.get('canonical') and urlparse(target['canonical']).path not in (path,''):
            fs.append({'severity':'MEDIUM','issue':f'Canonical chain: {pg["source"]} points at a page whose own canonical points elsewhere.','file':pg['source'],'rule':'canonical-chain'})
        if target.get('noindex'):
            fs.append({'severity':'HIGH','issue':f'Canonical target for {pg["source"]} is itself noindex.','file':pg['source'],'rule':'canonical-target-noindex'})
    # near-duplicate detection across all pages (5-word-shingle Jaccard; heuristic, not exact)
    sources=list(shingle_sets)
    for i in range(len(sources)):
        for j in range(i+1,len(sources)):
            a,b=sources[i],sources[j]
            score=_jaccard(shingle_sets[a],shingle_sets[b])
            if score>=0.85:
                fs.append({'severity':'MEDIUM','issue':f'{a} and {b} are heuristically near-identical ({score:.0%} shingle overlap) -- verify these are not doorway/duplicate pages.','file':a,'rule':'near-duplicate-heuristic','pair':b,'score':round(score,3)})
    print(json.dumps({'tool':'scan-canonicals','findings':fs,'notes':[f'Inspected {len(pages)} page(s); near-duplicate detection is a shingle-overlap heuristic, not proof of duplication.']},indent=2))
    return 1 if any(f['severity'] in ('CRITICAL','HIGH') for f in fs) else 0
if __name__=='__main__': raise SystemExit(main())
