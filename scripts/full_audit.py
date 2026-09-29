#!/usr/bin/env python3
"""One-command local SEO + AEO baseline; combines evidence without fabricating outcomes."""
import argparse,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
TOOLS={'framework':'framework_inspect.py','frameworkAdapters':'framework_adapters.py','routes':'scan_routes.py','metadata':'scan_metadata.py','metadataExtract':'metadata_extract.py','sitemap':'validate_sitemap.py','robots':'validate_robots.py','jsonld':'validate_jsonld.py','links':'scan_links.py','graph':'scan_link_graph.py','images':'scan_images.py','hreflang':'validate_hreflang.py','aeo':'validate_aeo.py','evidence':'evidence_ledger.py','regression':'seo_regression.py'}
def invoke(script,args):
 p=subprocess.run([sys.executable,str(HERE/script),*map(str,args)],text=True,capture_output=True)
 try: body=json.loads(p.stdout)
 except json.JSONDecodeError: body={'rawOutput':p.stdout.strip(),'error':p.stderr.strip() or 'Tool did not emit JSON.'}
 return {'exitCode':p.returncode,'result':body}
def state_check(root):
 sys.path.insert(0,str(HERE))
 from score import state_completeness
 stubs=state_completeness(root)
 findings=[{'severity':'MEDIUM','check':'state','issue':f'Content/keyword strategy: NOT STARTED (.claude/seo/{name} is still template-stub-only)','file':f'.claude/seo/{name}'} for name in stubs]
 return {'exitCode':1 if findings else 0,'result':{'tool':'state-completeness','findings':findings}}
def main():
 q=argparse.ArgumentParser();q.add_argument('project',nargs='?',default='.');q.add_argument('--initialize',action='store_true');q.add_argument('--snapshot',action='store_true');q.add_argument('--score',action='store_true');a=q.parse_args();root=Path(a.project).resolve()
 if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr);return 2
 state=None
 if a.initialize: state=invoke('init_state.py',['--project',root])
 result={'tool':'seo-architect-full-audit','project':str(root),'scope':'Static source evidence plus AEO review signals; not proof of crawling, indexing, rankings, citations, or traffic.','state':state,'checks':{}}
 for key,script in TOOLS.items():
  args=[root] if key not in ('evidence','regression') else (['verify',root] if key=='evidence' else ['compare',root])
  result['checks'][key]=invoke(script,args)
 result['checks']['state']=state_check(root)
 if a.snapshot or a.score: result['snapshot']=invoke('seo_regression.py',['snapshot',root])
 high=[]
 for key,check in result['checks'].items():
  for finding in check['result'].get('findings',[]):
   if finding.get('severity') in ('CRITICAL','HIGH'): high.append({'check':key,**finding})
 result['summary']={'highOrCritical':high,'nextStep':'Resolve evidenced high/critical findings, validate rendered staging pages, then establish or refresh the baseline.'}
 if a.score:
  sys.path.insert(0,str(HERE)); from score import compute,append_history
  result['score']=compute(root,result,{}); append_history(root,result['score'])
 print(json.dumps(result,indent=2));return 1 if high else 0
if __name__=='__main__':raise SystemExit(main())
