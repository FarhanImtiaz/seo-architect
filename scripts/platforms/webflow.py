"""Webflow code-export adapter. Statically-exported pages are scanned normally; Webflow CMS
Collection pages are NOT included in a code export (Webflow's own export limitation), so they are
always reported `unavailable` unless the user supplies a Collection CSV export."""
import re
from pathlib import Path

def detect(root):
    for p in list(root.rglob('*.html'))[:200]:
        text=p.read_text(errors='ignore')
        if 'data-wf-site' in text or 'data-wf-page' in text: return True
    return False

def scan(root):
    findings=[]; observed=[]; static_pages=0
    for p in root.rglob('*.html'):
        text=p.read_text(errors='ignore')
        if 'data-wf-page' not in text: continue
        static_pages+=1
        title=re.search(r'<title[^>]*>(.*?)</title>',text,re.I|re.S)
        if not title or not title.group(1).strip(): findings.append({'severity':'MEDIUM','file':str(p.relative_to(root)),'issue':'Static Webflow-exported page has no title.'})
        observed.append({'file':str(p.relative_to(root))})
    unavailable=[{'reason':'Webflow CMS Collection pages are not included in a code export.','howToUnlock':'Export the Collection as CSV (Webflow project settings) and re-run with that import for slug/SEO-field coverage.'}]
    return {'platform':'webflow','findings':findings,'observed':observed,'unavailable':unavailable,'staticPageCount':static_pages}
