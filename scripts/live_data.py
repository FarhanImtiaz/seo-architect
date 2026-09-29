#!/usr/bin/env python3
"""Optional, strictly opt-in live-data adapters. Never auto-run by any workflow --
the model must ask the user first. Writes immutable, content-hash-named, dated,
source-labeled snapshots to .claude/seo/measurement/raw/ (cataloged in
measurement/index.json) and matching 'observed' evidence-ledger entries. Never
writes an API key to disk or into a URL; keys are read from the environment and
sent as a request header only."""
import argparse,csv,hashlib,io,json,os,re,sys,urllib.request,zipfile
from datetime import date
from pathlib import Path

SECRET_PATTERN=re.compile(r'(?:'
    r'AIza[0-9A-Za-z_\-]{10,}'                          # Google API key
    r'|GOCSPX-[0-9A-Za-z_\-]{10,}'                       # Google OAuth client secret
    r'|ya29\.[A-Za-z0-9_\-\.]{10,}'                      # Google OAuth access token
    r'|1//0[A-Za-z0-9_\-]{15,}'                          # Google OAuth refresh token
    r'|sk-[A-Za-z0-9_\-]{16,}'                           # OpenAI-style secret key
    r'|sk_live_[A-Za-z0-9]{10,}'                         # Stripe live secret key
    r'|pk_live_[A-Za-z0-9]{10,}'                         # Stripe live publishable key
    r'|AKIA[0-9A-Z]{12,}'                                # AWS access key ID
    r'|ghp_[A-Za-z0-9]{20,}'                             # GitHub personal access token
    r'|xox[baprs]-[A-Za-z0-9\-]{10,}'                    # Slack token
    r'|eyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{5,}'  # JWT
    r'|-----BEGIN [A-Z ]*PRIVATE KEY-----'               # PEM private key block
    r'|Bearer\s+[A-Za-z0-9_\-\.]{10,}'                   # Bearer <token>
    # A key/secret/token NAME followed by an actual value-shaped string, not a bare keyword --
    # this must match json.dumps()'s quoted-key form ("api_key": "...") as well as CSV/plain
    # text (api_key=...); requiring a >=6-char value after the separator avoids flagging a
    # harmless URL parameter like "?token=" with no real value.
    r'|(?:api[_-]?key|client[_-]?secret|aws[_-]?secret[_-]?access[_-]?key|secret|password|passwd|token)["\']?\s*[:=]\s*["\']?[A-Za-z0-9_\-\.\/+=]{6,}'
    r')',re.I)
LABELS={'treated','control','site'}

def _redact(text):
    return SECRET_PATTERN.sub('[redacted]',re.sub(r'key=[^&\s"\']+','key=[redacted]',text))

def _rows_have_secret(rows):
    return any(SECRET_PATTERN.search(json.dumps(r)) for r in rows)

def _measurement_dirs(root):
    raw=root/'.claude/seo/measurement/raw'; raw.mkdir(parents=True,exist_ok=True); return raw

def _update_index(root,path,payload):
    idx=root/'.claude/seo/measurement/index.json'
    data={'version':1,'entries':[]}
    if idx.exists():
        try: data=json.loads(idx.read_text())
        except json.JSONDecodeError: pass
    data['entries'].append({'file':str(path.relative_to(root)),'source':payload['source'],'label':payload['label'],'dateRange':payload['dateRange'],'grain':payload['grain'],'sha256':payload['provenance']['fileSha256'],'synthetic':payload['synthetic'],'importedOn':payload['provenance']['importedOn']})
    idx.write_text(json.dumps(data,indent=2)+'\n')

def _write(root,source,property_,rows,date_range,limits,label='site',method='manual',grain='daily',synthetic=False):
    raw=_measurement_dirs(root)
    body_for_hash=json.dumps({'source':source,'label':label,'rows':rows,'dateRange':date_range},sort_keys=True)
    sha256=hashlib.sha256(body_for_hash.encode()).hexdigest()
    range_tag=f"{date_range['start']}_{date_range['end']}" if date_range else 'unspecified'
    fname=f'{source}-{label}-{range_tag}-{sha256[:8]}.json'
    payload={'schemaVersion':1,'source':source,'label':label,'provenance':{'method':method,'fileSha256':sha256,'importedOn':str(date.today()),'property':property_,'filters':[]},'dateRange':date_range,'grain':grain,'rows':rows,'limits':limits,'synthetic':synthetic}
    path=raw/fname; path.write_text(json.dumps(payload,indent=2)+'\n')
    _update_index(root,path,payload)
    return path,payload

def _date_range_arg(start,end):
    if start and end: return {'start':start,'end':end}
    return None

