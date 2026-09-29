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
def emit(kind, items, notes=None):
    notes=notes or []
    print(json.dumps({'tool':kind,'findings':items,'notes':notes},indent=2)); return 1 if any(x.get('severity') in ('CRITICAL','HIGH') for x in items) else 0
def rel(p, root): return str(p.relative_to(root))
def _route_from_path(s):
    """Strips a leading app/pages/src-pages/src-routes prefix, then a trailing page.<ext> filename,
    as two sequential passes so a project-root page (e.g. 'app/page.html') resolves to '/' rather than
    leaving a stray 'page' segment behind (that stray segment surfaces when the prefix has no path
    before it, since a single combined regex pass can't re-match against its own just-stripped text)."""
    s2=re.sub(r'^(?:.*/)?(?:app/routes|app|pages|src/pages|src/routes)/','',s,count=1)
    s3=re.sub(r'(^|/)\+?page\.[^.]+$','',s2,count=1)
    s3=re.sub(r'\.[^.]+$','',s3,count=1)
    route='/' + s3.strip('/')
    return re.sub(r'\[(?:\.\.\.)?[^]]+\]','[dynamic]',route) or '/'
def _route_records(root):
    found=[]
    for p in files(root):
        s=rel(p,root)
        if re.search(r'(^|/)(app/(?:.*/)?page|pages/.+|src/pages/.+|src/routes/.+|app/routes/.+)',s) or p.name in ('page.tsx','page.jsx','page.js','page.ts','page.html'):
            found.append({'route':_route_from_path(s),'file':s})
    return found
def route_scan(root):
    found=_route_records(root)
    if not found: return emit('scan-routes',[],['No conventional route files found; framework may be unsupported or routes may be dynamic.'])
    return emit('scan-routes',found,[f'Found {len(found)} conventionally discoverable route files.'])
METADATA_CONTEXT=re.compile(r'metadata|useHead|useSeoMeta|generateMetadata|<Head\b|Helmet|seoMeta',re.I)
def _scoped_matches(pattern,text):
    out=[]
    for m in re.finditer(pattern,text,re.I|re.S):
        tag=m.group(1)
        if tag is not None: out.append(tag); continue
        if METADATA_CONTEXT.search(text[max(0,m.start()-200):m.start()]): out.append(m.group(2))
    return out
def metadata(root):
    findings=[]; titles=[]; desc=[]; seen=files(root)
    for p in seen:
        text=p.read_text(errors='ignore'); path=rel(p,root)
        title=_scoped_matches(r'<title[^>]*>(.*?)</title>|title\s*:\s*[`\'\"]([^`\'\"]+)',text)
        description=_scoped_matches(r'name=["\']description["\'][^>]*content=["\']([^"\']+)|description\s*:\s*[`\'\"]([^`\'\"]+)',text)
        likely=('page.' in path or '/pages/' in path or '/app/' in path or '<head' in text.lower())
        if likely and not title: findings.append({'severity':'MEDIUM','file':path,'issue':'No statically detectable title.'})
        if likely and not description: findings.append({'severity':'LOW','file':path,'issue':'No statically detectable meta description.'})
        titles += [x.strip() for x in title]; desc += [x.strip() for x in description]
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
def _schema_rules():
    p=Path(__file__).resolve().parent/'schema_rules.json'
    return json.loads(p.read_text()).get('types',{}) if p.exists() else {}
def _walk_typed_nodes(obj):
    """Yield every dict carrying an @type, recursing through @graph, lists, and nested objects (Offer inside Product, etc.)."""
    if isinstance(obj,dict):
        if '@type' in obj: yield obj
        for v in obj.values(): yield from _walk_typed_nodes(v)
    elif isinstance(obj,list):
        for v in obj: yield from _walk_typed_nodes(v)
def _type_names(node):
    t=node.get('@type')
    if isinstance(t,list): return [x for x in t if isinstance(x,str)]
    return [t] if isinstance(t,str) else []
def _visible_text(text):
    v=re.sub(r'<script\b.*?</script>|<style\b.*?</style>',' ',text,flags=re.I|re.S)
    return re.sub(r'<[^>]+>',' ',v)
