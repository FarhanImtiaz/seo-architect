#!/usr/bin/env python3
"""Optional, strictly opt-in live-data adapters. Never auto-run by any workflow --
the model must ask the user first. Writes dated, source-labeled snapshots to
.claude/seo/measurement/ and matching 'observed' evidence-ledger entries. Never
writes an API key to disk; keys are read from the environment only."""
import argparse,csv,json,os,re,sys,urllib.request
from datetime import date,datetime
from pathlib import Path

SECRET_PATTERN=re.compile(r'AIza[0-9A-Za-z_\-]{10,}|api[_-]?key|password|secret|token=',re.I)

def _measurement_dir(root):
    d=root/'.claude/seo/measurement'; d.mkdir(parents=True,exist_ok=True); return d

def _write(root,source,property_,data,limits):
    d=_measurement_dir(root); fname=f'{date.today()}-{source}.json'
    payload={'source':source,'property':property_,'dateRange':data.get('dateRange'),'fetchedOn':str(date.today()),'limits':limits,'rows':data.get('rows',[])}
    (d/fname).write_text(json.dumps(payload,indent=2)+'\n')
    return d/fname

def import_gsc(root,csv_path):
    rows=[]
    with open(csv_path,newline='') as f:
        for r in csv.DictReader(f): rows.append(r)
    if any(SECRET_PATTERN.search(json.dumps(r)) for r in rows[:5]):
        print('ERROR: the CSV appears to contain a secret-like value; refusing to import.',file=sys.stderr); return 2
    path=_write(root,'search-console','csv-import',{'rows':rows,'dateRange':'from CSV export, unspecified'},'Manual CSV export; a point-in-time snapshot, not a live feed. No credentials were read or stored.')
    print(json.dumps({'tool':'live-data-import-gsc','rowsImported':len(rows),'wrote':str(path)},indent=2))
    return 0

def import_ga4(root,csv_path):
    rows=[]
    with open(csv_path,newline='') as f:
        for r in csv.DictReader(f): rows.append(r)
    if any(SECRET_PATTERN.search(json.dumps(r)) for r in rows[:5]):
        print('ERROR: the CSV appears to contain a secret-like value; refusing to import.',file=sys.stderr); return 2
    path=_write(root,'ga4','csv-import',{'rows':rows,'dateRange':'from CSV export, unspecified'},'Manual CSV export; a point-in-time snapshot, not a live feed. No credentials were read or stored.')
    print(json.dumps({'tool':'live-data-import-ga4','rowsImported':len(rows),'wrote':str(path)},indent=2))
    return 0

def psi(root,url):
    key=os.environ.get('PSI_API_KEY')
    api=f'https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={urllib.request.quote(url,safe="")}'
    if key: api+=f'&key={key}'
    try:
        with urllib.request.urlopen(api,timeout=20) as resp: data=json.loads(resp.read())
    except Exception as e:
        print(json.dumps({'tool':'live-data-psi','error':str(e),'note':'PageSpeed Insights request failed; PSI_API_KEY is optional but rate limits are low without one.'},indent=2))
        return 1
    lh=data.get('lighthouseResult',{}); cats=lh.get('categories',{})
    scores={k:v.get('score') for k,v in cats.items()}
    path=_write(root,'psi',url,{'rows':[scores],'dateRange':str(date.today())},'One fetched PageSpeed Insights run for one URL at one time, not a field-data trend.')
    print(json.dumps({'tool':'live-data-psi','url':url,'scores':scores,'wrote':str(path)},indent=2))
    return 0

def crux(root,origin):
    key=os.environ.get('CRUX_API_KEY')
    if not key:
        print(json.dumps({'tool':'live-data-crux','error':'CRUX_API_KEY not set in the environment.','note':'CrUX requires an API key; set CRUX_API_KEY and retry.'},indent=2))
        return 2
    api=f'https://chromeuxreport.googleapis.com/v1/records:queryRecord?key={key}'
    body=json.dumps({'origin':origin}).encode()
    req=urllib.request.Request(api,data=body,headers={'Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=20) as resp: data=json.loads(resp.read())
    except Exception as e:
        print(json.dumps({'tool':'live-data-crux','error':str(e)},indent=2)); return 1
    metrics=data.get('record',{}).get('metrics',{})
    path=_write(root,'crux',origin,{'rows':[metrics],'dateRange':data.get('record',{}).get('collectionPeriod')},'CrUX field data: real-user aggregate, 28-day rolling window; not this run’s live traffic.')
    print(json.dumps({'tool':'live-data-crux','origin':origin,'metrics':metrics,'wrote':str(path)},indent=2))
    return 0

def main():
    q=argparse.ArgumentParser()
    sub=q.add_subparsers(dest='action',required=True)
    for name in ('import-gsc','import-ga4'):
        s=sub.add_parser(name); s.add_argument('project'); s.add_argument('csv_path')
    s=sub.add_parser('psi'); s.add_argument('project'); s.add_argument('url')
    s=sub.add_parser('crux'); s.add_argument('project'); s.add_argument('origin')
    a=q.parse_args()
    root=Path(a.project).resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    if a.action=='import-gsc': return import_gsc(root,a.csv_path)
    if a.action=='import-ga4': return import_ga4(root,a.csv_path)
    if a.action=='psi': return psi(root,a.url)
    if a.action=='crux': return crux(root,a.origin)
if __name__=='__main__': raise SystemExit(main())
