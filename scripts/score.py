#!/usr/bin/env python3
"""Reproducible category scoring from full_audit.py evidence. Never invents a number: a
category with no supporting evidence is excluded from the score, not scored zero."""
import argparse,json,re,subprocess,sys
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

HERE=Path(__file__).resolve().parent
RUBRIC=json.loads((HERE/'rubric.json').read_text())
RUBRIC_HASH=__import__('hashlib').sha256((HERE/'rubric.json').read_bytes()).hexdigest()[:12]

def load_audit(root,from_json):
    if from_json:
        text=sys.stdin.read() if from_json=='-' else Path(from_json).read_text()
        return json.loads(text)
    p=subprocess.run([sys.executable,str(HERE/'full_audit.py'),str(root),'--snapshot'],capture_output=True,text=True)
    try: return json.loads(p.stdout)
    except json.JSONDecodeError:
        print('ERROR: full_audit.py did not emit JSON:\n'+p.stderr,file=sys.stderr); sys.exit(2)

def result_of(audit,key): return audit.get('checks',{}).get(key,{}).get('result',{})
def findings_of(audit,key): return result_of(audit,key).get('findings',[])
def notes_of(audit,key): return ' '.join(result_of(audit,key).get('notes',[]))

def state_completeness(root):
    """Returns the list of .claude/seo state files that are still template-stub-only."""
    stubs=[]
    for name in ('strategy.md','keywords.md'):
        f=root/'.claude/seo'/name
        if not f.exists(): stubs.append(name); continue
        lines=f.read_text().splitlines(); out=[]; i=0
        while i<len(lines):
            s=lines[i].strip()
            if not s or s.startswith('#') or s.startswith('<!--'): i+=1; continue
            if s.startswith('|') and i+1<len(lines) and re.match(r'^\|[\s:|-]+\|$',lines[i+1].strip()): i+=2; continue
            if re.match(r'^-\s*[A-Za-z0-9 /()]+:\s*$',s): i+=1; continue
            out.append(s); i+=1
        if not out: stubs.append(name)
    return stubs

def parse_keyword_targets(root):
    f=root/'.claude/seo/keywords.md'
    if not f.exists(): return []
    lines=[l for l in f.read_text().splitlines() if l.strip().startswith('|')]
    if len(lines)<3: return []
    header=[c.strip().lower() for c in lines[0].strip('|').split('|')]
    if 'target url' not in header: return []
    idx=header.index('target url'); targets=[]
    for row in lines[2:]:
        cells=[c.strip() for c in row.strip('|').split('|')]
        if len(cells)>idx and cells[idx] and cells[idx] not in ('-','--'): targets.append(cells[idx])
    return targets

def ratio_check(id_,points,mode,pass_count,total):
    if total==0: return {'id':id_,'points':points,'mode':mode,'applicable':False,'earned':None,'ratio':None}
    r=pass_count/total
    return {'id':id_,'points':points,'mode':mode,'applicable':True,'earned':round(points*r,2),'ratio':round(r,3)}

def binary_check(id_,points,mode,applicable,passed):
    if not applicable: return {'id':id_,'points':points,'mode':mode,'applicable':False,'earned':None,'ratio':None}
    return {'id':id_,'points':points,'mode':mode,'applicable':True,'earned':points if passed else 0.0,'ratio':1.0 if passed else 0.0}