def jsonld(root):
    rules=_schema_rules(); fs=[]; count=0
    for p in files(root):
        text=p.read_text(errors='ignore'); path=rel(p,root); visible=_visible_text(text)
        for match in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',text,re.I|re.S):
            count+=1
            try: obj=json.loads(match.group(1).strip())
            except json.JSONDecodeError as e: fs.append({'severity':'HIGH','file':path,'issue':f'Invalid JSON-LD: {e.msg}','rule':'invalid-json'}); continue
            for top in (obj if isinstance(obj,list) else [obj]):
                if not isinstance(top,dict) or '@context' not in top or ('@type' not in top and '@graph' not in top):
                    fs.append({'severity':'MEDIUM','file':path,'issue':'JSON-LD should be an object with @context and @type or @graph.','rule':'malformed'}); continue
                for node in _walk_typed_nodes(top):
                    for type_name in _type_names(node):
                        rule=rules.get(type_name)
                        if not rule:
                            fs.append({'severity':'INFO','file':path,'issue':f'Unrecognized @type "{type_name}"; not in the schema-rules registry, review manually.','rule':'unknown-type','type':type_name}); continue
                        required_severity='INFO' if rule.get('deprecated') else 'HIGH'
                        for field in rule.get('googleRequired',[]):
                            if field not in node: fs.append({'severity':required_severity,'file':path,'issue':f'{type_name} is missing required property "{field}" ({rule["docUrl"]}).','rule':'missing-required','type':type_name,'field':field})
                        for field in rule.get('googleRecommended',[]):
                            if field not in node: fs.append({'severity':'LOW','file':path,'issue':f'{type_name} is missing recommended property "{field}".','rule':'missing-recommended','type':type_name,'field':field})
                        if rule.get('volatile'): fs.append({'severity':'INFO','file':path,'issue':f'{type_name}: {rule.get("notes") or "Google eligibility for this type has changed before; verify current policy."}','rule':'volatile','type':type_name})
                        if type_name=='Product' and not any(k in node for k in ('offers','review','aggregateRating')):
                            fs.append({'severity':'HIGH','file':path,'issue':'Product has none of offers/review/aggregateRating; Google requires at least one of these for rich-result eligibility.','rule':'missing-required','type':type_name,'field':'offers|review|aggregateRating'})
                        if type_name=='Product' and isinstance(node.get('aggregateRating'),dict):
                            rv=str(node['aggregateRating'].get('ratingValue',''))
                            if rv and rv not in visible: fs.append({'severity':'MEDIUM','file':path,'issue':f'aggregateRating.ratingValue ({rv}) is not visible in this file’s rendered text; never assert unsupported schema.','rule':'visible-alignment','type':type_name,'field':'aggregateRating.ratingValue'})
                        if type_name=='Product' and isinstance(node.get('offers'),dict):
                            price=str(node['offers'].get('price',''))
                            if price and price not in visible: fs.append({'severity':'MEDIUM','file':path,'issue':f'offers.price ({price}) is not visible in this file’s rendered text.','rule':'visible-alignment','type':type_name,'field':'offers.price'})
                        if type_name=='LocalBusiness' and isinstance(node.get('address'),dict):
                            parts=[str(v) for k,v in node['address'].items() if k in ('streetAddress','addressLocality','postalCode') and v]
                            if parts and not any(part in visible for part in parts): fs.append({'severity':'MEDIUM','file':path,'issue':'LocalBusiness address is not visible in this file’s rendered text.','rule':'visible-alignment','type':type_name,'field':'address'})
        if re.search(r'dangerouslySetInnerHTML',text) and re.search(r'JSON\.stringify',text) and 'application/ld+json' in text:
            fs.append({'severity':'INFO','file':path,'issue':'JSON-LD appears to be built dynamically (dangerouslySetInnerHTML + JSON.stringify); validate the rendered output, not just source.','rule':'dynamic'})
    return emit('validate-jsonld',fs,[f'Parsed {count} static JSON-LD block(s); this does not validate eligibility or visible-content alignment.'])
def links(root):
    fs=[]; checked=0
    for p in files(root):
        text=p.read_text(errors='ignore')
        for href in re.findall(r'(?:href|to)=["\']([^"\']+)',text,re.I):
            if not href.startswith('/') or href.startswith('//') or '{' in href: continue
            checked+=1
            clean=href.split('#',1)[0].split('?',1)[0].rstrip('/') or '/'
            candidates=[root/'public'/clean.lstrip('/'),root/(clean.lstrip('/')+'.html')]
            candidates+=[root/'app'/clean.strip('/')/f'page.{ext}' for ext in ('tsx','jsx','ts','js','html')]
            candidates+=[root/'pages'/(clean.strip('/')+f'.{ext}') for ext in ('tsx','jsx','ts','js')]
            if not any(x.exists() for x in candidates): fs.append({'severity':'LOW','file':rel(p,root),'issue':f'Could not resolve local internal link: {href}'})
    return emit('scan-links',fs,[f'Checked {checked} static root-relative links; framework routing and dynamic links may be unresolved.'])
