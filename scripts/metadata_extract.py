#!/usr/bin/env python3
"""Framework-aware metadata state per route: static (found), dynamic (computed at
runtime -- verify rendered, not a finding), or absent (a finding). Replaces loose
regex title/description matching, which false-positives on any JS object with a
title: key (component props, CMS objects)."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from seo_tools import files,rel,_route_records

LAYOUT_NAMES={'layout.tsx','layout.jsx','layout.ts','layout.js','+layout.svelte'}

def _ancestor_layouts(p,root):
    """Next.js/SvelteKit inherit metadata from every layout file above a route in the tree."""
    out=[]; d=p.parent
    while True:
        for name in LAYOUT_NAMES:
            f=d/name
            if f.exists() and f!=p: out.append(f)
        if d==root or root not in d.parents: break
        d=d.parent
    return out

def _classify(text,ancestor_texts):
    combined=text+''.join(ancestor_texts)
    if re.search(r'export\s+(?:async\s+)?function\s+generateMetadata\b',text): return 'dynamic','Next.js App Router generateMetadata'
    if re.search(r'export\s+const\s+metadata\s*=',combined): return 'static','Next.js App Router metadata export (own file or an ancestor layout)'
    if 'next/head' in text and re.search(r'<Head\b',text): return 'static','Next.js Pages Router <Head>'
    if re.search(r'react-helmet',text,re.I) and re.search(r'<Helmet\b',text): return 'static','React Helmet'
    if re.search(r'\buseSeoMeta\s*\(',text): return 'static','Nuxt useSeoMeta'
    if re.search(r'\buseHead\s*\(',text):
        return ('dynamic' if re.search(r'useHead\s*\(\s*\(\)\s*=>|useHead\s*\([^)]*computed\(',text) else 'static'),'Nuxt useHead'
    if re.search(r'\bdefinePageMeta\s*\(',text) and 'title' in text: return 'static','Nuxt definePageMeta'
    if re.search(r'<svelte:head>',combined,re.I): return 'static','SvelteKit <svelte:head> (own file or an ancestor +layout.svelte)'
    if re.search(r'<Layout\b[^>]*\btitle\s*=',text) or 'BaseHead' in text: return 'static','Astro <Layout title> or BaseHead'
    if re.search(r'export\s+(?:const|function|async\s+function)\s+meta\b',text): return 'dynamic' if re.search(r'export\s+(?:async\s+)?function\s+meta\b',text) else 'static','Remix meta export'
    if re.search(r'\bmetaInfo\s*\(',text): return 'static','Vue metaInfo'
    if re.search(r'<title[^>]*>[^<]+</title>',text,re.I): return 'static','static HTML <title>'
    return 'absent',None

def extract(root):
    results=[]
    for r in _route_records(root):
        p=root/r['file']
        if not p.exists(): continue
        text=p.read_text(errors='ignore')
        ancestor_texts=[f.read_text(errors='ignore') for f in _ancestor_layouts(p,root)]
        state,via=_classify(text,ancestor_texts)
        results.append({'route':r['route'],'file':r['file'],'state':state,'via':via})
    return results

def scan_built_dir(built_dir):
    """Opt-in: parse built HTML for title/description, and flag duplicate visible content
    across pages -- the P09 doorway-page uniqueness check on real rendered output."""
    from collections import Counter
    pages=[]
    for p in built_dir.rglob('*.html'):
        text=p.read_text(errors='ignore')
        title=re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S)
        visible=re.sub(r'<script\b.*?</script>|<style\b.*?</style>','',text,flags=re.I|re.S)
        visible=re.sub(r'<[^>]+>',' ',visible); visible=re.sub(r'\s+',' ',visible).strip()
        pages.append({'file':str(p.relative_to(built_dir)),'title':title.group(1).strip() if title else None,'contentHash':hash(visible[:2000])})
    counts=Counter(p['contentHash'] for p in pages)
    findings=[{'severity':'HIGH','file':p['file'],'issue':'This built page’s visible content is near-identical to another built page; template-generated pages must be unique per-page, not doorway pages.','rule':'duplicate-built-content'} for p in pages if counts[p['contentHash']]>1]
    return {'tool':'metadata-extract-built','pagesScanned':len(pages),'findings':findings,'notes':['Evidence labeled "build artifact": one fetched/parsed build at one time, not proof of the live deployed response.']}

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    built_dir_arg=None
    if '--built-dir' in sys.argv:
        idx=sys.argv.index('--built-dir')
        built_dir_arg=sys.argv[idx+1] if idx+1<len(sys.argv) else None
    if built_dir_arg:
        bd=Path(built_dir_arg).resolve()
        if not bd.is_dir(): print(f'ERROR: --built-dir does not exist: {bd}',file=sys.stderr); return 2
        out=scan_built_dir(bd); print(json.dumps(out,indent=2)); return 1 if out['findings'] else 0
    results=extract(root)
    absent=[r for r in results if r['state']=='absent']
    findings=[{'severity':'MEDIUM','file':r['file'],'issue':f'No static or recognized dynamic metadata source for route {r["route"]}.','rule':'metadata-absent'} for r in absent]
    out={'tool':'metadata-extract','routes':results,'findings':findings,'notes':['dynamic metadata is not a finding here -- it needs a rendered check (see --built-dir), not a static one.']}
    print(json.dumps(out,indent=2))
    return 1 if findings else 0
if __name__=='__main__': raise SystemExit(main())
