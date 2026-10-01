"""Headless CMS content-model adapter (Sanity, Payload, Strapi, Contentful migrations). Checks
whether the CONTENT MODEL enforces SEO fields -- this is a model-level contract, not the content
itself, which lives in the CMS's database and is unavailable here unless the user provides an
offline export file."""
import json,re
from pathlib import Path

def detect(root):
    return (any(root.rglob('sanity.config.*')) or any(root.rglob('payload.config.*'))
            or (root/'strapi').is_dir() or any(root.rglob('content-types/*/schema.json')))

def _sanity_types(root):
    out=[]
    for p in root.rglob('*.*'):
        if p.suffix not in ('.js','.ts') or 'node_modules' in p.parts: continue
        text=p.read_text(errors='ignore')
        for m in re.finditer(r'defineType\s*\(\s*\{(.*?)\n\}\s*\)',text,re.S):
            body=m.group(1)
            name=re.search(r'name\s*:\s*[\'"]([^\'"]+)[\'"]',body)
            fields=re.findall(r'name\s*:\s*[\'"]([^\'"]+)[\'"]',body)
            if name: out.append({'file':str(p.relative_to(root)),'type':name.group(1),'fields':fields})
    return out

def _strapi_types(root):
    out=[]
    for p in root.rglob('content-types/*/schema.json'):
        try: data=json.loads(p.read_text())
        except json.JSONDecodeError: continue
        attrs=list(data.get('attributes',{}).keys())
        out.append({'file':str(p.relative_to(root)),'type':data.get('info',{}).get('singularName',p.parent.name),'fields':attrs})
    return out

SEO_FIELD_HINTS=('seo','slug','metaTitle','meta_title','metaDescription','meta_description','noindex','canonical')

def scan(root):
    findings=[]; observed=[]
    types=_sanity_types(root)+_strapi_types(root)
    for t in types:
        observed.append(t)
        fields_lower=[f.lower() for f in t['fields']]
        has_slug=any('slug' in f for f in fields_lower)
        has_seo=any(any(h.lower() in f for h in SEO_FIELD_HINTS) for f in fields_lower)
        if not has_slug: findings.append({'severity':'MEDIUM','file':t['file'],'issue':f'Content type "{t["type"]}" has no slug field in its schema -- routes for this type may not be stable/predictable.'})
        if not has_seo: findings.append({'severity':'LOW','file':t['file'],'issue':f'Content type "{t["type"]}" has no SEO-related field (title/description/seo object) in its schema.'})
    if types:
        unavailable=[{'reason':'Actual entries live in the CMS database, not this repo.','howToUnlock':'Provide an offline export file (Sanity .ndjson, Contentful export JSON, etc.) and re-run with that import.'}]
    else:
        # A CMS WAS detected (config file, strapi/ dir, etc. -- that's why scan() is even being
        # called) but zero content types could be statically parsed from it (e.g. Payload and
        # Contentful projects are detected but have no parser here yet). An empty findings/
        # unavailable list here would silently read as "nothing to report" rather than "we
        # couldn't check" -- make the gap explicit instead.
        unavailable=[{'reason':'A headless CMS was detected in this project, but its content-type schema could not be statically parsed (only Sanity defineType() and Strapi content-types/*/schema.json are currently parsed).','howToUnlock':'If this is Payload, Contentful, or another CMS, provide its schema/content-type definitions or an offline export for manual review.'}]
    return {'platform':'headless-cms','findings':findings,'observed':observed,'unavailable':unavailable}
