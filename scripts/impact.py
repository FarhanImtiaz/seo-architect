#!/usr/bin/env python3
"""Live-measurement feedback loop. Answers 'did this change measurably move anything' from
real imported data (scripts/live_data.py), honestly. This is the single highest-risk script in
the skill for implying causation it hasn't earned -- read references/measurement-methodology.md
before changing the verdict logic. Never fabricates data, never forecasts, never treats a plain
before/after difference as proof, and never lets the last few days of a partial week count as
settled. Impact results are never fed back into score.py: the 100-point score measures site
hygiene; this measures an observed, uncertainty-labeled outcome. Two different questions."""
import argparse,json,statistics,sys
from datetime import date,datetime,timedelta
from pathlib import Path

VERDICTS={
    'insufficient-data':'Not enough data yet to evaluate this change.',
    'confounded':'Cannot be attributed to this change: another change, event, or ranking incident overlaps the evaluation window.',
    'no-detectable-change':'The observed effect is within this site\'s own normal week-to-week variation (see minimumDetectableChange).',
    'change-consistent-with-hypothesis':'Observed, unusual relative to this site\'s own history; consistent with, not proof of, the change\'s effect.',
    'change-opposite-to-hypothesis':'Observed, unusual relative to this site\'s own history, but opposite in direction to the hypothesis; consistent with, not proof of, an effect.',
    'observed-sitewide-not-separable':'Observed change; with no control group, site-wide factors are not separable from this change\'s effect.',
}

def _changes_dir(root): return root/'.claude/seo/changes'
def _impact_dir(root): return root/'.claude/seo/impact'
def _events_path(root): return root/'.claude/seo/external-events.json'

def _load_change(root,change_id):
    p=_changes_dir(root)/f'{change_id}.json'
    if not p.exists(): return None,p
    return json.loads(p.read_text()),p

def _load_events(root):
    p=_events_path(root)
    if not p.exists(): return []
    try: return json.loads(p.read_text()).get('events',[])
    except json.JSONDecodeError as e:
        # Fail closed: a corrupt events file must never silently look like "no events", since
        # that silently disables confounder detection and can produce an overconfident verdict.
        raise RuntimeError(f'.claude/seo/external-events.json is not valid JSON: {e}. Fix or remove it before evaluating -- silently ignoring it would disable confounder detection.')

def cmd_mark(root,a):
    p=_changes_dir(root)/f'{a.id}.json'; p.parent.mkdir(parents=True,exist_ok=True)
    if p.exists() and not a.amend:
        print(f'ERROR: a change record for "{a.id}" already exists. Use --amend to modify windows/hypothesis (recorded in amendments[]); affectedUrls/deployedOn/description are otherwise fixed.',file=sys.stderr); return 2
    if p.exists() and a.amend:
        record=json.loads(p.read_text())
        amendment={'amendedOn':str(date.today()),'reason':a.amend}
        if a.pre_days: amendment['preDays']={'from':record['windows']['preDays'],'to':a.pre_days}; record['windows']['preDays']=a.pre_days
        if a.settle_days: amendment['settleDays']={'from':record['windows']['settleDays'],'to':a.settle_days}; record['windows']['settleDays']=a.settle_days
        if a.post_days: amendment['postDays']={'from':record['windows']['postDays'],'to':a.post_days}; record['windows']['postDays']=a.post_days
        record.setdefault('amendments',[]).append(amendment)
        p.write_text(json.dumps(record,indent=2)+'\n')
        print(json.dumps({'tool':'impact-mark','action':'amended','id':a.id,'amendments':record['amendments']},indent=2)); return 0
    if not a.deployed_on: print('ERROR: --deployed-on YYYY-MM-DD is required and must be user-confirmed, not guessed.',file=sys.stderr); return 2
    if not a.affected_urls: print('ERROR: --affected-urls (comma-separated) is required.',file=sys.stderr); return 2
    record={
        'id':a.id,'createdOn':str(date.today()),'deployedOn':a.deployed_on,'description':a.description or '',
        'affectedUrls':a.affected_urls.split(','),'controlUrls':a.control_urls.split(',') if a.control_urls else None,
        'hypothesis':{'metric':a.metric,'direction':a.direction},
        'windows':{'preDays':a.pre_days or 28,'settleDays':a.settle_days or 7,'postDays':a.post_days or 28},
        'minData':{'minPreClicks':a.min_pre_clicks or 50},
        'snapshotRef':a.snapshot_ref,'measurements':[],'amendments':[],
    }
    p.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'tool':'impact-mark','action':'created','id':a.id,'record':record},indent=2)); return 0

