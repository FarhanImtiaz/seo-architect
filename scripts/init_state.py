#!/usr/bin/env python3
"""Create missing project-local SEO state without overwriting existing facts."""
from argparse import ArgumentParser
from pathlib import Path
import json
NAMES=['strategy.md','keywords.md','competitors.md','entities.md','pages.md','content-plan.md','internal-links.md','audit.md','changelog.md']
def main():
 p=ArgumentParser();p.add_argument('--project',default='.');a=p.parse_args();root=Path(a.project).resolve()
 if not root.is_dir():p.error(f'not a directory: {root}')
 d=root/'.claude/seo';d.mkdir(parents=True,exist_ok=True);made=[]
 for n in NAMES:
  f=d/n
  if not f.exists():f.write_text(f'# {n[:-3].replace("-"," ").title()}\n\n<!-- Project-specific SEO state. Record evidence, assumptions, and dated decisions. -->\n');made.append(str(f.relative_to(root)))
 e=d/'evidence.json'
 if not e.exists(): e.write_text(json.dumps({'version':1,'entries':[]},indent=2)+'\n');made.append(str(e.relative_to(root)))
 for sub in ('snapshots','changes','impact'):
  sd=d/sub; sd.mkdir(parents=True,exist_ok=True)
 gi=d/'measurement/.gitignore'
 if not gi.exists():
  gi.parent.mkdir(parents=True,exist_ok=True)
  gi.write_text('# Raw imported measurement data (GSC/GA4/CrUX exports) is ignored by default: it may contain\n# real traffic/query data you may not want committed. Remove this file, or commit specific\n# files deliberately, if you want measurement history tracked in version control.\nraw/\nindex.json\n')
  made.append(str(gi.relative_to(root)))
 c=d/'config.json'
 if not c.exists():c.write_text(json.dumps({'domain':'','projectName':root.name,'primaryMarket':'','secondaryMarkets':[],'businessType':'','framework':'auto','canonicalHost':'','locale':'','tracking':{'searchConsole':False,'bingWebmaster':False,'analytics':False},'mode':'active'},indent=2)+'\n');made.append(str(c.relative_to(root)))
 print(json.dumps({'created':made,'stateDirectory':str(d.relative_to(root)),'note':'Existing state was preserved; never store secrets in config.json.'},indent=2))
if __name__=='__main__':main()