GLOBAL_FILE_HINTS=re.compile(r'(layout|nav|header|footer)',re.I)
GENERIC_ANCHORS={'click here','here','read more','learn more','more','link'}
def _match_route(link_path,routes):
    lp=[seg for seg in link_path.strip('/').split('/') if seg!='']
    for r in routes:
        rp=[seg for seg in r.strip('/').split('/') if seg!='']
        if len(lp)==len(rp) and all(a==b or b=='[dynamic]' for a,b in zip(lp,rp)): return r
    return None
def _anchor_text(html):
    return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',html)).strip()
def graph(root):
    records=_route_records(root); routes=[r['route'] for r in records]; route_of_file={r['file']:r['route'] for r in records}; file_of_route={r['route']:r['file'] for r in records}
    inbound_contextual={r:0 for r in routes}; inbound_global={r:0 for r in routes}
    anchors_by_target={}; adjacency={r:set() for r in routes}; global_targets=set(); broken=[]; fs=[]
    for p in files(root):
        path=rel(p,root); text=p.read_text(errors='ignore')
        is_global_file=bool(GLOBAL_FILE_HINTS.search(path)); source_route=route_of_file.get(path)
        seen_hrefs=set()
        for m in re.finditer(r'<(a|Link|NuxtLink|router-link)\b[^>]*?(?:href|to)\s*=\s*\{?["\']([^"\']+)["\']\}?[^>]*>(.*?)</\1>',text,re.I|re.S):
            href=m.group(2); anchor=_anchor_text(m.group(3)); seen_hrefs.add(href)
            if not href.startswith('/') or href.startswith('//'): continue
            clean=href.split('#',1)[0].split('?',1)[0]
            target=_match_route(clean,routes)
            if target is None: broken.append({'file':path,'href':href}); continue
            anchors_by_target.setdefault(target,[]).append(anchor)
            if is_global_file:
                inbound_global[target]=inbound_global.get(target,0)+1; global_targets.add(target)
            else:
                inbound_contextual[target]=inbound_contextual.get(target,0)+1
                if source_route: adjacency.setdefault(source_route,set()).add(target)
                if anchor.lower() in GENERIC_ANCHORS: fs.append({'severity':'LOW','file':path,'issue':f'Generic anchor text "{anchor}" linking to {target}; use descriptive anchor text.','rule':'generic-anchor','target':target})
        for href in re.findall(r'(?:href|to)\s*=\s*\{?["\']([^"\']+)["\']\}?',text,re.I):
            if href in seen_hrefs or not href.startswith('/') or href.startswith('//'): continue
            clean=href.split('#',1)[0].split('?',1)[0]
            if _match_route(clean,routes) is None: broken.append({'file':path,'href':href})
    for r in routes:
        for t in global_targets: adjacency.setdefault(r,set()).add(t)
    depth={r:None for r in routes}
    if '/' in routes:
        depth['/']=0; queue=['/']
        while queue:
            cur=queue.pop(0)
            for nxt in adjacency.get(cur,()):
                if depth.get(nxt) is None: depth[nxt]=depth[cur]+1; queue.append(nxt)
    orphans=[r for r in routes if r!='/' and inbound_contextual.get(r,0)==0 and inbound_global.get(r,0)==0]
    for r in orphans: fs.append({'severity':'MEDIUM','file':file_of_route.get(r,r),'issue':f'Route {r} has no inbound internal links (orphan).','rule':'orphan','target':r})
    seen=set()
    for b in broken:
        key=(b['file'],b['href'])
        if key in seen: continue
        seen.add(key); fs.append({'severity':'LOW','file':b['file'],'issue':f'Could not resolve internal link target to a known route: {b["href"]}','rule':'broken-target'})
    data={'routes':routes,'inboundContextual':inbound_contextual,'inboundGlobal':inbound_global,'orphans':orphans,'depth':depth,'anchorsByTarget':{k:sorted(set(v)) for k,v in anchors_by_target.items()}}
    target=root/'.claude/seo/link-graph.json'; target.parent.mkdir(parents=True,exist_ok=True); target.write_text(json.dumps(data,indent=2)+'\n')
    return emit('scan-link-graph',fs,[f'Built a graph over {len(routes)} discovered route(s); wrote {target.relative_to(root)}.'])