def cmd_import(root,a):
    record,p=_load_change(root,a.id)
    if record is None: print(f'ERROR: no change record "{a.id}"; run `mark` first.',file=sys.stderr); return 2
    mp=Path(a.measurement_file)
    if not mp.exists(): print(f'ERROR: measurement file not found: {mp}',file=sys.stderr); return 2
    try: payload=json.loads(mp.read_text())
    except json.JSONDecodeError: print('ERROR: measurement file is not valid JSON.',file=sys.stderr); return 2
    for field in ('source','rows'):
        if field not in payload: print(f'ERROR: measurement file is missing required field "{field}".',file=sys.stderr); return 2
    label=a.label or payload.get('label','site')
    if label not in ('treated','control','site'): print(f'ERROR: --label must be treated, control, or site (got {label!r}).',file=sys.stderr); return 2
    record.setdefault('measurements',[]).append({'path':str(mp.resolve().relative_to(root)) if mp.resolve().is_relative_to(root) else str(mp.resolve()),'label':label,'source':payload.get('source'),'dateRange':payload.get('dateRange'),'synthetic':bool(payload.get('synthetic',False)),'importedOn':payload.get('provenance',{}).get('importedOn') or str(date.today())})
    p.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'tool':'impact-import','id':a.id,'attached':record['measurements'][-1]},indent=2)); return 0

def cmd_status(root,a):
    record,p=_load_change(root,a.id)
    if record is None: print(f'ERROR: no change record "{a.id}".',file=sys.stderr); return 2
    deployed=datetime.strptime(record['deployedOn'],'%Y-%m-%d').date()
    eligible=deployed+timedelta(days=record['windows']['settleDays']+record['windows']['postDays'])
    print(json.dumps({'tool':'impact-status','id':a.id,'deployedOn':record['deployedOn'],'eligibleForEvaluationOn':str(eligible),'measurementsAttached':len(record.get('measurements',[])),'note':'This tool never auto-fetches data or schedules itself; re-run `evaluate` after this date once real data covers it, or use /schedule or /loop for a reminder.'},indent=2))
    return 0

def cmd_events(root,a):
    p=_events_path(root); data={'events':[]}
    if p.exists():
        try: data=json.loads(p.read_text())
        except json.JSONDecodeError as e:
            print(f'ERROR: .claude/seo/external-events.json is not valid JSON: {e}. Fix or remove it manually first -- refusing to overwrite it, since that would silently drop every existing event.',file=sys.stderr); return 2
    if a.events_action=='add':
        if not (a.date_ and a.description): print('ERROR: events add requires --date and --description.',file=sys.stderr); return 2
        data['events'].append({'date':a.date_,'description':a.description,'type':a.type_ or 'user-entered','source':'manual'})
        p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(data,indent=2)+'\n')
        print(json.dumps({'tool':'impact-events','action':'added','event':data['events'][-1]},indent=2)); return 0
    if a.events_action=='list':
        print(json.dumps(data,indent=2)); return 0
    if a.events_action=='fetch-google':
        print(json.dumps({'tool':'impact-events','action':'fetch-google','error':'Not run automatically. Re-invoke with the user\'s explicit approval; this build does not perform the network fetch without that approval gate being satisfied by the caller.'},indent=2)); return 1

