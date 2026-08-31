#!/usr/bin/env python3
"""Dependency-free, conservative static SEO inspection for local projects."""
from __future__ import annotations
import hashlib, json, re, sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

SKIP={'.git','node_modules','.next','dist','build','vendor','.venv','__pycache__'}
TEXT={'.html','.htm','.jsx','.tsx','.js','.ts','.vue','.svelte','.astro','.mdx'}
def files(root, suffixes=TEXT):
    return [p for p in root.rglob('*') if p.is_file() and p.suffix.lower() in suffixes and not any(x in SKIP for x in p.parts)]
def emit(kind, items, notes=[]):
    print(json.dumps({'tool':kind,'findings':items,'notes':notes},indent=2)); return 1 if any(x.get('severity') in ('CRITICAL','HIGH') for x in items) else 0
def rel(p, root): return str(p.relative_to(root))
def route_scan(root):
    patterns=[('Next app','app/**/page.*'),('Next pages','pages/**/*.{js,jsx,ts,tsx}'),('Astro','src/pages/**/*'),('SvelteKit','src/routes/**/*')]
    found=[]
    for p in files(root):
        s=rel(p,root)
        if re.search(r'(^|/)(app/(?:.*/)?page|pages/.+|src/pages/.+|src/routes/.+)',s) or p.name in ('page.tsx','page.jsx','page.js','page.ts','page.html'):
            route='/' + re.sub(r'(^.*?/(?:app|pages|src/pages|src/routes)/|/page\.[^.]+$|\.[^.]+$)','',s).strip('/')
            route=re.sub(r'\[(?:\.\.\.)?[^]]+\]','[dynamic]',route) or '/'
            found.append({'route':route,'file':s})
    if not found: return emit('scan-routes',[],['No conventional route files found; framework may be unsupported or routes may be dynamic.'])
    return emit('scan-routes',found,[f'Found {len(found)} conventionally discoverable route files.'])
def metadata(root):
    findings=[]; titles=[]; desc=[]; seen=files(root)
    for p in seen:
        text=p.read_text(errors='ignore'); path=rel(p,root)
        title=re.findall(r'<title[^>]*>(.*?)</title>|title\s*:\s*[`\'\"]([^`\'\"]+)',text,re.I|re.S)
        description=re.findall(r'(?:name=["\']description["\'][^>]*content=["\']([^"\']+)|description\s*:\s*[`\'\"]([^`\'\"]+))',text,re.I)
        likely=('page.' in path or '/pages/' in path or '/app/' in path or '<head' in text.lower())
        if likely and not title: findings.append({'severity':'MEDIUM','file':path,'issue':'No statically detectable title.'})
        if likely and not description: findings.append({'severity':'LOW','file':path,'issue':'No statically detectable meta description.'})
        titles += [(x[0] or x[1]).strip() for x in title]; desc += [(x[0] or x[1]).strip() for x in description]
        if '<html' in text.lower() and not re.search(r'rel=["\']canonical["\']|canonical\s*:',text,re.I): findings.append({'severity':'LOW','file':path,'issue':'No static canonical link found.'})
        if '<html' in text.lower() and len(re.findall(r'<h1\b',text,re.I)) != 1: findings.append({'severity':'LOW','file':path,'issue':'HTML page has zero or multiple H1 elements.'})
    for label, values in [('title',titles),('description',desc)]:
        for value,count in Counter(values).items():
            if value and count>1: findings.append({'severity':'MEDIUM','issue':f'Duplicate {label}: {value[:100]}','count':count})
    return emit('scan-metadata',findings,[f'Inspected {len(seen)} text source files; dynamic metadata may not be detectable.'])