NOINDEX_PATTERN=re.compile(
    r'<meta[^>]+name=["\']robots["\'][^>]*content=["\'][^"\']*noindex'  # <meta name="robots" content="...noindex...">
    r'|X-Robots-Tag["\']?\s*[:=]\s*["\']?[^"\'\n]*noindex'               # config-declared X-Robots-Tag header
    r'|robots\s*:\s*\{[^}]*index\s*:\s*false',                          # Next.js metadata `robots: { index: false }`
    re.I)
IMG_TAG=re.compile(r'<(img|Image|NuxtImg)\b([^>]*)/?>',re.I)
def _attr(attrs,name):
    m=re.search(rf'{name}\s*=\s*\{{?["\']([^"\']*)["\']\}}?',attrs,re.I)
    return m.group(1) if m else None
def images(root):
    fs=[]; total=0
    for p in files(root):
        text=p.read_text(errors='ignore'); path=rel(p,root)
        for idx,m in enumerate(IMG_TAG.finditer(text)):
            tag,attrs=m.group(1),m.group(2); total+=1
            alt=_attr(attrs,'alt'); src=_attr(attrs,'src'); width=_attr(attrs,'width'); height=_attr(attrs,'height'); loading=_attr(attrs,'loading')
            if alt is None: fs.append({'severity':'MEDIUM','file':path,'issue':f'<{tag}> has no alt attribute.','rule':'missing-alt','src':src})
            elif alt=='': fs.append({'severity':'INFO','file':path,'issue':f'<{tag}> has empty alt; confirm the image is decorative.','rule':'empty-alt','src':src})
            elif src and (alt.lower() in ('image','photo') or alt.lower() in (Path(src).stem.lower(),Path(src).name.lower()) or (len(alt.split())>2 and len(set(alt.lower().split()))==1)):
                fs.append({'severity':'LOW','file':path,'issue':f'<{tag}> alt text "{alt}" is not descriptive (filename/generic/repeated word); alt describes purpose, not keywords.','rule':'poor-alt','src':src})
            if tag.lower()=='img' and not (width and height): fs.append({'severity':'LOW','file':path,'issue':f'<{tag}> is missing width/height; can cause layout shift (see references/winning-patterns.md P11).','rule':'missing-dimensions','src':src})
            if idx==0 and loading and loading.lower()=='lazy': fs.append({'severity':'LOW','file':path,'issue':'First image in this file uses loading="lazy"; it is likely the LCP image and should not be deferred.','rule':'lazy-first-image','src':src})
            if src and not src.startswith(('http://','https://','data:')):
                candidate=(root/'public'/src.lstrip('/')) if src.startswith('/') else (p.parent/src)
                if candidate.exists() and candidate.is_file():
                    size=candidate.stat().st_size
                    if size>300*1024: fs.append({'severity':'LOW','file':path,'issue':f'Image {src} is {size//1024}KB (>300KB); consider compressing/resizing.','rule':'oversized','src':src})
                    if candidate.suffix.lower() in ('.jpg','.jpeg','.png'): fs.append({'severity':'INFO','file':path,'issue':f'Image {src} uses {candidate.suffix} rather than a modern format (webp/avif).','rule':'legacy-format','src':src})
    result={'tool':'scan-images','totalImages':total,'findings':fs,'notes':[f'Inspected {total} static image tag(s) (img/Image/NuxtImg); Astro <Image> compiles away and needs a rendered check.']}
    print(json.dumps(result,indent=2)); return 1 if any(x['severity'] in ('CRITICAL','HIGH') for x in fs) else 0