MIN_PLACEBO_WINDOWS=8  # below this, empirical variance is too noisy to trust; cap at no-detectable-change
MDE_FLOOR=0.02  # a placebo band can never be narrower than this -- flat/near-zero-variance history must
                # not turn a trivial blip into a directional verdict (see references/measurement-methodology.md)

def _daily_totals(rows,metric):
    totals={}
    for r in rows:
        d=r.get('date'); v=r.get(metric)
        if d is None or v is None: continue
        try: v=float(v)
        except (TypeError,ValueError): continue
        totals[d]=totals.get(d,0.0)+v
    return totals

def _totals_for_entries(root,entries,metric):
    """Merge daily totals across every measurement file attached under one label, deduping by
    date so an overlapping re-import (e.g. a refreshed export) can never double-count a day --
    the file with the latest provenance.importedOn wins for any date both files cover. Fails
    closed (raises) on a missing or unparseable file rather than silently skipping it, since a
    silently-skipped file can quietly turn a real control group into an empty one."""
    per_file=[]
    for m in entries:
        mp=root/m['path'] if not Path(m['path']).is_absolute() else Path(m['path'])
        if not mp.exists(): raise RuntimeError(f"measurement file referenced by this change record is missing on disk: {m['path']}")
        try: payload=json.loads(mp.read_text())
        except json.JSONDecodeError as e: raise RuntimeError(f"measurement file is not valid JSON: {m['path']}: {e}")
        per_file.append((m.get('importedOn') or '',_daily_totals(payload.get('rows',[]),metric)))
    per_file.sort(key=lambda x:x[0])
    merged={}
    for _,totals in per_file: merged.update(totals)  # later (newer-imported) file wins on a shared date
    return merged

def _window_sum(totals,start,end):
    return sum(v for d,v in totals.items() if start<=datetime.strptime(d,'%Y-%m-%d').date()<end)

def _window_days_present(totals,start,end):
    return sum(1 for d in totals if start<=datetime.strptime(d,'%Y-%m-%d').date()<end)

def _date_span(totals):
    if not totals: return None,None
    ds=sorted(datetime.strptime(d,'%Y-%m-%d').date() for d in totals)
    return ds[0],ds[-1]

def _ratio(pre_sum,post_sum):
    if pre_sum<=0: return None
    return post_sum/pre_sum