UNAVAILABLE_REASONS={
    'robots-not-blocking-all':('No robots.txt found in the project.','Add a robots.txt file, then re-run the audit.'),
    'sitemap-valid-absolute':('No sitemap XML found in the project.','Add a sitemap*.xml file, then re-run the audit.'),
    'sitemap-covers-routes':('No sitemap XML found in the project.','Add a sitemap*.xml file, then re-run the audit.'),
    'no-routes-missing-vs-baseline':('No regression baseline exists yet.','Run `seo_tools.py snapshot .` once, then re-run the audit after future changes.'),
    'orphan-ratio':('No link graph has been built yet.','Run `seo_tools.py graph .` (or `full_audit.py`, which calls it) to build .claude/seo/link-graph.json.'),
    'click-depth-ratio':('No link graph has been built yet.','Run `seo_tools.py graph .` to build .claude/seo/link-graph.json.'),
    'keyword-targets-resolve':('.claude/seo/keywords.md has no "Target URL" column with rows yet.','Fill in keywords.md with target URLs, then re-run the audit.'),
    'no-unresolved-internal-links':('No root-relative internal links were found to check.','Add internal navigation links, then re-run the audit.'),
    'no-orphans':('No link graph has been built yet.','Run `seo_tools.py graph .` to build .claude/seo/link-graph.json.'),
    'generic-anchor-ratio':('No internal link anchors were found via the link graph.','Run `seo_tools.py graph .`, then re-run the audit.'),
    'jsonld-parses':('No JSON-LD structured data was found.','Add JSON-LD structured data where it visibly applies, then re-run the audit.'),
    'required-properties-present':('No typed JSON-LD (with an @type) was found.','Add JSON-LD structured data where it visibly applies, then re-run the audit.'),
    'org-or-website-on-home':('No home-page file was identified.','Confirm the project has a discoverable home route, then re-run the audit.'),
    'visible-content-alignment':('No typed JSON-LD (with an @type) was found.','Add JSON-LD structured data where it visibly applies, then re-run the audit.'),
    'no-zero-business-potential-clusters':('No matching evidence-ledger entry was attested via --attest.','Add an evidence-ledger entry for this claim and pass --attest no-zero-business-potential-clusters=<index>.'),
    'schema-visible-alignment':('No matching evidence-ledger entry was attested via --attest.','Add an evidence-ledger entry for this claim and pass --attest schema-visible-alignment=<index>.'),
}
def unavailable(id_,points,mode): return {'id':id_,'points':points,'mode':mode,'applicable':False,'earned':None,'ratio':None}

def attested_check(id_,points,mode,attest,root):
    key=id_
    if key not in attest: return unavailable(id_,points,mode)
    ledger=root/'.claude/seo/evidence.json'
    try: entries=json.loads(ledger.read_text()).get('entries',[])
    except (OSError,json.JSONDecodeError): entries=[]
    idx=attest[key]
    passed=0<=idx<len(entries) and entries[idx].get('status')=='active'
    return {'id':id_,'points':points,'mode':mode,'applicable':True,'earned':points if passed else 0.0,'ratio':1.0 if passed else 0.0}

def norm_path(x):
    x=urlparse(x).path if '://' in x else x
    x=x.rstrip('/'); return x or '/'

def score_technical(audit,pages,routes,sitemap_urls):
    out=[]
    robots_notes=notes_of(audit,'robots'); robots_findings=findings_of(audit,'robots')
    if 'No robots.txt found' in robots_notes: out.append(unavailable('robots-not-blocking-all',4,'binary'))
    else: out.append(binary_check('robots-not-blocking-all',4,'binary',True,not any(f['severity']=='HIGH' for f in robots_findings)))
    sitemap_notes=notes_of(audit,'sitemap'); sitemap_findings=findings_of(audit,'sitemap')
    if 'No sitemap XML found' in sitemap_notes: out.append(unavailable('sitemap-valid-absolute',3,'binary')); out.append(unavailable('sitemap-covers-routes',3,'ratio'))
    else:
        out.append(binary_check('sitemap-valid-absolute',3,'binary',True,not any(f['severity'] in ('HIGH','CRITICAL') for f in sitemap_findings)))
        route_paths={norm_path(r['route']) for r in routes}
        sitemap_paths={norm_path(u) for u in sitemap_urls}
        covered=len(route_paths & sitemap_paths)
        out.append(ratio_check('sitemap-covers-routes',3,'ratio',covered,len(route_paths)))
    out.append(ratio_check('canonical-present-ratio',4,'ratio',sum(1 for p in pages if p.get('canonical')),len(pages)))
    out.append(ratio_check('no-noindex-on-sitemap-routes',3,'ratio',sum(1 for p in pages if not p.get('noindex')),len(pages)))
    regr_notes=notes_of(audit,'regression')
    if 'No baseline' in regr_notes: out.append(unavailable('no-routes-missing-vs-baseline',3,'binary'))
    else: out.append(binary_check('no-routes-missing-vs-baseline',3,'binary',True,not any('missing' in f.get('issue','').lower() for f in findings_of(audit,'regression'))))
    return out