def page_record(p,root):
    text=p.read_text(errors='ignore')
    title=_scoped_matches(r'<title[^>]*>(.*?)</title>|title\s*:\s*[`\'\"]([^`\'\"]+)',text)
    desc=_scoped_matches(r'name=["\']description["\'][^>]*content=["\']([^"\']+)|description\s*:\s*[`\'\"]([^`\'\"]+)',text)
    canon=re.search(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',text,re.I)
    noindex=bool(NOINDEX_PATTERN.search(text))
    visible=re.sub(r'<script\b.*?</script>|<style\b.*?</style>',' ',text,flags=re.I|re.S); visible=re.sub(r'<[^>]+>',' ',visible)
    word_count=len(re.findall(r'[A-Za-z]{2,}',visible))
    return {'source':rel(p,root),'hash':hashlib.sha256(text.encode()).hexdigest()[:16],'title':title[0].strip() if title else None,'description':desc[0].strip() if desc else None,'canonical':canon.group(1) if canon else None,'h1Count':len(re.findall(r'<h1\b',text,re.I)),'jsonldTypes':sorted(set(re.findall(r'"@type"\s*:\s*"([^"\n]+)',text))), 'internalLinkCount':len(re.findall(r'(?:href|to)=["\']/+',text,re.I)),'noindex':noindex,'wordCount':word_count}
def _git_sha(root):
    import subprocess
    try:
        p=subprocess.run(['git','rev-parse','--short','HEAD'],cwd=root,capture_output=True,text=True,timeout=5)
        return p.stdout.strip() if p.returncode==0 and p.stdout.strip() else 'nogit'
    except (OSError,subprocess.SubprocessError): return 'nogit'

def snapshot(root,name=None):
    routes=[]; pages=[]
    for p in files(root):
        t=p.read_text(errors='ignore');
        if 'page.' in rel(p,root) or '/pages/' in rel(p,root): routes.append(rel(p,root)); pages.append(page_record(p,root))
    sitemaps=[]
    for p in root.rglob('sitemap*.xml'):
        try:sitemaps += [n.text.strip() for n in ET.parse(p).findall('.//{*}loc') if n.text]
        except ET.ParseError:pass
    data={'version':2,'routes':sorted(routes),'pages':sorted(pages,key=lambda x:x['source']),'sitemapUrls':sorted(sitemaps),'robotsPresent':bool(list(root.rglob('robots.txt'))),'jsonldBlocks':sum(len(re.findall(r'application/ld\+json',p.read_text(errors='ignore'),re.I)) for p in files(root))}
    target=root/'.claude/seo/baseline.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(data,indent=2)+'\n')
    named_path=None
    if name:
        from datetime import date
        snaps=root/'.claude/seo/snapshots'; snaps.mkdir(parents=True,exist_ok=True)
        named_path=snaps/f'{date.today()}-{_git_sha(root)}.json'
        named_path.write_text(json.dumps({**data,'label':name},indent=2)+'\n')
    print(json.dumps({'tool':'seo-regression','action':'snapshot','file':str(target),'namedFile':str(named_path) if named_path else None,'snapshot':data},indent=2));return 0
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
        for key in ('title','description','canonical','h1Count','jsonldTypes','noindex'):
            if prior.get(key)!=now.get(key):
                severity='HIGH' if key=='noindex' and now.get(key) and not prior.get(key) else 'MEDIUM'
                issue=f'Page newly set to noindex since baseline.' if key=='noindex' and now.get(key) and not prior.get(key) else f'Page SEO property changed: {key}'
                fs.append({'severity':severity,'issue':issue,'file':prior['source'],'before':prior.get(key),'after':now.get(key),'action':'Review intent, visible content, and migration record if applicable.'})
    return emit('seo-regression',fs,['Comparison is static and conservative; inspect intended route changes and runtime-generated assets.'])
def main():
    if len(sys.argv)<3: print('Usage: seo_tools.py <routes|metadata|sitemap|robots|jsonld|links|graph|images|snapshot|compare> <project> [--name LABEL]');return 2
    command,root=sys.argv[1],Path(sys.argv[2]).resolve()
    if not root.is_dir():print(f'ERROR: project directory does not exist: {root}',file=sys.stderr);return 2
    handlers={'routes':route_scan,'metadata':metadata,'sitemap':sitemap,'robots':robots,'jsonld':jsonld,'links':links,'graph':graph,'images':images,'snapshot':snapshot,'compare':regression}
    if command not in handlers: print(f'ERROR: unknown command: {command}',file=sys.stderr); return 2
    if command=='snapshot':
        name=None
        if '--name' in sys.argv[3:]:
            i=sys.argv.index('--name'); name=sys.argv[i+1] if i+1<len(sys.argv) else None
        return snapshot(root,name)
    return handlers[command](root)
if __name__=='__main__':
    try: raise SystemExit(main())
    except (OSError,PermissionError) as e: print(f'ERROR: {e}',file=sys.stderr); raise SystemExit(2)
