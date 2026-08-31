#!/usr/bin/env python3
"""Detect common web frameworks from repository evidence; never guesses silently."""
from pathlib import Path
import json, sys
def main():
 root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve(); pkg=root/'package.json'; evidence=[]; framework='unknown'
 if pkg.exists():
  try:
   data=json.loads(pkg.read_text()); deps={**data.get('dependencies',{}),**data.get('devDependencies',{})}
   for name,label in [('next','nextjs'),('astro','astro'),('nuxt','nuxt'),('@sveltejs/kit','sveltekit'),('@remix-run/react','remix'),('vite','vite')]:
    if name in deps: framework=label; evidence.append(f'package.json dependency: {name}'); break
  except (OSError,json.JSONDecodeError) as e: evidence.append(f'Could not parse package.json: {e}')
 dirs={'nextjs':['app','pages'],'astro':['src/pages'],'sveltekit':['src/routes'],'nuxt':['pages'],'remix':['app/routes']}
 for label,paths in dirs.items():
  if any((root/p).exists() for p in paths): evidence.append('route convention: '+label); framework=label if framework=='unknown' else framework
 print(json.dumps({'framework':framework,'evidence':evidence or ['No supported framework evidence found.'],'confidence':'observed' if evidence else 'unknown'},indent=2))
if __name__=='__main__': main()