def _csv_rows(path):
    # utf-8-sig strips a leading UTF-8 BOM if present (a plain Search Console/GA4 CSV export is
    # often BOM'd) -- without this, a BOM'd 'Date' header becomes '﻿Date', matches nothing
    # in _normalize_row_keys, and every row silently ends up with no usable date (H4-round-2).
    with open(path,newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

_NUMERIC_KEYS={'clicks','impressions'}

def _normalize_row_keys(row):
    """GSC/GA4 exports use capitalized headers (Date, Clicks, CTR as '5.5%', Position) that
    impact.py's _daily_totals()/_window_days_present() never match (they look for lowercase
    'date'/<metric>). Without this, every real import silently produces zero usable rows and
    evaluate() dead-ends at insufficient-data forever -- it fails safe, but it never actually
    works. This normalizes onto the lowercase keys impact.py expects, merged alongside the
    original columns (nothing is dropped)."""
    out=dict(row)
    for k,v in row.items():
        if k is None or v is None: continue
        lk=k.strip().lower()
        if lk=='date':
            out['date']=v.strip() if isinstance(v,str) else v
        elif lk in _NUMERIC_KEYS:
            try: out[lk]=float(str(v).replace(',','').strip())
            except (TypeError,ValueError): pass
        elif lk=='ctr':
            s=str(v).strip()
            try:
                f=float(s.rstrip('%'))
                out['ctr']=f/100 if s.endswith('%') else f
            except (TypeError,ValueError): pass
        elif lk in ('position','average position','avg. position','avg position'):
            try: out['position']=float(str(v).replace(',','').strip())
            except (TypeError,ValueError): pass
    return out

def _warn_if_no_dated_rows(rows,kind):
    if rows and not any(r.get('date') for r in rows):
        print(f'WARNING: {len(rows)} row(s) were read from the {kind}, but none ended up with a usable "date" value after header normalization -- check the CSV\'s header names (a BOM, an unexpected locale like "Datum"/"Klicks", or an unrecognized column layout can all cause this). This import will be unusable for before/after measurement.',file=sys.stderr)

def import_gsc(root,csv_path,start,end,label):
    rows=[_normalize_row_keys(r) for r in _csv_rows(csv_path)]
    if _rows_have_secret(rows):
        print('ERROR: the CSV appears to contain a secret-like value; refusing to import.',file=sys.stderr); return 2
    _warn_if_no_dated_rows(rows,'GSC CSV')
    date_range=_date_range_arg(start,end)
    note='Manual CSV export; a point-in-time snapshot, not a live feed. No credentials were read or stored.'
    if not date_range: note+=' No date range was given (--start/--end); this import cannot be used for before/after measurement until one is known.'
    path,_=_write(root,'search-console','csv-import',rows,date_range,note,label=label,method='ui-export-csv')
    print(json.dumps({'tool':'live-data-import-gsc','rowsImported':len(rows),'dateRange':date_range,'wrote':str(path)},indent=2))
    return 0

def import_ga4(root,csv_path,start,end,label):
    rows=[_normalize_row_keys(r) for r in _csv_rows(csv_path)]
    if _rows_have_secret(rows):
        print('ERROR: the CSV appears to contain a secret-like value; refusing to import.',file=sys.stderr); return 2
    _warn_if_no_dated_rows(rows,'GA4 CSV')
    date_range=_date_range_arg(start,end)
    note='Manual CSV export; a point-in-time snapshot, not a live feed. No credentials were read or stored. GA4 exports may be affected by consent-mode gaps, data thresholding, or sampling.'
    if not date_range: note+=' No date range was given (--start/--end); this import cannot be used for before/after measurement until one is known.'
    path,_=_write(root,'ga4','csv-import',rows,date_range,note,label=label,method='ui-export-csv')
    print(json.dumps({'tool':'live-data-import-ga4','rowsImported':len(rows),'dateRange':date_range,'wrote':str(path)},indent=2))
    return 0

def _zip_csv(z,name):
    with z.open(name) as f: return list(csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig')))

def import_gsc_zip(root,zip_path,start,end,label):
    try: z=zipfile.ZipFile(zip_path)
    except (zipfile.BadZipFile,OSError) as e:
        print(f'ERROR: could not open ZIP: {e}',file=sys.stderr); return 2
    with z:
        names=z.namelist()
        dates_name=next((n for n in names if n.lower().endswith('dates.csv')),None)
        if not dates_name:
            print('ERROR: the ZIP has no Dates.csv -- that is the only file in a GSC export with date-keyed daily totals, and it is what impact.py evaluates against. A Pages.csv/Queries.csv-only export cannot be used for before/after measurement.',file=sys.stderr); return 2
        dates_rows_raw=_zip_csv(z,dates_name)
        rows=[_normalize_row_keys(r) for r in dates_rows_raw]
        rows=[r for r in rows if r.get('date')]  # drop any row the header-normalization couldn't date-key
        date_range=_date_range_arg(start,end)
        if not date_range and rows:
            ds=sorted(r['date'] for r in rows)
            if ds: date_range={'start':ds[0],'end':ds[-1]}
        if not date_range:
            print('ERROR: could not determine a date range from Dates.csv, and none was given via --start/--end; refusing to import without a known date range.',file=sys.stderr); return 2
        if _rows_have_secret(dates_rows_raw):
            print('ERROR: the export appears to contain a secret-like value; refusing to import.',file=sys.stderr); return 2
    limits=('GSC UI ZIP export filtered by the export\'s own filters (see Filters.csv inside the ZIP); a point-in-time snapshot, not a live feed. '
            'rows[] holds Dates.csv\'s date-keyed daily totals (date/clicks/impressions/ctr/position) -- the data impact.py evaluates against. '
            'Pages.csv and Queries.csv breakdowns inside the ZIP are not imported as separate rows.')
    path,_=_write(root,'search-console',f'gsc-zip:{Path(zip_path).name}',rows,date_range,limits,label=label,method='ui-export-zip')
    print(json.dumps({'tool':'live-data-import-gsc-zip','rowsImported':len(rows),'dateRange':date_range,'wrote':str(path)},indent=2))
    return 0

def psi(root,url):
    key=os.environ.get('PSI_API_KEY')
    api=f'https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={urllib.request.quote(url,safe="")}'
    req=urllib.request.Request(api,headers={'X-goog-api-key':key} if key else {})
    try:
        with urllib.request.urlopen(req,timeout=20) as resp: data=json.loads(resp.read())
    except Exception as e:
        print(json.dumps({'tool':'live-data-psi','error':_redact(str(e)),'note':'PageSpeed Insights request failed; PSI_API_KEY is optional but rate limits are low without one.'},indent=2))
        return 1
    lh=data.get('lighthouseResult',{}); cats=lh.get('categories',{})
    scores={k:v.get('score') for k,v in cats.items()}
    path,_=_write(root,'psi',url,[scores],{'start':str(date.today()),'end':str(date.today())},'One fetched PageSpeed Insights run for one URL at one time, not a field-data trend.')
    print(json.dumps({'tool':'live-data-psi','url':url,'scores':scores,'wrote':str(path)},indent=2))
    return 0

def crux(root,origin):
    key=os.environ.get('CRUX_API_KEY')
    if not key:
        print(json.dumps({'tool':'live-data-crux','error':'CRUX_API_KEY not set in the environment.','note':'CrUX requires an API key; set CRUX_API_KEY and retry.'},indent=2))
        return 2
    api='https://chromeuxreport.googleapis.com/v1/records:queryRecord'
    body=json.dumps({'origin':origin}).encode()
    req=urllib.request.Request(api,data=body,headers={'Content-Type':'application/json','X-goog-api-key':key})
    try:
        with urllib.request.urlopen(req,timeout=20) as resp: data=json.loads(resp.read())
    except Exception as e:
        print(json.dumps({'tool':'live-data-crux','error':_redact(str(e))},indent=2)); return 1
    record=data.get('record',{}); metrics=record.get('metrics',{})
    period=record.get('collectionPeriod') or {}
    date_range={'start':period.get('firstDate',{}).get('year') and str(period['firstDate']),'end':period.get('lastDate',{}).get('year') and str(period['lastDate'])} if period else None
    path,_=_write(root,'crux',origin,[metrics],date_range,'CrUX field data: real-user aggregate, 28-day rolling window; not this run’s live traffic.')
    print(json.dumps({'tool':'live-data-crux','origin':origin,'metrics':metrics,'wrote':str(path)},indent=2))
    return 0

def main():
    q=argparse.ArgumentParser()
    sub=q.add_subparsers(dest='action',required=True)
    for name in ('import-gsc','import-ga4'):
        s=sub.add_parser(name); s.add_argument('project'); s.add_argument('csv_path'); s.add_argument('--start'); s.add_argument('--end'); s.add_argument('--label',choices=sorted(LABELS),default='site')
    s=sub.add_parser('import-gsc-zip'); s.add_argument('project'); s.add_argument('zip_path'); s.add_argument('--start'); s.add_argument('--end'); s.add_argument('--label',choices=sorted(LABELS),default='site')
    s=sub.add_parser('psi'); s.add_argument('project'); s.add_argument('url')
    s=sub.add_parser('crux'); s.add_argument('project'); s.add_argument('origin')
    a=q.parse_args()
    root=Path(a.project).resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    if a.action=='import-gsc': return import_gsc(root,a.csv_path,a.start,a.end,a.label)
    if a.action=='import-ga4': return import_ga4(root,a.csv_path,a.start,a.end,a.label)
    if a.action=='import-gsc-zip': return import_gsc_zip(root,a.zip_path,a.start,a.end,a.label)
    if a.action=='psi': return psi(root,a.url)
    if a.action=='crux': return crux(root,a.origin)
if __name__=='__main__': raise SystemExit(main())
