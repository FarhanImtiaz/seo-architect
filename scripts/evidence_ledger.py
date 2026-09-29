#!/usr/bin/env python3
"""Maintain verifiable project evidence without collecting credentials."""
import argparse,json,sys
from datetime import date
from pathlib import Path
FIELDS={'claim','kind','source','confidence','observedOn','status'}
def file(root): return root/'.claude/seo/evidence.json'
def load(p):
 if not p.exists(): return {'version':1,'entries':[]}
 try: return json.loads(p.read_text())
 except json.JSONDecodeError: raise ValueError('evidence.json is invalid JSON')
def _known_source_ids(root):
 p=root/'references/sources.json'
 if not p.exists(): p=Path(__file__).resolve().parent.parent/'references/sources.json'
 if not p.exists(): return set()
 try: return {s['id'] for s in json.loads(p.read_text())['sources']}
 except (json.JSONDecodeError,KeyError): return set()
def main():
 q=argparse.ArgumentParser();q.add_argument('action',choices=['add','verify','list']);q.add_argument('project');q.add_argument('--claim');q.add_argument('--kind',default='project-fact');q.add_argument('--source');q.add_argument('--confidence',choices=['observed','inference','hypothesis'],default='observed');q.add_argument('--source-id');a=q.parse_args();root=Path(a.project).resolve();p=file(root)
 try:data=load(p)
 except ValueError as e: print('ERROR:',e,file=sys.stderr);return 2
 if a.action=='add':
  if not a.claim or not a.source: print('ERROR: --claim and --source are required.',file=sys.stderr);return 2
  if any(x in (a.source.lower()+a.claim.lower()) for x in ('api_key','password','secret','token=','aiza')): print('ERROR: evidence cannot contain secrets.',file=sys.stderr);return 2
  kind=a.kind
  if a.source_id:
   if a.source_id not in _known_source_ids(root): print(f'ERROR: --source-id "{a.source_id}" is not in references/sources.json.',file=sys.stderr);return 2
   kind='external-pattern'
  entry={'claim':a.claim,'kind':kind,'source':a.source,'confidence':a.confidence,'observedOn':str(date.today()),'status':'active'}
  if a.source_id: entry['sourceId']=a.source_id
  data['entries'].append(entry);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2)+'\n')
 if a.action=='verify':
  bad=[x for x in data['entries'] if not FIELDS.issubset(x) or x.get('confidence') not in ('observed','inference','hypothesis')]
  print(json.dumps({'entries':len(data['entries']),'invalid':bad,'result':'pass' if not bad else 'fail'},indent=2));return 1 if bad else 0
 if a.action=='list': print(json.dumps(data,indent=2))
 return 0
if __name__=='__main__': raise SystemExit(main())
