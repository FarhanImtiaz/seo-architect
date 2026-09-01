#!/usr/bin/env python3
"""Conservative static AEO signals. It reports review signals, never a visibility score."""
from pathlib import Path
import json,re,sys
EXT={'.html','.htm','.jsx','.tsx','.js','.ts','.vue','.svelte','.astro','.mdx'}; SKIP={'.git','node_modules','.next','dist','build','.venv'}
def main():
 root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve(); pages=[]; findings=[]
 for p in root.rglob('*'):
  if not p.is_file() or p.suffix not in EXT or any(x in SKIP for x in p.parts): continue
  path=str(p.relative_to(root)); text=p.read_text(errors='ignore'); likely=('page.' in path or '/pages/' in path or '<html' in text.lower())
  if not likely: continue
  signals={'questionHeading':bool(re.search(r'<h[2-3][^>]*>\s*(?:what|how|why|when|where|who|can|does|is)\b',text,re.I)),'faq':bool(re.search(r'faq|frequently asked|<details',text,re.I)),'definition':bool(re.search(r'\b(?:is|means|refers to)\b',text,re.I)),'comparison':bool(re.search(r'<table\b|\bcompare|\bversus\b|\bvs\.?',text,re.I)),'authorOrOrganization':bool(re.search(r'author|organization|publisher|about us|company',text,re.I)),'date':bool(re.search(r'(?:datePublished|dateModified|published|updated)\b',text,re.I)),'visibleSchema':bool(re.search(r'application/ld\+json',text,re.I)),'media':bool(re.search(r'<img\b|<video\b',text,re.I))}
  missing=[k for k,v in signals.items() if not v]
  pages.append({'file':path,'signals':signals})
  if not signals['authorOrOrganization']: findings.append({'severity':'LOW','file':path,'issue':'No static author or organization identity signal; check visible trust context.'})
  if not signals['definition'] and not signals['questionHeading']: findings.append({'severity':'INFO','file':path,'issue':'No static direct-answer/definition signal; review primary intent manually.'})
 print(json.dumps({'tool':'validate-aeo','pages':pages,'findings':findings,'limit':'Signals do not predict AI feature inclusion, citations, rankings, or traffic. Verify rendered/indexable pages and real evidence.'},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
