"""WordPress theme adapter. Theme PHP/templates are statically inspectable; actual page titles,
canonicals, sitemap, and schema are usually owned by an SEO plugin (Yoast/Rank Math) or the
database and are `unavailable` unless the user opts into an unauthenticated public REST import."""
import re
from pathlib import Path

def detect(root):
    return (root/'style.css').exists() and 'Theme Name' in (root/'style.css').read_text(errors='ignore') if (root/'style.css').exists() else any(root.rglob('functions.php'))

def scan(root):
    findings=[]; observed=[]
    php_files=[p for p in root.rglob('*.php') if 'node_modules' not in p.parts]
    functions=root/'functions.php'
    has_title_tag_support=False
    for p in php_files:
        text=p.read_text(errors='ignore')
        if "add_theme_support('title-tag')" in text or 'add_theme_support("title-tag")' in text: has_title_tag_support=True
        if re.search(r'<title>[^<]*</title>',text) and '<?php' in text:
            findings.append({'severity':'MEDIUM','file':str(p.relative_to(root)),'issue':'Hard-coded <title> tag found; this will conflict with wp_head()/an SEO plugin\'s title output.'})
        if re.search(r'<link[^>]+rel=["\']canonical["\']',text) and 'wp_head' not in text:
            findings.append({'severity':'MEDIUM','file':str(p.relative_to(root)),'issue':'Hard-coded canonical link tag found outside wp_head() -- likely to conflict with an SEO plugin\'s canonical output.'})
    if not has_title_tag_support and functions.exists():
        findings.append({'severity':'LOW','file':'functions.php','issue':"No add_theme_support('title-tag') found; classic themes need this (or a hard-coded <title>, not recommended) for a document title."})
    for name in ('header.php','index.php','single.php','page.php'):
        p=root/name
        if p.exists() and 'wp_head()' not in p.read_text(errors='ignore') and name=='header.php':
            findings.append({'severity':'HIGH','file':name,'issue':'header.php does not call wp_head() -- SEO plugins, meta tags, and enqueued styles/scripts will not output.'})
    theme_json=root/'theme.json'
    if theme_json.exists(): observed.append({'file':'theme.json','note':'Block theme detected.'})
    observed.append({'hasTitleTagSupport':has_title_tag_support,'phpFilesScanned':len(php_files)})
    unavailable=[{'reason':'Actual titles, canonicals, sitemap, and schema are usually owned by an SEO plugin (Yoast/Rank Math) or the database.','howToUnlock':'Opt into an unauthenticated public REST import (/wp-json/wp/v2/pages, rate-limited) against the user\'s own site.'}]
    return {'platform':'wordpress','findings':findings,'observed':observed,'unavailable':unavailable}
