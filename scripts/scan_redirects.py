#!/usr/bin/env python3
"""Static redirect-chain analysis: parses redirect rules from common config formats (no server
access, no network) and flags chains, loops, and unresolved targets. Anything not statically
parseable (a computed array, an unsupported config format) is reported as unavailable, never
silently treated as "no redirects"."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from seo_tools import _route_records, rel

def _norm(p):
    p=p.split('?',1)[0].split('#',1)[0]
    return '/'+p.strip('/') if p not in ('','/') else '/'

def parse_next_config(text,path):
    out=[]
    m=re.search(r'redirects\s*\(\s*\)\s*\{[^}]*?return\s*(\[.*?\])\s*;?\s*\}',text,re.S)
    if not m: return out,'computed' if 'redirects' in text else None
    body=m.group(1)
    for obj in re.finditer(r'\{([^{}]*)\}',body):
        seg=obj.group(1)
        src=re.search(r'source\s*:\s*[\'"]([^\'"]+)[\'"]',seg)
        dst=re.search(r'destination\s*:\s*[\'"]([^\'"]+)[\'"]',seg)
        perm=re.search(r'permanent\s*:\s*(true|false)',seg)
        if src and dst: out.append({'source':_norm(src.group(1)),'destination':dst.group(1),'permanent':perm.group(1)=='true' if perm else None,'file':path})
    return out,None

def parse_vercel_json(text,path):
    try: data=json.loads(text)
    except json.JSONDecodeError: return [],'invalid-json'
    out=[]
    for r in data.get('redirects',[]):
        if 'source' in r and 'destination' in r:
            out.append({'source':_norm(r['source']),'destination':r['destination'],'permanent':r.get('permanent',True),'file':path})
    return out,None

def parse_underscore_redirects(text,path):
    out=[]
    for n,line in enumerate(text.splitlines(),1):
        s=line.split('#',1)[0].strip()
        if not s: continue
        parts=s.split()
        if len(parts)>=2: out.append({'source':_norm(parts[0]),'destination':parts[1],'permanent':not (len(parts)>2 and parts[2].startswith('3') and parts[2]!='301' and parts[2]!='308'),'file':path,'line':n})
    return out,None

def parse_htaccess(text,path):
    out=[]
    for n,line in enumerate(text.splitlines(),1):
        s=line.strip()
        m=re.match(r'Redirect(?:Match)?\s+(?:(\d{3})\s+)?(\S+)\s+(\S+)',s,re.I)
        if m:
            code,src,dst=m.groups()
            out.append({'source':_norm(src),'destination':dst,'permanent':code in (None,'301','308'),'file':path,'line':n})
    return out,None

def parse_nginx(text,path):
    out=[]
    for n,line in enumerate(text.splitlines(),1):
        m=re.search(r'rewrite\s+(\S+)\s+(\S+)\s+permanent',line)
        if m: out.append({'source':_norm(m.group(1)),'destination':m.group(2),'permanent':True,'file':path,'line':n})
    return out,None

PARSERS=[('next.config.js',parse_next_config),('next.config.mjs',parse_next_config),('next.config.ts',parse_next_config),
         ('vercel.json',parse_vercel_json),('_redirects',parse_underscore_redirects),('.htaccess',parse_htaccess)]

def collect(root):
    rules=[]; unavailable=[]
    for name,parser in PARSERS:
        p=root/name
        if p.exists():
            out,note=parser(p.read_text(errors='ignore'),name)
            rules+=out
            if note: unavailable.append({'file':name,'reason':note})
    for p in root.rglob('netlify.toml'):
        text=p.read_text(errors='ignore')
        for block in re.finditer(r'\[\[redirects\]\](.*?)(?=\[\[|\Z)',text,re.S):
            seg=block.group(1)
            src=re.search(r'from\s*=\s*"([^"]+)"',seg); dst=re.search(r'to\s*=\s*"([^"]+)"',seg); code=re.search(r'status\s*=\s*(\d+)',seg)
            if src and dst: rules.append({'source':_norm(src.group(1)),'destination':dst.group(1),'permanent':(code.group(1) in ('301','308')) if code else True,'file':rel(p,root)})
    for p in root.rglob('*.conf'):
        if 'node_modules' in p.parts: continue
        out,_=parse_nginx(p.read_text(errors='ignore'),rel(p,root)); rules+=out
    for p in root.rglob('routeRules') if False else []: pass  # Nuxt routeRules / Astro redirects: computed config objects, not statically enumerable here
    if (root/'nuxt.config.ts').exists() or (root/'nuxt.config.js').exists():
        unavailable.append({'file':'nuxt.config.*','reason':'routeRules is a JS/TS object; not statically enumerated by this parser'})
    if (root/'astro.config.mjs').exists():
        unavailable.append({'file':'astro.config.mjs','reason':'redirects config is a JS object; not statically enumerated by this parser'})
    return rules,unavailable

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    rules,unavailable=collect(root)
    routes={r['route'] for r in _route_records(root)}
    by_source={}
    for r in rules: by_source.setdefault(r['source'],[]).append(r)
    fs=[]
    for src,rs in by_source.items():
        if len(rs)>1: fs.append({'severity':'MEDIUM','issue':f'Multiple redirect rules for the same source {src}; only the first matched by the host will apply.','sources':[r['file'] for r in rs]})
    def is_external(dst): return re.match(r'^[a-z][a-z0-9+.-]*://',dst,re.I) is not None
    # chain-follow, loop, and unresolved-target detection. `hops` counts every redirect jump
    # actually followed, starting from and including this rule itself (A->B is 1 hop, A->B->C
    # is 2 hops), so the plan's "chains of >=2 hops" threshold means 3 URLs total: A->B->C.
    for r in rules:
        seen=[r['source']]; cur=r['destination']; hops=1
        while not is_external(cur) and cur in by_source and hops<20:
            cur_norm=_norm(cur)
            if cur_norm in seen: fs.append({'severity':'CRITICAL','issue':f'Redirect loop starting at {r["source"]}.','file':r['file'],'chain':seen+[cur_norm]}); break
            seen.append(cur_norm); nxt=by_source[cur_norm][0]['destination']; cur=nxt; hops+=1
        else:
            if hops>=2: fs.append({'severity':'HIGH' if hops>=5 else 'MEDIUM','issue':f'Redirect chain of {hops} hop(s) from {r["source"]}; point directly at the final destination instead.','file':r['file'],'chain':seen+([cur] if not is_external(cur) else [cur])})
        if not is_external(r['destination']):
            dnorm=_norm(r['destination'])
            if dnorm not in routes and dnorm not in by_source: fs.append({'severity':'MEDIUM','issue':f'Redirect target {r["destination"]} does not resolve to a known route.','file':r['file']})
    observed=[{'source':r['source'],'destination':r['destination'],'file':r['file']} for r in rules]
    notes=[f'Parsed {len(rules)} redirect rule(s) across {len({r["file"] for r in rules})} file(s).']
    if unavailable: notes.append(f'{len(unavailable)} redirect source(s) could not be statically parsed: '+', '.join(u['file'] for u in unavailable)+'.')
    out={'tool':'scan-redirects','findings':fs,'observed':observed,'unavailable':unavailable,'notes':notes}
    print(json.dumps(out,indent=2))
    return 1 if any(f['severity'] in ('CRITICAL','HIGH') for f in fs) else 0
if __name__=='__main__': raise SystemExit(main())
