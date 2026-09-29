"""Shopify theme adapter. `layout/theme.liquid`, section/snippet Liquid files, and
`robots.txt.liquid` (if present) are statically inspectable; the sitemap, product/collection
catalog data, and Markets hreflang are platform-generated/DB-owned and always `unavailable`
unless the user supplies a CSV export."""
import re
from pathlib import Path

def detect(root):
    return (root/'layout/theme.liquid').exists() or any(root.rglob('*.liquid'))

def scan(root):
    findings=[]; observed=[]
    theme=root/'layout/theme.liquid'
    if theme.exists():
        text=theme.read_text(errors='ignore')
        for tag,label in (('canonical_url','canonical URL'),('page_title','page title'),('page_description','meta description')):
            if tag not in text: findings.append({'severity':'MEDIUM','file':'layout/theme.liquid','issue':f'No {{{{ {tag} }}}} ({label}) found in theme.liquid.'})
        observed.append({'file':'layout/theme.liquid','hasCanonical':'canonical_url' in text,'hasTitle':'page_title' in text,'hasDescription':'page_description' in text})
    else:
        findings.append({'severity':'MEDIUM','issue':'No layout/theme.liquid found; cannot check canonical/title/description tags.'})
    robots=root/'templates/robots.txt.liquid'
    if robots.exists():
        text=robots.read_text(errors='ignore')
        if re.search(r'\{\{\s*-?\s*disallow\b.*\*\s*-?\s*\}\}',text,re.I) or 'Disallow: /\n' in text.replace(' ',''):
            findings.append({'severity':'HIGH','file':'templates/robots.txt.liquid','issue':'robots.txt.liquid appears to disallow all crawling.'})
    for p in root.rglob('*.liquid'):
        text=p.read_text(errors='ignore')
        if re.search(r'\{\{\s*product\.(?:price|title)',text) and 'application/ld+json' in text:
            observed.append({'file':str(p.relative_to(root)),'note':'Product JSON-LD present using theme variant data.'})
        for m in re.finditer(r'<img\b[^>]*>',text,re.I):
            tag=m.group(0)
            if 'width=' not in tag and 'image_tag' not in tag: findings.append({'severity':'LOW','file':str(p.relative_to(root)),'issue':'<img> without explicit width (and not using the image_tag/image_url helper).'})
    unavailable=[{'reason':'Sitemap, product/collection catalog, and Markets hreflang are platform-generated and DB-owned.','howToUnlock':'Export products/collections as CSV from Shopify admin and re-run with that import.'}]
    return {'platform':'shopify','findings':findings,'observed':observed,'unavailable':unavailable}
