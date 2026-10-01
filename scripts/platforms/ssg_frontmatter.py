"""Static-site-generator frontmatter adapter (Hugo, Jekyll, Eleventy, Docusaurus, Gatsby, Astro
content collections). Highest-value, cheapest platform to check: content lives in the repo as
YAML/TOML frontmatter, so nothing here is behind a database or a runtime plugin -- there is
nothing to mark `unavailable` beyond build/runtime rendering itself. Supports simple flat TOML
frontmatter (+++) with a dependency-free parser, not full TOML (this repo supports Python 3.9+,
so stdlib tomllib -- 3.11+ only -- isn't usable unconditionally)."""
import re
from pathlib import Path

FM_YAML_RE=re.compile(r'^---\s*\n(.*?)\n---\s*\n',re.S)
FM_TOML_RE=re.compile(r'^\+\+\+\s*\n(.*?)\n\+\+\+\s*\n',re.S)
CONTENT_DIRS=('content','posts','_posts','pages','blog')
INDEX_STEMS=('index','_index')  # Hugo/page-bundle convention: parent dir is the real slug

def detect(root):
    """True only when an actual SSG content dir contains a markdown file that itself starts with
    a real frontmatter delimiter -- not just "a content-dir-shaped folder exists somewhere and a
    .md file exists somewhere else in the repo" (the old `A and B or C` precedence bug let a
    Next.js project with a `pages/` dir and a root README.md misdetect as an SSG site)."""
    for d in CONTENT_DIRS:
        dirp=root/d
        if not dirp.is_dir(): continue
        for ext in ('*.md','*.mdx'):
            for p in dirp.rglob(ext):
                if any(x in p.parts for x in ('node_modules','.git')): continue
                try: head=p.read_text(errors='ignore')[:8].lstrip()
                except OSError: continue
                if head.startswith('---') or head.startswith('+++'): return True
    return False

def _parse_toml_frontmatter(block):
    """Minimal flat key=value TOML, enough for typical title/description/draft/date frontmatter --
    not the full TOML spec (nested tables, arrays of tables, etc. are not needed here)."""
    fm={}
    for line in block.splitlines():
        line=line.split('#',1)[0].strip()
        kv=re.match(r'^([A-Za-z0-9_]+)\s*=\s*(.*)$',line)
        if not kv: continue
        key,val=kv.group(1),kv.group(2).strip()
        if val.lower() in ('true','false'): val=val.lower()=='true'
        elif len(val)>=2 and val[0]==val[-1]=='"': val=val[1:-1]
        elif len(val)>=2 and val[0]==val[-1]=="'": val=val[1:-1]
        else: val=val.strip()
        fm[key]=val
    return fm

def _parse_frontmatter(text):
    m=FM_YAML_RE.match(text)
    if m:
        fm={}
        for line in m.group(1).splitlines():
            kv=re.match(r'^([A-Za-z0-9_]+)\s*:\s*(.*)$',line)
            if kv: fm[kv.group(1)]=kv.group(2).strip().strip('"\'')
        return fm
    m=FM_TOML_RE.match(text)
    if m: return _parse_toml_frontmatter(m.group(1))
    return None

def _slug_for(p):
    """A file literally named index.md/_index.md (a Hugo page bundle, e.g. a/index.md and
    b/index.md as two separate, legitimate pages) must use its PARENT directory as the slug --
    using the filename itself makes every page bundle collide on the same fake "index" slug."""
    return p.parent.name if p.stem.lower() in INDEX_STEMS else p.stem

def _path_segments(url_or_path):
    return [seg for seg in re.split(r'[/\\]',str(url_or_path)) if seg]

def scan(root):
    findings=[]; observed=[]; seen_slugs={}
    md_files=[p for p in root.rglob('*.md') if not any(x in p.parts for x in ('node_modules','.git'))]+\
             [p for p in root.rglob('*.mdx') if not any(x in p.parts for x in ('node_modules','.git'))]
    sitemap_texts=[(sm,sm.read_text(errors='ignore')) for sm in root.rglob('sitemap*.xml')]
    for p in md_files:
        text=p.read_text(errors='ignore')
        fm=_parse_frontmatter(text)
        rel=str(p.relative_to(root))
        if fm is None: continue
        observed.append({'file':rel,'frontmatter':fm})
        title=fm.get('title'); desc=fm.get('description') or fm.get('excerpt')
        slug=fm.get('slug') or _slug_for(p)
        draft=str(fm.get('draft','')).lower() in ('true','yes','1')
        if not title: findings.append({'severity':'MEDIUM','file':rel,'issue':'No title in frontmatter.'})
        if not desc: findings.append({'severity':'LOW','file':rel,'issue':'No description/excerpt in frontmatter.'})
        if slug in seen_slugs: findings.append({'severity':'HIGH','file':rel,'issue':f'Duplicate slug "{slug}" also used by {seen_slugs[slug]}.'})
        else: seen_slugs[slug]=rel
        if draft:
            for sm,sm_text in sitemap_texts:
                # Full path-segment match, not substring -- a substring match let slug "ai" match
                # inside an unrelated "/blog/maintain/" URL.
                sm_segments={seg for url in re.findall(r'<loc>\s*([^<]+)\s*</loc>',sm_text) for seg in _path_segments(url)}
                if slug in sm_segments:
                    findings.append({'severity':'HIGH','file':rel,'issue':f'Page is frontmatter draft:true but its slug "{slug}" appears as a URL path segment in {sm.relative_to(root)} -- a draft should not be listed in the sitemap.'}); break
    return {'platform':'ssg-frontmatter','findings':findings,'observed':observed,'unavailable':[]}
