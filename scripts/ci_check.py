#!/usr/bin/env python3
"""CI/PR-time SEO regression check: runs full_audit.py+score.py on a base ref/dir and on the
current project, diffs the findings, and reports what changed. No network, no secrets required
by default -- everything here is the same static evidence full_audit.py already produces."""
import argparse,json,re,shutil,subprocess,sys,tarfile,tempfile
from datetime import date
from pathlib import Path
HERE=Path(__file__).resolve().parent

def run_audit(root):
    # full_audit.py --score writes .claude/seo/baseline.json into whatever directory it's pointed
    # at as a side effect of --snapshot. A CI check must never mutate the caller's real project
    # state (their actual regression baseline) just by being run -- so this always audits a
    # throwaway copy, never `root` itself, regardless of whether `root` is the real working tree
    # or an already-disposable git-archive extraction.
    scratch=Path(tempfile.mkdtemp(prefix='seo-ci-audit-'))
    try:
        shutil.copytree(root,scratch,dirs_exist_ok=True)
        p=subprocess.run([sys.executable,str(HERE/'full_audit.py'),str(scratch),'--score'],capture_output=True,text=True)
    finally:
        shutil.rmtree(scratch,ignore_errors=True)
    try: return json.loads(p.stdout)
    except json.JSONDecodeError:
        return {'error':'full_audit.py did not emit JSON','stderr':p.stderr.strip()}

def checkout_ref(ref,project_root):
    tmp=Path(tempfile.mkdtemp(prefix='seo-ci-base-'))
    archive=tmp/'archive.tar'
    with open(archive,'wb') as fh:
        p=subprocess.run(['git','-C',str(project_root),'archive',ref],stdout=fh,stderr=subprocess.PIPE)
    if p.returncode!=0:
        shutil.rmtree(tmp,ignore_errors=True)
        raise SystemExit(f'ERROR: git archive {ref} failed: {p.stderr.decode(errors="ignore")}')
    with tarfile.open(archive) as t: t.extractall(tmp)
    archive.unlink()
    return tmp

def fingerprint(tool,f):
    return '|'.join([tool,str(f.get('severity','')),(f.get('issue') or f.get('problem') or '').strip(),(f.get('file') or f.get('route') or '').strip()])

def all_findings(audit):
    out=[]
    for tool,check in audit.get('checks',{}).items():
        for f in check.get('result',{}).get('findings',[]):
            if isinstance(f,dict) and 'severity' in f: out.append((tool,f))
    return out

def routes_of(audit):
    return {f['route'] for f in audit.get('checks',{}).get('routes',{}).get('result',{}).get('findings',[]) if 'route' in f}

def redirect_sources_of(audit):
    check=audit.get('checks',{}).get('redirects')
    if not check: return None  # Phase 11's scan_redirects.py not present in this TOOLS set yet
    return {o['source'].lstrip('/') for o in check.get('result',{}).get('observed',[]) if 'source' in o}

def diff_audits(base,head):
    base_pairs=all_findings(base); head_pairs=all_findings(head)
    base_map={fingerprint(t,f):(t,f) for t,f in base_pairs}
    head_map={fingerprint(t,f):(t,f) for t,f in head_pairs}
    new_fps=set(head_map)-set(base_map); resolved_fps=set(base_map)-set(head_map)
    d={'newFindings':[{'tool':t,**f} for fp,(t,f) in head_map.items() if fp in new_fps],
       'resolvedFindings':[{'tool':t,**f} for fp,(t,f) in base_map.items() if fp in resolved_fps]}
    base_routes=routes_of(base); head_routes=routes_of(head)
    d['routesRemoved']=sorted(base_routes-head_routes); d['routesAdded']=sorted(head_routes-base_routes)
    redirect_sources=redirect_sources_of(head)
    d['unresolvedRemovedRoutes']=(d['routesRemoved'] if redirect_sources is None
        else [r for r in d['routesRemoved'] if r.lstrip('/') not in redirect_sources])
    bh=base.get('score',{}).get('rubricHash'); hh=head.get('score',{}).get('rubricHash')
    if bh and hh and bh!=hh: d['rubricComparable']=False; d['scoreDelta']=None
    else:
        d['rubricComparable']=True
        bs=base.get('score',{}).get('score'); hs=head.get('score',{}).get('score')
        d['scoreDelta']=round(hs-bs,1) if bs is not None and hs is not None else None
    return d

def apply_ignores(d,cfg):
    today=date.today().isoformat(); active=[]; expired=[]
    for ig in cfg.get('ignore',[]):
        (expired if ig.get('expires') and ig['expires']<today else active).append(ig)
    active_fps={ig['fingerprint'] for ig in active if 'fingerprint' in ig}
    d['newFindings']=[f for f in d['newFindings'] if fingerprint(f['tool'],f) not in active_fps]
    return expired

