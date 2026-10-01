#!/usr/bin/env python3
"""Response-vs-render diff: compares --response (server/build HTML, what a crawler gets before
JS runs) against an optional --rendered (a user-supplied post-JS DOM dump). Without --rendered,
only compares source/build output against itself and says so -- it never claims to know what
JavaScript changes at runtime without real rendered evidence."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from seo_tools import page_record

def _load(path):
    p=Path(path)
    if p.is_file(): return {p.name:p}
    return {str(f.relative_to(p)):f for f in p.rglob('*') if f.is_file() and f.suffix in ('.html','.htm')}

def main():
    import argparse
    q=argparse.ArgumentParser(); q.add_argument('--response',required=True); q.add_argument('--rendered')
    a=q.parse_args()
    resp=_load(a.response)
    if not resp: print(json.dumps({'tool':'render-diff','findings':[],'notes':[f'No HTML files found under --response {a.response}.']},indent=2)); return 0
    fs=[]
    if not a.rendered:
        for name,p in resp.items():
            text=p.read_text(errors='ignore')
            if re.search(r'<meta[^>]+noindex',text,re.I): fs.append({'severity':'INFO','file':name,'issue':'Response HTML contains noindex -- per Google, a noindex found in the initial response means rendering is skipped entirely for this page.'})
        print(json.dumps({'tool':'render-diff','findings':fs,'notes':['No --rendered input given; only compared response/build HTML against itself for a noindex-skips-rendering signal. Pass --rendered (a post-JS DOM dump) to compare what changes after JavaScript runs.']},indent=2)); return 0
    rend=_load(a.rendered); checked=0; unmatched=[]
    for name,rp in resp.items():
        # Full relative-path match ONLY -- a basename-only fallback used to pair unrelated files
        # (e.g. response "blog/index.html" with a rendered root "index.html" just because both
        # happen to be named "index.html"), producing false findings on two different pages.
        matched=rend.get(name)
        if not matched:
            unmatched.append(name); continue
        checked+=1
        rtext=rp.read_text(errors='ignore'); dtext=matched.read_text(errors='ignore')
        r_canon=re.search(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',rtext,re.I)
        d_canon=re.search(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',dtext,re.I)
        if (r_canon.group(1) if r_canon else None)!=(d_canon.group(1) if d_canon else None):
            fs.append({'severity':'HIGH','file':name,'issue':f'Canonical differs between response ({r_canon.group(1) if r_canon else None}) and rendered ({d_canon.group(1) if d_canon else None}) HTML.'})
        r_title=re.search(r'<title[^>]*>(.*?)</title>',rtext,re.I|re.S); d_title=re.search(r'<title[^>]*>(.*?)</title>',dtext,re.I|re.S)
        if (r_title.group(1).strip() if r_title else None)!=(d_title.group(1).strip() if d_title else None):
            fs.append({'severity':'MEDIUM','file':name,'issue':'Title differs between response and rendered HTML.'})
        if re.search(r'<meta[^>]+noindex',rtext,re.I):
            fs.append({'severity':'INFO','file':name,'issue':'Response HTML has noindex; Google skips rendering in this case, so any rendered-only content below is unseen by Google regardless of this diff.'})
        r_links=set(re.findall(r'<a[^>]+href=["\']([^"\']+)',rtext,re.I)); d_links=set(re.findall(r'<a[^>]+href=["\']([^"\']+)',dtext,re.I))
        render_only_links=d_links-r_links
        if render_only_links: fs.append({'severity':'MEDIUM','file':name,'issue':f'{len(render_only_links)} link(s) exist only after rendering, not in the initial response -- these depend on JavaScript execution to be crawlable.','links':sorted(render_only_links)[:20]})
        r_ld=len(re.findall(r'application/ld\+json',rtext,re.I)); d_ld=len(re.findall(r'application/ld\+json',dtext,re.I))
        if d_ld>r_ld: fs.append({'severity':'MEDIUM','file':name,'issue':f'{d_ld-r_ld} JSON-LD block(s) exist only after rendering.'})
        r_words=len(re.sub(r'<[^>]+>',' ',rtext).split()); d_words=len(re.sub(r'<[^>]+>',' ',dtext).split())
        if d_words>0 and r_words<d_words*0.5: fs.append({'severity':'LOW','file':name,'issue':f'Response HTML has {r_words} words vs. {d_words} rendered -- most content depends on JavaScript.'})
    notes=[f'Compared {checked} matched file(s) between --response and --rendered (matched by identical relative path only, never by basename alone).']
    if unmatched: notes.append(f'{len(unmatched)} response file(s) had no same-relative-path match under --rendered and were skipped, not guessed at: {sorted(unmatched)[:20]}')
    print(json.dumps({'tool':'render-diff','findings':fs,'notes':notes},indent=2))
    return 1 if any(f['severity'] in ('CRITICAL','HIGH') for f in fs) else 0
if __name__=='__main__': raise SystemExit(main())