def _placebo_ratios(totals,control_totals,pre_days,settle_days,post_days,before_date):
    """Slides the same pre/post window pair across history strictly before `before_date`,
    entirely within already-observed (pre-change) data, to build a null distribution of the
    same statistic the real evaluation computes -- this is what lets the verdict say 'unusual
    relative to this site's own history' instead of relying on an assumed distribution."""
    span_start,_=_date_span(totals)
    if span_start is None: return []
    ratios=[]; cursor=span_start+timedelta(days=pre_days)
    step=max(7,pre_days//4)
    while cursor+timedelta(days=settle_days+post_days)<=before_date:
        pre=_window_sum(totals,cursor-timedelta(days=pre_days),cursor)
        post=_window_sum(totals,cursor+timedelta(days=settle_days),cursor+timedelta(days=settle_days+post_days))
        r=_ratio(pre,post)
        if r is not None:
            if control_totals:
                cpre=_window_sum(control_totals,cursor-timedelta(days=pre_days),cursor)
                cpost=_window_sum(control_totals,cursor+timedelta(days=settle_days),cursor+timedelta(days=settle_days+post_days))
                cr=_ratio(cpre,cpost)
                if cr: ratios.append(r/cr)
            else:
                ratios.append(r)
        cursor+=timedelta(days=step)
    return ratios

def _find_confounders(root,record,window_start,window_end):
    """window_start/window_end must already span the FULL evaluation window including the
    pre-change baseline (deployedOn - preDays), not just [deployedOn, post_end] -- an event or
    overlapping change that happened just before deploy can depress the pre-window baseline and
    make an unrelated post-deploy recovery look like this change's effect (see H1 in the QA
    report this fix responds to)."""
    found=[]
    for e in _load_events(root):
        try: ed=datetime.strptime(e['date'],'%Y-%m-%d').date()
        except (KeyError,ValueError):
            raise RuntimeError(f'external-events.json contains an event with a missing/invalid date: {e!r}. Fix it before evaluating.')
        if window_start<=ed<=window_end: found.append({'type':'external-event','date':e['date'],'description':e.get('description','')})
    for p in _changes_dir(root).glob('*.json'):
        if p.stem==record['id']: continue
        try: other=json.loads(p.read_text())
        except json.JSONDecodeError as e:
            raise RuntimeError(f'change record {p.name} is not valid JSON: {e}. Fix or remove it before evaluating -- silently skipping it could hide a real confounder.')
        try:
            od=datetime.strptime(other['deployedOn'],'%Y-%m-%d').date()
            ostart=od-timedelta(days=other['windows']['preDays']); oend=od+timedelta(days=other['windows']['settleDays']+other['windows']['postDays'])
        except (KeyError,ValueError) as e:
            raise RuntimeError(f'change record {p.name} is missing or has an invalid deployedOn/windows field: {e}. Fix or remove it before evaluating.')
        overlaps_window=ostart<=window_end and oend>=window_start
        other_urls=set(other.get('affectedUrls',[]))
        touches_treated=bool(set(record.get('affectedUrls',[]))&other_urls)
        touches_control=bool(set(record.get('controlUrls') or [])&other_urls)
        no_control=not record.get('controlUrls')
        wildcard=other.get('affectedUrls')==['*']
        if overlaps_window and (touches_treated or touches_control or no_control or wildcard):
            touched='both' if (touches_treated and touches_control) else ('control' if touches_control else ('treated' if touches_treated else 'sitewide-no-control-group'))
            found.append({'type':'overlapping-change','id':other['id'],'deployedOn':other['deployedOn'],'touches':touched})
    return found

def cmd_evaluate(root,a):
    record,p=_load_change(root,a.id)
    if record is None: print(f'ERROR: no change record "{a.id}".',file=sys.stderr); return 2
    measurements=record.get('measurements',[])
    if any(m['synthetic'] for m in measurements) and not a.allow_synthetic:
        print('ERROR: at least one attached measurement is marked synthetic; refusing to evaluate real-looking output from test data. Pass --allow-synthetic only for tests.',file=sys.stderr); return 2
    treated=[m for m in measurements if m['label'] in ('treated','site')]
    control=[m for m in measurements if m['label']=='control']
    if not treated:
        print(json.dumps({'tool':'impact-evaluate','id':a.id,'verdict':'insufficient-data','reason':'No treated/site-labeled measurement has been imported yet.','amendments':record.get('amendments',[])},indent=2)); return 0
    metric=record['hypothesis']['metric']
    try:
        treated_totals=_totals_for_entries(root,treated,metric)
        control_totals=_totals_for_entries(root,control,metric) if control else None
    except RuntimeError as e:
        print(f'ERROR: {e}',file=sys.stderr); return 2
    deployed=datetime.strptime(record['deployedOn'],'%Y-%m-%d').date()
    pre_days,settle_days,post_days=record['windows']['preDays'],record['windows']['settleDays'],record['windows']['postDays']
    as_of=datetime.strptime(a.as_of,'%Y-%m-%d').date() if a.as_of else date.today()
    provisional_cutoff=as_of-timedelta(days=3)
    pre_start=deployed-timedelta(days=pre_days); post_start=deployed+timedelta(days=settle_days); post_end=deployed+timedelta(days=settle_days+post_days)
    span_start,span_end=_date_span(treated_totals)
    out={'tool':'impact-evaluate','id':a.id,'asOf':str(as_of),'amendments':record.get('amendments',[]),'primaryMetric':metric}
    if metric=='position': out['warning']='primaryMetric is average position, not a rank; direction and magnitude are reported but never treated as a rank change.'
    missing=[]
    if span_start is None or span_end is None or span_start>pre_start: missing.append(f'at least {pre_days} days of pre-change data')
    if post_end>provisional_cutoff: missing.append(f'the last 3 days before {a.as_of or "today"} are excluded as provisional, and the post window does not yet end before that')
    if span_end is not None and post_end>span_end: missing.append('imported data does not yet reach the end of the post window')
    if not missing:
        # Even when the data SPANS the windows, it can have gaps inside them (e.g. a partial
        # re-export) -- a gap must never read as a real traffic drop/gain. Count actual days
        # present, not just first/last date.
        treated_pre_present=_window_days_present(treated_totals,pre_start,deployed)
        treated_post_present=_window_days_present(treated_totals,post_start,post_end)
        if treated_pre_present<pre_days: missing.append(f'treated pre-window {metric} data has gaps: {treated_pre_present}/{pre_days} days present')
        if treated_post_present<post_days: missing.append(f'treated post-window {metric} data has gaps: {treated_post_present}/{post_days} days present')
    if missing:
        out['verdict']='insufficient-data'; out['missing']=missing; print(json.dumps(out,indent=2)); return 0
    pre_sum=_window_sum(treated_totals,pre_start,deployed)
    if pre_sum<record.get('minData',{}).get('minPreClicks',50):
        out['verdict']='insufficient-data'; out['missing']=[f'treated pre-window {metric} total ({pre_sum:g}) is below the minimum ({record["minData"]["minPreClicks"]})']
        print(json.dumps(out,indent=2)); return 0
    cpre=cpost=None
    if control_totals is not None:  # a control was attached (an EMPTY dict for zero rows still counts) -- see H3
        control_pre_present=_window_days_present(control_totals,pre_start,deployed)
        control_post_present=_window_days_present(control_totals,post_start,post_end)
        cpre=_window_sum(control_totals,pre_start,deployed); cpost=_window_sum(control_totals,post_start,post_end)
        # A control group that's incomplete or empty in the window can't support ANY verdict --
        # it must never silently fall through to a confident "no-detectable-change" (H3).
        if control_pre_present<pre_days or control_post_present<post_days or cpre<=0 or cpost<=0:
            out['verdict']='insufficient-data'
            out['missing']=[f'control-group {metric} data is incomplete or empty in the evaluation window (pre: {control_pre_present}/{pre_days} days, total {cpre:g}; post: {control_post_present}/{post_days} days, total {cpost:g})']
            print(json.dumps(out,indent=2)); return 0
    try:
        confounders=_find_confounders(root,record,pre_start,post_end)  # H1: window starts at the pre-change baseline, not deployedOn
    except RuntimeError as e:
        print(f'ERROR: {e}',file=sys.stderr); return 2
    post_sum=_window_sum(treated_totals,post_start,post_end)
    treated_ratio=_ratio(pre_sum,post_sum)
    out['observed']={'treatedPreSum':pre_sum,'treatedPostSum':post_sum,'treatedRatio':round(treated_ratio,4) if treated_ratio else None}
    if confounders:
        out['verdict']='confounded'; out['confounders']=confounders; out['note']=VERDICTS['confounded']
        print(json.dumps(out,indent=2)); return 0
    if control_totals is None:
        out['verdict']='observed-sitewide-not-separable'; out['note']=VERDICTS['observed-sitewide-not-separable']
        print(json.dumps(out,indent=2)); return 0
    control_ratio=_ratio(cpre,cpost)
    effect=treated_ratio/control_ratio if control_ratio else None
    out['observed']['controlRatio']=round(control_ratio,4) if control_ratio else None; out['observed']['effect']=round(effect,4) if effect else None
    placebo=_placebo_ratios(treated_totals,control_totals,pre_days,settle_days,post_days,deployed)
    if len(placebo)<12: out.setdefault('limitations',[]).append(f'Only {len(placebo)} placebo window(s) available in pre-change history; resolution is limited.')
    if len(placebo)>=MIN_PLACEBO_WINDOWS:
        median=statistics.median(placebo); mde=max(statistics.pstdev(placebo)*2,MDE_FLOOR)
        band=(median-mde,median+mde)
        out['placebo']={'windowCount':len(placebo),'median':round(median,4),'minimumDetectableChange':round(mde,4),'band':[round(band[0],4),round(band[1],4)]}
        within_band=band[0]<=effect<=band[1] if effect is not None else True
    else:
        # Below MIN_PLACEBO_WINDOWS there's no reliable empirical distribution to compare
        # against. The old fallback assumed a fixed +/-15%-of-median band here, which
        # references/measurement-methodology.md explicitly says this method never does (it's
        # supposed to be empirical, not assumed) -- so instead of guessing, cap the verdict.
        within_band=True
        out['placebo']={'windowCount':len(placebo),'note':f'Fewer than {MIN_PLACEBO_WINDOWS} placebo windows are available ({len(placebo)} found) in this site\'s pre-change history; resolution is too limited to bound normal variation, so no directional verdict is issued.'}
    if effect is None or within_band:
        out['verdict']='no-detectable-change'; out['note']=VERDICTS['no-detectable-change']
    else:
        direction=record['hypothesis']['direction']; observed_direction='increase' if effect>1 else 'decrease'
        out['verdict']='change-consistent-with-hypothesis' if observed_direction==direction else 'change-opposite-to-hypothesis'
        out['note']=VERDICTS[out['verdict']]
    print(json.dumps(out,indent=2))
    idir=_impact_dir(root); idir.mkdir(parents=True,exist_ok=True)
    (idir/f'{a.id}-{a.as_of or date.today()}.json').write_text(json.dumps(out,indent=2)+'\n')
    return 0

def main():
    q=argparse.ArgumentParser()
    sub=q.add_subparsers(dest='action',required=True)
    m=sub.add_parser('mark'); m.add_argument('project'); m.add_argument('--id',required=True); m.add_argument('--description'); m.add_argument('--deployed-on'); m.add_argument('--affected-urls'); m.add_argument('--control-urls'); m.add_argument('--metric',default='clicks',choices=['clicks','impressions','ctr','position']); m.add_argument('--direction',default='increase',choices=['increase','decrease']); m.add_argument('--pre-days',type=int); m.add_argument('--settle-days',type=int); m.add_argument('--post-days',type=int); m.add_argument('--min-pre-clicks',type=int); m.add_argument('--snapshot-ref'); m.add_argument('--amend')
    i=sub.add_parser('import'); i.add_argument('project'); i.add_argument('id'); i.add_argument('measurement_file'); i.add_argument('--label',choices=['treated','control','site'])
    s=sub.add_parser('status'); s.add_argument('project'); s.add_argument('id')
    e=sub.add_parser('evaluate'); e.add_argument('project'); e.add_argument('id'); e.add_argument('--allow-synthetic',action='store_true'); e.add_argument('--as-of')
    ev=sub.add_parser('events'); ev.add_argument('project'); ev.add_argument('events_action',choices=['add','list','fetch-google']); ev.add_argument('--date',dest='date_'); ev.add_argument('--description'); ev.add_argument('--type',dest='type_')
    a=q.parse_args()
    root=Path(a.project).resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    return {'mark':cmd_mark,'import':cmd_import,'status':cmd_status,'evaluate':cmd_evaluate,'events':cmd_events}[a.action](root,a)
if __name__=='__main__': raise SystemExit(main())