def rule_triggers(d,cfg):
    fail_on=set(cfg.get('failOn',[])); triggers=[]
    def new_has(sev): return any(f.get('severity')==sev for f in d['newFindings'])
    def new_issue_has(*needles): return any(any(n in (f.get('issue') or '').lower() for n in needles) for f in d['newFindings'])
    if 'new-critical' in fail_on and new_has('CRITICAL'): triggers.append('new-critical')
    if 'new-high' in fail_on and new_has('HIGH'): triggers.append('new-high')
    if 'route-removed-without-redirect' in fail_on and d['unresolvedRemovedRoutes']: triggers.append('route-removed-without-redirect')
    if 'noindex-added' in fail_on and new_issue_has('noindex'): triggers.append('noindex-added')
    if 'robots-disallow-all' in fail_on and new_issue_has('disallows all crawling'): triggers.append('robots-disallow-all')
    if 'canonical-changed' in fail_on and new_issue_has('canonical'): triggers.append('canonical-changed')
    if 'jsonld-invalid' in fail_on and any(f.get('tool')=='jsonld' and f.get('severity') in ('HIGH','CRITICAL') for f in d['newFindings']): triggers.append('jsonld-invalid')
    tol=cfg.get('scoreDropTolerance')
    if tol is not None and d.get('scoreDelta') is not None and d['scoreDelta']<-abs(tol): triggers.append('score-drop')
    return triggers

def markdown_summary(d,triggers,expired):
    lines=['# SEO Architect CI check','']
    lines.append('_Rubric version changed between base and head; category deltas not comparable._' if not d['rubricComparable']
        else f"Score delta: {d['scoreDelta']}" if d['scoreDelta'] is not None else 'Score delta: n/a')
    lines.append('')
    lines.append(f"**{len(d['newFindings'])} new finding(s)**" if d['newFindings'] else 'No new findings.')
    for f in d['newFindings'][:50]: lines.append(f"- `{f.get('severity')}` {f.get('tool')}: {f.get('issue','')} ({f.get('file','')})")
    if d['unresolvedRemovedRoutes']:
        lines.append(''); lines.append(f"**Routes removed without a matching redirect:** {', '.join(d['unresolvedRemovedRoutes'])}")
    if expired:
        lines.append(''); lines.append(f"**{len(expired)} ignore rule(s) expired and were NOT applied:** "+', '.join(i.get('reason','(no reason given)') for i in expired))
    if triggers:
        lines.append(''); lines.append(f"**Failing rules:** {', '.join(triggers)}")
    return '\n'.join(lines)+'\n'

def annotations(d):
    out=[]
    for f in d['newFindings']:
        if f.get('severity') in ('CRITICAL','HIGH'):
            level='error' if f.get('severity')=='CRITICAL' else 'warning'
            loc=f" file={f['file']}" if f.get('file') else ''
            out.append(f"::{level}{loc}::{f.get('tool')}: {f.get('issue','')}")
    return out

def to_sarif(d):
    rules={}; results=[]
    for f in d['newFindings']:
        rule_id=(f.get('tool','seo')+':'+re.sub(r'\W+','-',(f.get('issue') or 'finding')[:40]).strip('-').lower()) or 'seo:finding'
        rules[rule_id]={'id':rule_id,'shortDescription':{'text':f.get('issue','')}}
        level={'CRITICAL':'error','HIGH':'error','MEDIUM':'warning'}.get(f.get('severity'),'note')
        loc=[{'physicalLocation':{'artifactLocation':{'uri':f['file']}}}] if f.get('file') else []
        results.append({'ruleId':rule_id,'level':level,'message':{'text':f.get('issue','')},'locations':loc})
    return {'version':'2.1.0','$schema':'https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json',
            'runs':[{'tool':{'driver':{'name':'seo-architect','informationUri':'https://github.com','rules':list(rules.values())}},'results':results}]}

def load_cfg(root):
    p=root/'.claude/seo/ci.json'
    if p.exists():
        try: return json.loads(p.read_text())
        except json.JSONDecodeError: print(f'WARNING: {p} is not valid JSON; using defaults.',file=sys.stderr)
    return {'failOn':['new-critical','new-high','route-removed-without-redirect','robots-disallow-all'],'ignore':[]}

def main():
    q=argparse.ArgumentParser()
    q.add_argument('project',nargs='?',default='.')
    q.add_argument('--base-ref'); q.add_argument('--base-dir')
    q.add_argument('--summary-out'); q.add_argument('--sarif')
    a=q.parse_args(); root=Path(a.project).resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    if not a.base_ref and not a.base_dir:
        print('ERROR: pass --base-ref <git ref> or --base-dir <path> to compare against.',file=sys.stderr); return 2
    tmp=None
    base_root=Path(a.base_dir).resolve() if a.base_dir else (tmp:=checkout_ref(a.base_ref,root))
    try:
        base_audit=run_audit(base_root); head_audit=run_audit(root)
    finally:
        if tmp: shutil.rmtree(tmp,ignore_errors=True)
    if 'error' in base_audit or 'error' in head_audit:
        print(json.dumps({'tool':'ci-check','error':'audit failed to run on base or head','base':base_audit.get('error'),'head':head_audit.get('error')},indent=2)); return 2
    cfg=load_cfg(root)
    d=diff_audits(base_audit,head_audit)
    expired=apply_ignores(d,cfg)
    triggers=rule_triggers(d,cfg)
    out={'tool':'ci-check','diff':d,'failOn':sorted(cfg.get('failOn',[])),'triggers':triggers,'expiredIgnores':expired}
    print(json.dumps(out,indent=2))
    for line in annotations(d): print(line)
    if a.summary_out: Path(a.summary_out).write_text(markdown_summary(d,triggers,expired))
    if a.sarif: Path(a.sarif).write_text(json.dumps(to_sarif(d),indent=2))
    return 1 if triggers else 0
if __name__=='__main__':raise SystemExit(main())
