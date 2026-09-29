#!/usr/bin/env python3
"""hreflang validation -- only meaningful once i18n is actually in play; self-gates otherwise
rather than reporting false findings on a single-locale site."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from seo_tools import files,rel

ISO_LANG=re.compile(r'^[a-z]{2,3}(-[A-Z]{2})?$')
COMMON_MISTAKES={'en-UK':'en-GB','en-us':'en-US'}

def _config(root):
    p=root/'.claude/seo/config.json'
    if not p.exists(): return {}
    try: return json.loads(p.read_text())
    except json.JSONDecodeError: return {}

def _i18n_detected(root,config):
    if config.get('secondaryMarkets') or config.get('locale'): return True
    for p in files(root):
        s=rel(p,root)
        if re.search(r'\[(locale|lang)\]',s): return True
        if p.name in ('next.config.js','next.config.ts') and 'i18n' in p.read_text(errors='ignore'): return True
    return False

def _own_url(path):
    return '/'+re.sub(r'\.[^./]+$','',path)

def _alternates(root):
    """path -> {code: href} from static <link rel=alternate hreflang> tags."""
    out={}
    for p in files(root):
        text=p.read_text(errors='ignore'); path=rel(p,root); found={}
        for m in re.finditer(r'<link[^>]+rel=["\']alternate["\'][^>]*hreflang=["\']([^"\']+)["\'][^>]*href=["\']([^"\']+)["\']',text,re.I):
            found[m.group(1)]=m.group(2)
        for m in re.finditer(r'<link[^>]+hreflang=["\']([^"\']+)["\'][^>]*href=["\']([^"\']+)["\']',text,re.I):
            found.setdefault(m.group(1),m.group(2))
        if found: out[path]=found
    return out

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    config=_config(root)
    if not _i18n_detected(root,config):
        print(json.dumps({'tool':'validate-hreflang','applicable':False,'findings':[],'notes':['No locale/secondaryMarkets in config.json and no i18n route/config signal detected; hreflang check not applicable.']},indent=2))
        return 0
    alternates=_alternates(root)
    fs=[]
    if not alternates:
        print(json.dumps({'tool':'validate-hreflang','applicable':True,'findings':[{'severity':'MEDIUM','issue':'i18n was detected but no static hreflang <link> tags were found; verify localized pages declare alternates.'}],'notes':[]},indent=2))
        return 1
    url_to_path={_own_url(path):path for path in alternates}
    for path,found in alternates.items():
        own_url=_own_url(path)
        for code,href in found.items():
            if code=='x-default': continue
            if code not in COMMON_MISTAKES and not ISO_LANG.match(code): fs.append({'severity':'LOW','file':path,'issue':f'hreflang code "{code}" does not look like a valid ISO 639-1(-region) code.'})
            elif code in COMMON_MISTAKES: fs.append({'severity':'LOW','file':path,'issue':f'hreflang code "{code}" looks like a common mistake; did you mean "{COMMON_MISTAKES[code]}"?'})
        if 'x-default' not in found: fs.append({'severity':'INFO','file':path,'issue':'No x-default hreflang fallback declared.'})
        if own_url not in found.values(): fs.append({'severity':'MEDIUM','file':path,'issue':f'No self-referencing hreflang entry ({own_url}) found among this page’s alternates.'})
        for code,href in found.items():
            if code=='x-default': continue
            target_path=url_to_path.get(href)
            if target_path is None: continue  # external/unresolved target; can't verify reciprocity statically
            if own_url not in alternates.get(target_path,{}).values(): fs.append({'severity':'MEDIUM','file':path,'issue':f'hreflang to "{href}" ({code}) is not reciprocated back to {own_url} from that page.'})
    print(json.dumps({'tool':'validate-hreflang','applicable':True,'findings':fs,'notes':[f'Checked {len(alternates)} file(s) with static hreflang tags.']},indent=2))
    return 1 if any(f['severity'] in ('CRITICAL','HIGH') for f in fs) else 0
if __name__=='__main__': raise SystemExit(main())