def _link_graph(root):
    f=root/'.claude/seo/link-graph.json'
    if not f.exists(): return None
    try: return json.loads(f.read_text())
    except json.JSONDecodeError: return None

def score_ia(audit,pages,routes,root):
    out=[]
    graph=_link_graph(root)
    if graph:
        depth=graph.get('depth',{}); orphans=set(graph.get('orphans',[]))
        all_routes=list(depth.keys())
        out.append(ratio_check('orphan-ratio',4,'ratio',len(all_routes)-len(orphans),len(all_routes)))
        within3=sum(1 for v in depth.values() if v is not None and v<=3)
        out.append(ratio_check('click-depth-ratio',4,'ratio',within3,len(all_routes)))
    else:
        out.append(unavailable('orphan-ratio',4,'ratio')); out.append(unavailable('click-depth-ratio',4,'ratio'))
    file_route={r['file']:r['route'] for r in routes}
    nested=[p for p in pages if norm_path(file_route.get(p['source'],'/')).count('/')>1]
    out.append(ratio_check('breadcrumbs-on-nested-routes',2,'ratio',sum(1 for p in nested if 'BreadcrumbList' in p.get('jsonldTypes',[])),len(nested)))
    return out

def score_onpage(pages):
    out=[]
    titled=[p for p in pages if p.get('title')]
    out.append(ratio_check('title-present',4,'ratio',len(titled),len(pages)))
    counts=Counter(p['title'] for p in titled)
    out.append(ratio_check('titles-unique',3,'ratio',sum(1 for p in titled if counts[p['title']]==1),len(titled)))
    described=[p for p in pages if p.get('description')]
    out.append(ratio_check('description-present',2,'ratio',len(described),len(pages)))
    dcounts=Counter(p['description'] for p in described)
    out.append(ratio_check('descriptions-unique',2,'ratio',sum(1 for p in described if dcounts[p['description']]==1),len(described)))
    out.append(ratio_check('single-h1',2,'ratio',sum(1 for p in pages if p.get('h1Count')==1),len(pages)))
    out.append(ratio_check('title-length-range',2,'ratio',sum(1 for p in titled if 15<=len(p['title'])<=65),len(titled)))
    return out

def score_content(root,pages,attest):
    out=[]
    stubs=state_completeness(root)
    out.append(binary_check('strategy-keywords-not-stub',3,'binary',True,not stubs))
    routes_files=[p['source'] for p in pages]
    targets=parse_keyword_targets(root)
    if targets:
        resolved=sum(1 for t in targets if any(t.rstrip('/') in f or f.endswith(t.strip('/')) for f in routes_files) or t=='/')
        out.append(ratio_check('keyword-targets-resolve',3,'ratio',resolved,len(targets)))
    else: out.append(unavailable('keyword-targets-resolve',3,'ratio'))
    out.append(ratio_check('thin-content-ratio',3,'ratio',sum(1 for p in pages if p.get('wordCount',0)>=150),len(pages)))
    hashes=Counter(p['hash'] for p in pages)
    out.append(ratio_check('no-duplicate-template-text',3,'ratio',sum(1 for p in pages if hashes[p['hash']]==1),len(pages)))
    out.append(attested_check('no-zero-business-potential-clusters',3,'attested',attest,root))
    return out