def sitemap(root):
    paths=list(root.rglob('sitemap*.xml'))
    if not paths:return emit('validate-sitemap',[],['No sitemap XML found; it may be generated dynamically or absent.'])
    fs=[]
    for p in paths:
        try:
            tree=ET.parse(p); urls=[n.text.strip() for n in tree.findall('.//{*}loc') if n.text]
            if not urls: fs.append({'severity':'HIGH','file':rel(p,root),'issue':'Sitemap has no <loc> URLs.'})
            for u in urls:
                x=urlparse(u)
                if x.scheme not in ('http','https') or not x.netloc: fs.append({'severity':'HIGH','file':rel(p,root),'issue':f'Invalid absolute URL: {u}'})
        except ET.ParseError as e: fs.append({'severity':'CRITICAL','file':rel(p,root),'issue':f'Invalid XML: {e}'})
    return emit('validate-sitemap',fs,[f'Validated {len(paths)} sitemap file(s).'])
def robots(root):
    paths=list(root.rglob('robots.txt'))
    if not paths:return emit('validate-robots',[],['No robots.txt found; it may be generated dynamically or absent.'])
    fs=[]
    for p in paths:
        active=False
        for n,line in enumerate(p.read_text(errors='ignore').splitlines(),1):
            x=line.split('#',1)[0].strip()
            if not x:continue
            if ':' not in x: fs.append({'severity':'MEDIUM','file':rel(p,root),'line':n,'issue':'Malformed directive.'});continue
            key,val=[z.strip() for z in x.split(':',1)]; low=key.lower()
            if low=='user-agent':active=True
            elif low=='disallow' and val=='/' and active:fs.append({'severity':'HIGH','file':rel(p,root),'line':n,'issue':'Disallows all crawling for a declared user agent.'})
            elif low not in {'user-agent','allow','disallow','sitemap','crawl-delay','host'}:fs.append({'severity':'LOW','file':rel(p,root),'line':n,'issue':f'Unknown directive: {key}'})
    return emit('validate-robots',fs,[f'Validated {len(paths)} robots file(s); directives are not a guarantee of index behavior.'])
def jsonld(root):
    fs=[]; count=0
    for p in files(root):
        text=p.read_text(errors='ignore')
        for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',text,re.I|re.S):
            count+=1
            try:
                obj=json.loads(match.group(1).strip())
                values=obj if isinstance(obj,list) else [obj]
                for x in values:
                    if not isinstance(x,dict) or '@context' not in x or '@type' not in x: fs.append({'severity':'MEDIUM','file':rel(p,root),'issue':'JSON-LD should be an object with @context and @type.'})
            except json.JSONDecodeError as e:fs.append({'severity':'HIGH','file':rel(p,root),'issue':f'Invalid JSON-LD: {e.msg}'})
    return emit('validate-jsonld',fs,[f'Parsed {count} static JSON-LD block(s); this does not validate eligibility or visible-content alignment.'])
def links(root):
    fs=[]; checked=0
    for p in files(root):
        text=p.read_text(errors='ignore')
        for href in re.findall(r'(?:href|to)=["\']([^"\']+)',text,re.I):
            if not href.startswith('/') or href.startswith('//') or '{' in href: continue
            checked+=1
            clean=href.split('#',1)[0].split('?',1)[0].rstrip('/') or '/'
            candidates=[root/'public'/clean.lstrip('/'),root/(clean.lstrip('/')+'.html'),root/'app'/clean.strip('/')/'page.tsx',root/'pages'/(clean.strip('/')+'.tsx')]
            if not any(x.exists() for x in candidates): fs.append({'severity':'LOW','file':rel(p,root),'issue':f'Could not resolve local internal link: {href}'})
    return emit('scan-links',fs,[f'Checked {checked} static root-relative links; framework routing and dynamic links may be unresolved.'])
