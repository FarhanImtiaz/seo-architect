"""Static-site-generator frontmatter adapter (Hugo, Jekyll, Eleventy, Docusaurus, Gatsby, Astro
content collections). Highest-value, cheapest platform to check: content lives in the repo as
YAML/TOML frontmatter, so nothing here is behind a database or a runtime plugin -- there is
nothing to mark `unavailable` beyond build/runtime rendering itself."""
import re
from pathlib import Path

FM_RE=re.compile(r'^---\s*\n(.*?)\n---\s*\n',re.S)
CONTENT_DIRS=('content','posts','_posts','pages','blog')

def detect(root):
    return any((root/d).is_dir() for d in CONTENT_DIRS) and any(root.rglob('*.md')) or any(root.rglob('*.mdx'))

def _parse_frontmatter(text):
    m=FM_RE.match(text)
    if not m: return None
    fm={}
    for line in m.group(1).splitlines():
        kv=re.match(r'^([A-Za-z0-9_]+)\s*:\s*(.*)$',line)
        if kv: fm[kv.group(1)]=kv.group(2).strip().strip('"\'')
    return fm

def scan(root):
    findings=[]; observed=[]; seen_slugs={}
    md_files=[p for p in root.rglob('*.md') if not any(x in p.parts for x in ('node_modules','.git'))]+\
             [p for p in root.rglob('*.mdx') if not any(x in p.parts for x in ('node_modules','.git'))]
    for p in md_files:
        text=p.read_text(errors='ignore')
        fm=_parse_frontmatter(text)
        rel=str(p.relative_to(root))
        if fm is None: continue
        observed.append({'file':rel,'frontmatter':fm})
        title=fm.get('title'); desc=fm.get('description') or fm.get('excerpt')
        slug=fm.get('slug') or p.stem
        draft=str(fm.get('draft','')).lower() in ('true','yes','1')
        if not title: findings.append({'severity':'MEDIUM','file':rel,'issue':'No title in frontmatter.'})
        if not desc: findings.append({'severity':'LOW','file':rel,'issue':'No description/excerpt in frontmatter.'})
        if slug in seen_slugs: findings.append({'severity':'HIGH','file':rel,'issue':f'Duplicate slug "{slug}" also used by {seen_slugs[slug]}.'})
        else: seen_slugs[slug]=rel
        if draft:
            for sm in root.rglob('sitemap*.xml'):
                if slug in sm.read_text(errors='ignore'):
                    findings.append({'severity':'HIGH','file':rel,'issue':f'Page is frontmatter draft:true but its slug "{slug}" appears in {sm.relative_to(root)} -- a draft should not be listed in the sitemap.'}); break
    return {'platform':'ssg-frontmatter','findings':findings,'observed':observed,'unavailable':[]}