def score_links(audit,root):
    out=[]
    notes=notes_of(audit,'links'); m=re.search(r'Checked (\d+)',notes)
    checked=int(m.group(1)) if m else 0
    findings=findings_of(audit,'links')
    if checked: out.append(ratio_check('no-unresolved-internal-links',4,'ratio',max(checked-len(findings),0),checked))
    else: out.append(unavailable('no-unresolved-internal-links',4,'ratio'))
    graph=_link_graph(root)
    if graph:
        depth=graph.get('depth',{}); orphans=set(graph.get('orphans',[]))
        all_routes=list(depth.keys())
        out.append(ratio_check('no-orphans',3,'ratio',len(all_routes)-len(orphans),len(all_routes)))
        graph_findings=findings_of(audit,'graph')
        anchor_findings=[f for f in graph_findings if f.get('rule')=='generic-anchor']
        total_anchors=sum(len(v) for v in graph.get('anchorsByTarget',{}).values())
        if total_anchors: out.append(ratio_check('generic-anchor-ratio',3,'ratio',max(total_anchors-len(anchor_findings),0),total_anchors))
        else: out.append(unavailable('generic-anchor-ratio',3,'ratio'))
    else:
        out.append(unavailable('no-orphans',3,'ratio')); out.append(unavailable('generic-anchor-ratio',3,'ratio'))
    return out

def score_schema(audit,pages):
    out=[]
    notes=notes_of(audit,'jsonld'); m=re.search(r'Parsed (\d+)',notes)
    total=int(m.group(1)) if m else 0
    invalid=sum(1 for f in findings_of(audit,'jsonld') if f['severity'] in ('HIGH','CRITICAL') and 'Invalid JSON-LD' in f.get('issue',''))
    if total: out.append(ratio_check('jsonld-parses',3,'ratio',max(total-invalid,0),total))
    else: out.append(unavailable('jsonld-parses',3,'ratio'))
    required=[f for f in findings_of(audit,'jsonld') if f.get('rule')=='missing-required']
    typed_pages=[p for p in pages if p.get('jsonldTypes')]
    if typed_pages: out.append(ratio_check('required-properties-present',4,'ratio',len(typed_pages)-len({f.get('file') for f in required}),len(typed_pages)))
    else: out.append(unavailable('required-properties-present',4,'ratio'))
    home=[p for p in pages if norm_path(p['source'])=='/'] or [p for p in pages if p['source'] in ('app/page.html','index.html')]
    if home: out.append(binary_check('org-or-website-on-home',1,'binary',True,any(t in home[0].get('jsonldTypes',[]) for t in ('Organization','WebSite'))))
    else: out.append(unavailable('org-or-website-on-home',1,'binary'))
    alignment=[f for f in findings_of(audit,'jsonld') if f.get('rule')=='visible-alignment']
    if typed_pages: out.append(ratio_check('visible-content-alignment',2,'ratio',len(typed_pages)-len(alignment),len(typed_pages)))
    else: out.append(unavailable('visible-content-alignment',2,'ratio'))
    return out

def _latest_measurement(root,source):
    d=root/'.claude/seo/measurement'
    if not d.exists(): return None
    matches=sorted(d.glob(f'*-{source}.json'))
    if not matches: return None
    try: return json.loads(matches[-1].read_text())
    except json.JSONDecodeError: return None

def _crux_good_density_ratio(crux_payload):
    """Average 'good' bucket density across CrUX's Core Web Vitals metrics, when present."""
    rows=crux_payload.get('rows') or [{}]
    metrics=rows[0]
    good=[]
    for key in ('largest_contentful_paint','cumulative_layout_shift','interaction_to_next_paint','first_contentful_paint'):
        m=metrics.get(key)
        if not m: continue
        for h in m.get('histogram',[]):
            if h.get('start') in (0,0.0) or h.get('density') is not None and h is m.get('histogram',[None])[0]:
                good.append(h.get('density',0)); break
    return sum(good)/len(good) if good else None