def page_record(p,root):
    text=p.read_text(errors='ignore'); title=re.search(r'<title[^>]*>(.*?)</title>|title\s*:\s*[`\'\"]([^`\'\"]+)',text,re.I|re.S); desc=re.search(r'(?:name=["\']description["\'][^>]*content=["\']([^"\']+)|description\s*:\s*[`\'\"]([^`\'\"]+))',text,re.I)
    canon=re.search(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',text,re.I)
    return {'source':rel(p,root),'hash':hashlib.sha256(text.encode()).hexdigest()[:16],'title':(title.group(1) or title.group(2)).strip() if title else None,'description':(desc.group(1) or desc.group(2)).strip() if desc else None,'canonical':canon.group(1) if canon else None,'h1Count':len(re.findall(r'<h1\b',text,re.I)),'jsonldTypes':sorted(set(re.findall(r'"@type"\s*:\s*"([^"\n]+)',text))), 'internalLinkCount':len(re.findall(r'(?:href|to)=["\']/+',text,re.I))}
def snapshot(root):
    routes=[]; pages=[]
    for p in files(root):
        t=p.read_text(errors='ignore');
        if 'page.' in rel(p,root) or '/pages/' in rel(p,root): routes.append(rel(p,root)); pages.append(page_record(p,root))
    sitemaps=[]
    for p in root.rglob('sitemap*.xml'):
        try:sitemaps += [n.text.strip() for n in ET.parse(p).findall('.//{*}loc') if n.text]
        except ET.ParseError:pass
    data={'version':2,'routes':sorted(routes),'pages':sorted(pages,key=lambda x:x['source']),'sitemapUrls':sorted(sitemaps),'robotsPresent':bool(list(root.rglob('robots.txt'))),'jsonldBlocks':sum(len(re.findall(r'application/ld\+json',p.read_text(errors='ignore'),re.I)) for p in files(root))}
    target=root/'.claude/seo/baseline.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(data,indent=2)+'\n');print(json.dumps({'tool':'seo-regression','action':'snapshot','file':str(target),'snapshot':data},indent=2));return 0
def regression(root):
    baseline=root/'.claude/seo/baseline.json'
    if not baseline.exists():return emit('seo-regression',[],['No baseline at .claude/seo/baseline.json. Run `seo_regression.py snapshot .` first.'])
    old=json.loads(baseline.read_text()); tmp=root/'.claude/seo/.current.json';
    # calculate without persisting a baseline replacement
    current_files=[p for p in files(root) if 'page.' in rel(p,root) or '/pages/' in rel(p,root)]; routes=sorted([rel(p,root) for p in current_files]); current={x['source']:x for x in (page_record(p,root) for p in current_files)}
    fs=[]
    missing=sorted(set(old.get('routes',[]))-set(routes))
    if missing: fs.append({'severity':'HIGH','issue':'Previously discovered route files are missing; review URL migration/redirects.','paths':missing})
    if old.get('robotsPresent') and not list(root.rglob('robots.txt')):fs.append({'severity':'HIGH','issue':'robots.txt disappeared since baseline.'})
    for prior in old.get('pages',[]):
        now=current.get(prior['source'])
        if not now: continue
        for key in ('title','description','canonical','h1Count','jsonldTypes'):
            if prior.get(key)!=now.get(key): fs.append({'severity':'MEDIUM','issue':f'Page SEO property changed: {key}','file':prior['source'],'before':prior.get(key),'after':now.get(key),'action':'Review intent, visible content, and migration record if applicable.'})
    return emit('seo-regression',fs,['Comparison is static and conservative; inspect intended route changes and runtime-generated assets.'])
def main():
    if len(sys.argv)<3: print('Usage: seo_tools.py <routes|metadata|sitemap|robots|jsonld|links|snapshot|compare> <project>');return 2
    command,root=sys.argv[1],Path(sys.argv[2]).resolve()
    if not root.is_dir():print(f'ERROR: project directory does not exist: {root}',file=sys.stderr);return 2
    handlers={'routes':route_scan,'metadata':metadata,'sitemap':sitemap,'robots':robots,'jsonld':jsonld,'links':links,'snapshot':snapshot,'compare':regression}
    if command not in handlers: print(f'ERROR: unknown command: {command}',file=sys.stderr); return 2
    return handlers[command](root)
if __name__=='__main__':
    try: raise SystemExit(main())
    except (OSError,PermissionError) as e: print(f'ERROR: {e}',file=sys.stderr); raise SystemExit(2)
