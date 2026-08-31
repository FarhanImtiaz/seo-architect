#!/usr/bin/env python3
"""Framework-specific static metadata and route convention checks."""
from pathlib import Path
import json,re,sys
SKIP={'.git','node_modules','.next','dist','build','.venv'}
def source(root):
 return [p for p in root.rglob('*') if p.is_file() and p.suffix in {'.js','.jsx','.ts','.tsx','.vue','.svelte','.astro','.html'} and not any(x in SKIP for x in p.parts)]
def main():
 root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve(); fs=source(root); findings=[]; observed=[]
 next_pages=[p for p in fs if re.search(r'(^|/)(app/(?:.*/)?page|pages/)',str(p.relative_to(root)))]
 if next_pages:
  observed.append({'adapter':'nextjs','pages':[str(p.relative_to(root)) for p in next_pages]})
  for p in next_pages:
   text=p.read_text(errors='ignore'); path=str(p.relative_to(root))
   if not (re.search(r'export\s+const\s+metadata\s*=',text) or '<title',text): findings.append({'severity':'MEDIUM','adapter':'nextjs','file':path,'issue':'No static Next metadata export or HTML title.'})
   if 'metadataBase' not in text and 'canonical' not in text and ('app/' in path): findings.append({'severity':'LOW','adapter':'nextjs','file':path,'issue':'No static metadataBase/canonical evidence in this route; may be inherited.'})
  for name in ('sitemap.ts','sitemap.js','robots.ts','robots.js'):
   if (root/'app'/name).exists(): observed.append({'adapter':'nextjs','generatedAsset':f'app/{name}'})
 astro=[p for p in fs if '/src/pages/' in ('/'+str(p.relative_to(root)))]
 if astro:
  observed.append({'adapter':'astro','pages':[str(p.relative_to(root)) for p in astro]})
  for p in astro:
   text=p.read_text(errors='ignore')
   if '<head' not in text.lower() and 'BaseHead' not in text: findings.append({'severity':'LOW','adapter':'astro','file':str(p.relative_to(root)),'issue':'No static Astro head evidence; may be inherited.'})
 nuxt=[p for p in fs if '/pages/' in ('/'+str(p.relative_to(root)))]
 if (root/'nuxt.config.ts').exists() or (root/'nuxt.config.js').exists():
  observed.append({'adapter':'nuxt','pages':[str(p.relative_to(root)) for p in nuxt]})
  for p in nuxt:
   if 'useHead(' not in p.read_text(errors='ignore') and 'definePageMeta(' not in p.read_text(errors='ignore'): findings.append({'severity':'LOW','adapter':'nuxt','file':str(p.relative_to(root)),'issue':'No static Nuxt head evidence; may be inherited.'})
 svelte=[p for p in fs if '/src/routes/' in ('/'+str(p.relative_to(root)))]
 if svelte:
  observed.append({'adapter':'sveltekit','pages':[str(p.relative_to(root)) for p in svelte]})
  for p in svelte:
   if p.name.startswith('+page') and '<svelte:head>' not in p.read_text(errors='ignore'): findings.append({'severity':'LOW','adapter':'sveltekit','file':str(p.relative_to(root)),'issue':'No static Svelte head evidence; may be inherited.'})
 print(json.dumps({'tool':'framework-adapters','observed':observed,'findings':findings,'limits':'Inherited or runtime metadata can be valid but is not proven by this source inspection.'},indent=2));return 1 if any(x['severity']=='MEDIUM' for x in findings) else 0
if __name__=='__main__':raise SystemExit(main())