def score_performance(audit,root):
    crux=_latest_measurement(root,'crux')
    if crux:
        ratio=_crux_good_density_ratio(crux)
        if ratio is not None:
            return [{'id':'field-data-core-web-vitals','points':5,'mode':'ratio','applicable':True,'earned':round(5*ratio,2),'ratio':round(ratio,3),'source':'CrUX field data (overrides static image proxies per references/scoring-rubric.md)'}]
    img=result_of(audit,'images')
    if not img: return [unavailable('images-have-dimensions',2,'ratio'),unavailable('no-lazy-load-on-first-image',1,'ratio'),unavailable('image-weight-ok',2,'ratio')]
    findings=img.get('findings',[])
    # M1 fix: a site with zero images must be reported as unavailable (no evidence), never as a
    # perfect 5/5 -- `total=... or 1` previously forced a fake denominator of 1 with 0 findings,
    # which ratio_check() then scored as a flawless 1.0 ratio. Passing the real total (0 when
    # there are no images) lets ratio_check()'s own total==0 guard mark it unavailable instead.
    total=img.get('totalImages',0)
    dims=sum(1 for f in findings if f.get('rule')=='missing-dimensions')
    lazy=sum(1 for f in findings if f.get('rule')=='lazy-first-image')
    weight=sum(1 for f in findings if f.get('rule')=='oversized')
    return [ratio_check('images-have-dimensions',2,'ratio',max(total-dims,0),total),
            ratio_check('no-lazy-load-on-first-image',1,'ratio',max(total-lazy,0) if lazy<=total else 0,total),
            ratio_check('image-weight-ok',2,'ratio',max(total-weight,0),total)]

PHONE=re.compile(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b')
def score_local(root,pages,routes):
    types=set()
    for p in pages: types.update(p.get('jsonldTypes',[]))
    phones=set()
    for p in pages:
        f=root/p['source']
        if f.exists(): phones.update(PHONE.findall(f.read_text(errors='ignore')))
    signal=('LocalBusiness' in types) or bool(phones)
    if not signal: return None
    out=[]
    out.append(binary_check('nap-consistency',2,'binary',True,len(phones)<=1))
    out.append(binary_check('localbusiness-schema-with-address',2,'binary',True,'LocalBusiness' in types))
    out.append(binary_check('contact-route-exists',1,'binary',True,any('contact' in r['route'].lower() for r in routes)))
    return out

def score_aeo(audit,attest,root):
    aeo_pages=result_of(audit,'aeo').get('pages',[])
    out=[]
    out.append(ratio_check('direct-answer-signal',3,'ratio',sum(1 for p in aeo_pages if p['signals'].get('questionHeading') or p['signals'].get('definition')),len(aeo_pages)))
    out.append(ratio_check('author-or-org-identity',2,'ratio',sum(1 for p in aeo_pages if p['signals'].get('authorOrOrganization')),len(aeo_pages)))
    out.append(ratio_check('date-signal',2,'ratio',sum(1 for p in aeo_pages if p['signals'].get('date')),len(aeo_pages)))
    out.append(attested_check('schema-visible-alignment',3,'attested',attest,root))
    return out

def score_platform(audit):
    """Rubric v2: a detected non-framework-code platform (Shopify/WordPress/Webflow/headless CMS/
    SSG) with real `unavailable[]` content gaps lowers coveragePct, the same honesty model the
    framework-code adapters already apply. Not applicable (excluded, not scored zero) when no
    such platform is detected at all -- this never penalizes an ordinary framework-code project."""
    result=result_of(audit,'platforms')
    detected=result.get('detected') or []
    if not detected: return None
    platforms=result.get('platforms',{})
    fully_visible=sum(1 for name in detected if not (platforms.get(name,{}).get('unavailable') or []))
    return [ratio_check('platform-content-visible',5,'ratio',fully_visible,len(detected))]

def compute(root,audit,attest):
    pages=audit.get('snapshot',{}).get('result',{}).get('snapshot',{}).get('pages',[])
    sitemap_urls=audit.get('snapshot',{}).get('result',{}).get('snapshot',{}).get('sitemapUrls',[])
    routes=findings_of(audit,'routes')
    categories={
        'technical':score_technical(audit,pages,routes,sitemap_urls),
        'ia':score_ia(audit,pages,routes,root),
        'onpage':score_onpage(pages),
        'content':score_content(root,pages,attest),
        'links':score_links(audit,root),
        'schema':score_schema(audit,pages),
        'performance':score_performance(audit,root),
        'local':score_local(root,pages,routes),
        'aeo':score_aeo(audit,attest,root),
        'platform':score_platform(audit),
    }
    out={'rubricVersion':RUBRIC['version'],'rubricHash':RUBRIC_HASH,'categories':{},'label':RUBRIC['label']}
    total_earned=0.0; total_applicable_max=0.0; total_declared_max=0.0; unavailable_checks=[]
    for name,checks in categories.items():
        declared_max=RUBRIC['categories'][name]['max']; total_declared_max+=declared_max
        if checks is None: out['categories'][name]={'status':'unavailable','declaredMax':declared_max}; continue
        for c in checks:
            c['evidenceMix']=_evidence_mix(c)
            if not c['applicable']:
                reason,how=UNAVAILABLE_REASONS.get(c['id'],(f'No evidence was available for check "{c["id"]}" in this audit run.',f'Re-run the audit after adding the relevant source (see references/scoring-rubric.md, check "{c["id"]}").'))
                unavailable_checks.append({'id':c['id'],'category':name,'reason':reason,'howToUnlock':how})
        applicable=[c for c in checks if c['applicable']]
        if not applicable: out['categories'][name]={'status':'unavailable','declaredMax':declared_max,'checks':checks}; continue
        earned=sum(c['earned'] for c in applicable); applicable_max=sum(c['points'] for c in applicable)
        total_earned+=earned; total_applicable_max+=applicable_max
        out['categories'][name]={'status':'evidenced','declaredMax':declared_max,'applicableMax':applicable_max,'earned':round(earned,2),'checks':checks}
    out['score']=round(100*total_earned/total_applicable_max,1) if total_applicable_max else None
    out['evidencedMax']=round(total_applicable_max,2)
    out['coveragePct']=round(100*total_applicable_max/total_declared_max,1) if total_declared_max else 0.0
    out['unavailableChecks']=unavailable_checks
    return out

def _evidence_mix(check):
    if check.get('mode')=='attested': return 'attested'
    src=str(check.get('source') or '')
    if 'CrUX' in src or 'field data' in src.lower(): return 'field-data'
    return 'source-static'

def append_history(root,out):
    hist=root/'.claude/seo/audit-history.json'
    data={'version':1,'entries':[]}
    if hist.exists():
        try: data=json.loads(hist.read_text())
        except json.JSONDecodeError: pass
    data['entries'].append({'date':str(date.today()),'rubricHash':out['rubricHash'],'score':out['score'],'coveragePct':out['coveragePct']})
    hist.parent.mkdir(parents=True,exist_ok=True); hist.write_text(json.dumps(data,indent=2)+'\n')

def main():
    q=argparse.ArgumentParser(); q.add_argument('project',nargs='?',default='.'); q.add_argument('--from-json'); q.add_argument('--attest',action='append',default=[]); a=q.parse_args()
    root=Path(a.project).resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    attest={}
    for spec in a.attest:
        if '=' not in spec: print(f'ERROR: --attest must be checkId=ledgerIndex, got {spec}',file=sys.stderr); return 2
        k,v=spec.split('=',1)
        try: attest[k]=int(v)
        except ValueError: print(f'ERROR: ledger index must be an integer: {v}',file=sys.stderr); return 2
    audit=load_audit(root,a.from_json)
    out=compute(root,audit,attest)
    append_history(root,out)
    print(json.dumps(out,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
