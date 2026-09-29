#!/usr/bin/env python3
import json, subprocess, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; TOOLS=ROOT/'scripts/seo_tools.py'; INIT=ROOT/'scripts/init_state.py'; FIX=ROOT/'tests/fixtures/site'; HOOK=ROOT/'scripts/guardian_hook.py'; LEDGER=ROOT/'scripts/evidence_ledger.py'; CONTRACT=ROOT/'scripts/validate_page_contract.py'; FRAMEWORK=ROOT/'scripts/framework_inspect.py'; ADAPTERS=ROOT/'scripts/framework_adapters.py'; AEO=ROOT/'scripts/validate_aeo.py'; FULL=ROOT/'scripts/full_audit.py'; CLAUDE=ROOT/'scripts/validate_claude_skill.py'; SCORE=ROOT/'scripts/score.py'; VALSRC=ROOT/'scripts/validate_sources.py'; PATTERNMATCH=ROOT/'scripts/pattern_match.py'; LINKGRAPH=ROOT/'scripts/scan_link_graph.py'; IMAGES=ROOT/'scripts/scan_images.py'; METAEXTRACT=ROOT/'scripts/metadata_extract.py'; HREFLANG=ROOT/'scripts/validate_hreflang.py'; LIVEDATA=ROOT/'scripts/live_data.py'; CI=ROOT/'scripts/ci_check.py'; REDIRECTS=ROOT/'scripts/scan_redirects.py'; CANONICALS=ROOT/'scripts/scan_canonicals.py'; FRESHNESS=ROOT/'scripts/scan_freshness.py'; RENDERDIFF=ROOT/'scripts/render_diff.py'; SCANLOGS=ROOT/'scripts/scan_logs.py'
def run(*args, ok=(0,)):
 p=subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True)
 if p.returncode not in ok: raise AssertionError(f'{args}: {p.returncode}\n{p.stdout}\n{p.stderr}')
 return p.stdout

TESTS=[]
def test(fn): TESTS.append(fn); return fn

@test
def state_and_validators():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True)
  out=json.loads(run(INIT,'--project',p)); assert (p/'.claude/seo/config.json').exists() and out['created']
  assert (p/'.claude/seo/evidence.json').exists()
  for cmd in ('routes','metadata','sitemap','robots','jsonld','links'): json.loads(run(TOOLS,cmd,p))

@test
def framework_adapters_detect_and_full_audit():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True)
  assert json.loads(run(ADAPTERS,p,ok=(0,1)))['observed']
  all_results=json.loads(run(FULL,p,'--snapshot',ok=(0,1))); assert set(('metadata','aeo','regression')).issubset(all_results['checks'])

@test
def framework_adapters_next_metadata_bug_fixed():
 fx=ROOT/'tests/fixtures/next-app'
 data=json.loads(run(ADAPTERS,fx,ok=(0,1)))
 medium=[x for x in data['findings'] if x['severity']=='MEDIUM']
 assert any(x['file']=='app/about/page.tsx' for x in medium), 'missing-metadata page must be flagged'
 assert not any(x['file']=='app/contact/page.tsx' for x in medium), 'page with export const metadata must not be flagged'

@test
def framework_adapters_next_nuxt_disambiguated():
 fx=ROOT/'tests/fixtures/nuxt-app'
 data=json.loads(run(ADAPTERS,fx,ok=(0,1)))
 adapters={x['adapter'] for x in data['observed']}
 assert adapters=={'nuxt'}, f'nuxt project must not also be classified as nextjs, got {adapters}'

@test
def aeo_signals():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True)
  subprocess.run(['cp',str(ROOT/'tests/fixtures/aeo-page.html'),str(p/'app/aeo-page.html')],check=True)
  aeo=json.loads(run(AEO,p)); assert any(x['signals']['questionHeading'] and x['signals']['comparison'] for x in aeo['pages'])

@test
def regression_snapshot_and_compare():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True)
  baseline=json.loads(run(TOOLS,'snapshot',p)); assert baseline['snapshot']['version']==2 and baseline['snapshot']['pages']
  page=p/'app/page.html'; page.write_text(page.read_text().replace('Example</title>','Changed</title>')); data=json.loads(run(TOOLS,'compare',p,ok=(0,1))); assert any('title' in x['issue'] for x in data['findings'])
  page.unlink(); data=json.loads(run(TOOLS,'compare',p,ok=(0,1))); assert any(x['severity']=='HIGH' for x in data['findings'])

@test
def guardian_hook_asks_and_allows():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True)
  event={'tool_input':{'file_path':str(p/'robots.txt'),'new_string':'User-agent: *\nDisallow: /'}}
  result=subprocess.run([sys.executable,str(HOOK)],input=json.dumps(event),capture_output=True,text=True,check=True); assert json.loads(result.stdout)['hookSpecificOutput']['permissionDecision']=='ask'
  event={'tool_input':{'file_path':str(p/'components/Button.tsx'),'new_string':'color: red'}}
  result=subprocess.run([sys.executable,str(HOOK)],input=json.dumps(event),capture_output=True,text=True,check=True); assert not result.stdout.strip()

@test
def guardian_hook_catches_previously_missed_high_risk_edits():
 # H5: a Fable-5.1 QA pass found these all silently passed through as "allow" -- case-sensitive
 # substring matching missed capitalized/whitespace-variant JSON-LD, and several entire file
 # types (next.config.js, vercel.json, netlify.toml, .htaccess) and canonical removals were
 # never inspected at all.
 def ask(event):
  r=subprocess.run([sys.executable,str(HOOK)],input=json.dumps(event),capture_output=True,text=True,check=True)
  out=json.loads(r.stdout) if r.stdout.strip() else {}
  return out.get('hookSpecificOutput',{}).get('permissionDecision')
 cases=[
  {'tool_input':{'file_path':'/app/page.tsx','content':'{"@type":"AggregateRating","ratingValue":4.5}'}},
  {'tool_input':{'file_path':'/app/page.tsx','content':'{"@type": "Review"}'}},
  {'tool_input':{'file_path':'/next.config.js','content':'module.exports={ redirects(){ return [{source:"/a",destination:"/b",permanent:true}] } }'}},
  {'tool_input':{'file_path':'/vercel.json','content':'{"redirects":[{"source":"/a","destination":"/b"}]}'}},
  {'tool_input':{'file_path':'/.htaccess','content':'Redirect 301 /old /new'}},
  {'tool_input':{'file_path':'/app/page.tsx','content':'export const metadata = { alternates: { canonical: "https://x.com/a" } }'}},
  {'tool_input':{'file_path':'/app/page.tsx','old_string':'<link rel="canonical" href="https://x.com/a">','new_string':'<div>x</div>'}},
 ]
 for event in cases: assert ask(event)=='ask', f'must ask for review: {event}'
 assert ask({'tool_input':{'file_path':'/src/components/Button.tsx','content':'export default function Button(){return null}'}}) is None, 'an ordinary unrelated file must still pass through untouched'

@test
def evidence_ledger_and_page_contracts():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True)
  run(LEDGER,'add',p,'--claim','A verified service exists','--source','project brief'); assert json.loads(run(LEDGER,'verify',p))['result']=='pass'
  assert json.loads(run(CONTRACT,'service','--brief',ROOT/'tests/fixtures/service-brief.json'))['result']=='pass'
  assert json.loads(run(CONTRACT,'location','--brief',ROOT/'tests/fixtures/location-brief.json'))['result']=='pass'

@test
def framework_detection_and_skill_validation():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True)
  assert json.loads(run(FRAMEWORK,p))['framework'] in ('unknown','nextjs')
  assert 'PASS' in run(CLAUDE,ROOT)

@test
def schema_per_type_validation():
 SCHEMA=ROOT/'tests/fixtures/schema'
 def jsonld_findings(name):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); subprocess.run(['cp',str(SCHEMA/name),str(p/name)],check=True)
   return json.loads(run(TOOLS,'jsonld',p,ok=(0,1)))['findings']
 f=jsonld_findings('product-no-offers.html')
 assert any(x['severity']=='HIGH' and x['rule']=='missing-required' for x in f), 'Product with no offers/review/aggregateRating must be HIGH'
 f=jsonld_findings('article-ok.html')
 assert not any(x['severity'] in ('HIGH','CRITICAL') for x in f), 'complete Article must not raise HIGH/CRITICAL findings'
 f=jsonld_findings('rating-not-visible.html')
 assert any(x['severity']=='MEDIUM' and x['rule']=='visible-alignment' for x in f), 'schema values absent from visible text must be flagged MEDIUM'
 f=jsonld_findings('graph.html')
 assert not any(x['severity'] in ('HIGH','CRITICAL') for x in f), '@graph must parse without spurious errors'
 f=jsonld_findings('faq.html')
 assert any(x['severity']=='INFO' and x['rule']=='volatile' for x in f), 'FAQPage must carry the volatile-eligibility note'

@test
def live_data_imports_csv_and_redacts_and_skips_offline():
 LD=ROOT/'tests/fixtures/live-data'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  out=json.loads(run(LIVEDATA,'import-gsc',p,LD/'gsc-export.csv','--start','2026-01-01','--end','2026-01-14','--label','treated',ok=(0,)))
  assert out['rowsImported']==2 and out['dateRange']=={'start':'2026-01-01','end':'2026-01-14'}
  written=list((p/'.claude/seo/measurement/raw').glob('search-console-*.json'))
  assert len(written)==1
  saved=json.loads(written[0].read_text())
  assert saved['source']=='search-console' and len(saved['rows'])==2 and saved['label']=='treated'
  assert (p/'.claude/seo/measurement/index.json').exists()
  r=subprocess.run([sys.executable,str(LIVEDATA),'import-gsc',str(p),str(LD/'gsc-export-with-secret.csv')],capture_output=True,text=True)
  assert r.returncode==2 and 'secret' in (r.stdout+r.stderr).lower()
  env=dict(**{k:v for k,v in __import__('os').environ.items() if k!='CRUX_API_KEY'})
  r=subprocess.run([sys.executable,str(LIVEDATA),'crux',str(p),'example.com'],capture_output=True,text=True,env=env)
  assert r.returncode==2, 'crux without CRUX_API_KEY must fail closed, never silently fabricate field data'
  assert 'CRUX_API_KEY' in r.stdout

@test
def live_data_no_date_range_is_marked_unspecified_and_key_never_leaks():
 LD=ROOT/'tests/fixtures/live-data'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  out=json.loads(run(LIVEDATA,'import-gsc',p,LD/'gsc-export.csv',ok=(0,)))
  assert out['dateRange'] is None
  first=list((p/'.claude/seo/measurement/raw').glob('search-console-*.json'))
  out2=json.loads(run(LIVEDATA,'import-gsc',p,LD/'gsc-export.csv','--label','control',ok=(0,)))
  second=list((p/'.claude/seo/measurement/raw').glob('search-console-*.json'))
  assert len(second)==len(first)+1, 'a second same-day import with a different label must not collide with/overwrite the first'
  env=dict(**{k:v for k,v in __import__('os').environ.items()},PSI_API_KEY='AIzaTestKeyShouldNeverLeak1234567890')
  r=subprocess.run([sys.executable,str(LIVEDATA),'psi',str(p),'http://example.invalid/'],capture_output=True,text=True,env=env)
  assert 'AIzaTestKeyShouldNeverLeak' not in (r.stdout+r.stderr), 'API key must never appear in output/stderr, whether via URL or an error message'

@test
def live_data_secret_scan_covers_every_row_not_just_the_first_five():
 LD=ROOT/'tests/fixtures/live-data'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  r=subprocess.run([sys.executable,str(LIVEDATA),'import-gsc',str(p),str(LD/'gsc-export-secret-row-7.csv')],capture_output=True,text=True)
  assert r.returncode==2 and 'secret' in (r.stdout+r.stderr).lower(), 'a secret on row 7 must be caught, not just the first 5 rows'

@test
def live_data_secret_scanner_catches_quoted_key_value_shapes():
 # H6: the old regex ran against json.dumps(row), whose quoted-key form ("api_key": "...")
 # broke the old `api[_-]?key\s*[:=]` pattern (the quote sits between the key and the colon),
 # so a CSV column literally named api_key/password/client_secret sailed through undetected.
 LD=ROOT/'tests/fixtures/live-data'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  csv_path=Path(d)/'quoted-key-secret.csv'
  csv_path.write_text('page,clicks,api_key\n/a,5,not-a-real-key-but-value-shaped\n')
  r=subprocess.run([sys.executable,str(LIVEDATA),'import-gsc',str(p),str(csv_path)],capture_output=True,text=True)
  assert r.returncode==2 and 'secret' in (r.stdout+r.stderr).lower(), f'a plain api_key column must be caught even though json.dumps() quotes the key: {r.stdout}{r.stderr}'
  benign=Path(d)/'benign.csv'; benign.write_text('page,clicks\n/a,5\n/b,10\n')
  out=json.loads(run(LIVEDATA,'import-gsc',p,benign,ok=(0,)))
  assert out['rowsImported']==2, 'ordinary rows with no secret-shaped values must still import cleanly'

@test
def live_data_gsc_zip_derives_date_range_and_refuses_without_one():
 LD=ROOT/'tests/fixtures/live-data'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  out=json.loads(run(LIVEDATA,'import-gsc-zip',p,LD/'gsc-export.zip',ok=(0,)))
  assert out['dateRange']=={'start':'2026-01-01','end':'2026-01-14'}, 'date range must come from Dates.csv when not given explicitly'
  r=subprocess.run([sys.executable,str(LIVEDATA),'import-gsc-zip',str(p),str(LD/'gsc-export-no-dates.zip')],capture_output=True,text=True)
  assert r.returncode==2 and 'dates.csv' in (r.stdout+r.stderr).lower(), 'must refuse a ZIP with no Dates.csv'
  # H4 fix: Dates.csv is the ONLY file with date-keyed daily rows impact.py can evaluate against
  # (Pages.csv/Queries.csv have no date column) -- an explicit --start/--end can't manufacture
  # data that isn't there, so this must still be refused, not silently "succeed" with unusable rows.
  r2=subprocess.run([sys.executable,str(LIVEDATA),'import-gsc-zip',str(p),str(LD/'gsc-export-no-dates.zip'),'--start','2026-03-01','--end','2026-03-14'],capture_output=True,text=True)
  assert r2.returncode==2 and 'dates.csv' in (r2.stdout+r2.stderr).lower(), 'an explicit date range must not bypass the missing-Dates.csv refusal'
  # the end-to-end pipeline must actually work now: import a real-shaped ZIP, attach it to a
  # change record, and confirm evaluate() does NOT dead-end at insufficient-data.
  out3=json.loads(run(LIVEDATA,'import-gsc-zip',p,LD/'gsc-export.zip','--label','site',ok=(0,)))
  assert out3['rowsImported']==2 and out3['dateRange']=={'start':'2026-01-01','end':'2026-01-14'}
  wrote=json.loads(Path(out3['wrote']).read_text())
  assert wrote['rows'] and 'date' in wrote['rows'][0] and 'clicks' in wrote['rows'][0], f'imported rows must be date-keyed and usable by impact.py, not the old Pages/Queries rows with no date field: {wrote["rows"]}'

@test
def seo_tools_noindex_tightened_and_named_snapshot_written():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True)
  mentions=p/'app/mentions-noindex/page.html'; mentions.parent.mkdir(parents=True,exist_ok=True)
  mentions.write_text('<html><head><title>About noindex tags</title></head><body><h1>About noindex tags</h1><p>This page explains what noindex means.</p></body></html>')
  actually_noindexed=p/'app/private/page.html'; actually_noindexed.parent.mkdir(parents=True,exist_ok=True)
  actually_noindexed.write_text('<html><head><title>Private</title><meta name="robots" content="noindex,nofollow"></head><body><h1>Private</h1></body></html>')
  out=json.loads(run(TOOLS,'snapshot',p,ok=(0,)))
  pages={pg['source']:pg for pg in out['snapshot']['pages']}
  assert pages['app/mentions-noindex/page.html']['noindex'] is False, 'mentioning the word "noindex" in prose must not be flagged'
  assert pages['app/private/page.html']['noindex'] is True, 'an actual <meta name="robots" content="noindex"> must still be flagged'
  out2=json.loads(run(TOOLS,'snapshot',p,'--name','pre-change',ok=(0,)))
  assert out2['namedFile'] and Path(out2['namedFile']).exists()
  assert list((p/'.claude/seo/snapshots').glob('*.json')), 'named snapshot must be written under .claude/seo/snapshots/'

@test
def validator_flags_dev_null_hook_suppression_and_rubric_changelog_mismatch():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(ROOT)+'/.',str(p)],check=True)
  skill=p/'SKILL.md'; text=skill.read_text()
  skill.write_text(text.replace('|| true','2>/dev/null || true',1))
  r=subprocess.run([sys.executable,str(CLAUDE),str(p)],capture_output=True,text=True)
  assert r.returncode==1 and '/dev/null' in r.stdout
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(ROOT)+'/.',str(p)],check=True)
  rubric=p/'scripts/rubric.json'; data=json.loads(rubric.read_text()); data['version']=999; rubric.write_text(json.dumps(data))
  r=subprocess.run([sys.executable,str(CLAUDE),str(p)],capture_output=True,text=True)
  assert r.returncode==1 and 'CHANGELOG.md does not document rubric.json version 999' in r.stdout

@test
def score_evidence_mix_and_unavailable_checks_present():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  run(SCORE,p,ok=(0,1))  # first call establishes the regression baseline as a side effect
  out=json.loads(run(SCORE,p,ok=(0,1)))
  assert 'unavailableChecks' in out and isinstance(out['unavailableChecks'],list)
  onpage_checks=out['categories']['onpage']['checks']
  assert all('evidenceMix' in c for c in onpage_checks)
  out2=json.loads(run(SCORE,p,ok=(0,1)))
  assert out['unavailableChecks']==out2['unavailableChecks'], 'evidenceMix/unavailableChecks must be deterministic across repeated runs'

@test
def worked_example_before_after_matches_golden_summary():
 EX=ROOT/'examples/worked-example-nextjs'
 def summarize(fixture_dir):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d); subprocess.run(['cp','-R',str(fixture_dir)+'/.',str(p)],check=True)
   run(INIT,'--project',p)
   out=json.loads(run(FULL,p,'--score',ok=(0,1)))
   high=out['summary']['highOrCritical']
   return {
    'highOrCriticalCount':len(high),
    'highOrCritical':[{'check':x['check'],'severity':x['severity'],'rule':x.get('rule')} for x in high],
    'score':out['score']['score'],'coveragePct':out['score']['coveragePct'],
    'categories':{k:({'status':v['status']} if v['status']=='unavailable' else {'status':v['status'],'earned':v['earned']}) for k,v in out['score']['categories'].items()},
   }
 before_actual=summarize(EX/'before'); before_golden=json.loads((EX/'expected-audit.json').read_text())
 after_actual=summarize(EX/'after'); after_golden=json.loads((EX/'expected-audit-after.json').read_text())
 for k in ('highOrCriticalCount','highOrCritical','score','coveragePct','categories'):
  assert before_actual[k]==before_golden[k], f'before/ {k} drifted from golden: {before_actual[k]} != {before_golden[k]}'
  assert after_actual[k]==after_golden[k], f'after/ {k} drifted from golden: {after_actual[k]} != {after_golden[k]}'
 assert after_actual['highOrCriticalCount']<before_actual['highOrCriticalCount']
 assert after_actual['score']>before_actual['score']

@test
def metadata_extract_per_framework_states():
 MF=ROOT/'tests/fixtures/metadata-frameworks'
 def state_of(fixture,route):
  out=json.loads(run(METAEXTRACT,MF/fixture,ok=(0,1)))
  return next(r['state'] for r in out['routes'] if r['route']==route)
 assert state_of('nextjs','/dynamic-page')=='dynamic'
 assert state_of('nextjs-layout-inherit','/child')=='static', 'metadata inherited from an ancestor layout.tsx must count as static'
 assert state_of('sveltekit','/about')=='static'
 assert state_of('astro','/about')=='static'
 assert state_of('remix','/about')=='static'
 out=json.loads(run(METAEXTRACT,MF/'component-prop-regression',ok=(0,1)))
 assert out['routes'][0]['state']=='absent', 'a component prop object like {title: "Card"} must not be mistaken for page metadata'
 assert any(f['rule']=='metadata-absent' for f in out['findings'])

@test
def hreflang_self_gates_and_catches_bad_code_and_missing_reciprocity():
 out=json.loads(run(HREFLANG,FIX,ok=(0,1)))
 assert out['applicable'] is False, 'a project with no locale/i18n signal must not run hreflang checks'
 HF=ROOT/'tests/fixtures/hreflang'
 out=json.loads(run(HREFLANG,HF,ok=(0,1)))
 assert out['applicable'] is True
 by_file={}
 for f in out['findings']: by_file.setdefault(f.get('file'),[]).append(f['issue'])
 assert any('does not look like a valid ISO' in i for i in by_file.get('de/about.html',[])), 'the malformed de-DE-XX code must be flagged'
 assert any('is not reciprocated back to' in i for i in by_file.get('de/about.html',[])), 'the missing return link from en back to de must be flagged'
 assert not any('is not reciprocated' in i or 'does not look like a valid ISO' in i for i in by_file.get('en/about.html',[])+by_file.get('fr/about.html',[])), 'the correct en/fr pair must not be flagged'

@test
def link_graph_finds_orphan_depth_and_generic_anchor():
 LG=ROOT/'tests/fixtures/linkgraph'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(LG)+'/.',str(p)],check=True)
  out=json.loads(run(LINKGRAPH,p,ok=(0,1)))
  assert any(f['rule']=='generic-anchor' and f['target']=='/hub' for f in out['findings'])
  assert any(f['rule']=='orphan' and f['target']=='/orphan' for f in out['findings'])
  graph=json.loads((p/'.claude/seo/link-graph.json').read_text())
  assert graph['depth']['/']==0
  assert graph['depth']['/deep/level2/level3/level4']==4, 'the 4-hop chain must resolve to depth 4'
  assert graph['depth']['/orphan'] is None

@test
def images_scan_flags_each_case_and_leaves_the_clean_image_alone():
 IMG=ROOT/'tests/fixtures/images'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(IMG)+'/.',str(p)],check=True)
  out=json.loads(run(IMAGES,p,ok=(0,1)))
  by_src={}
  for f in out['findings']: by_src.setdefault(f['src'],[]).append(f['rule'])
  assert 'missing-alt' in by_src['/hero.jpg'] and 'lazy-first-image' in by_src['/hero.jpg']
  assert by_src['/logo.png']==['empty-alt','missing-dimensions'] or set(by_src['/logo.png'])=={'empty-alt','missing-dimensions'}
  assert 'poor-alt' in by_src['/team.jpg']
  assert 'oversized' in by_src['/big.jpg'] and 'legacy-format' in by_src['/big.jpg']
  assert '/staff.jpg' not in by_src, 'a descriptive alt with width/height and normal size must not be flagged'

@test
def score_ia_and_links_use_the_link_graph():
 LG=ROOT/'tests/fixtures/linkgraph'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(LG)+'/.',str(p)],check=True); run(INIT,'--project',p)
  out=json.loads(run(SCORE,p,ok=(0,1)))
  assert out['categories']['ia']['status']=='evidenced'
  assert out['categories']['links']['status']=='evidenced'
  orphan_check=next(c for c in out['categories']['links']['checks'] if c['id']=='no-orphans')
  assert orphan_check['applicable'] and orphan_check['ratio']<1.0, 'the fixture has one orphan route, no-orphans must be < 1.0'

@test
def score_zero_images_is_unavailable_not_a_perfect_score():
 # M1: a site with no images at all must report the image-based Performance checks as
 # unavailable (no evidence), never as a flawless 5/5 -- `FIX` (tests/fixtures/site) has no
 # <img> tags at all.
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  out=json.loads(run(SCORE,p,ok=(0,1)))
  for check_id in ('images-have-dimensions','no-lazy-load-on-first-image','image-weight-ok'):
   check=next(c for c in out['categories']['performance']['checks'] if c['id']==check_id)
   assert check['applicable'] is False and check['earned'] is None, f'a site with zero images must not score {check_id} as evidenced: {check}'

@test
def validate_sources_passes_on_real_content():
 out=json.loads(run(VALSRC,ROOT,ok=(0,1)))
 assert out['result']=='pass', out['errors']
 assert out['cardsChecked']>=15 and out['sourcesChecked']>=15

@test
def validate_sources_catches_negative_fixtures():
 BAD=ROOT/'tests/fixtures/sources-bad'
 out=json.loads(run(VALSRC,BAD,ok=(0,1)))
 assert out['result']=='fail'
 joined=' '.join(out['errors'])
 assert 'missing required heading' in joined
 assert 'unknown source id' in joined
 assert 'percentage figure' in joined
 assert 'unhedged promise phrase' in joined

@test
def pattern_match_returns_expected_ids():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  out=json.loads(run(PATTERNMATCH,p,ok=(0,1)))
  assert 'P04' in out['matched'], 'fixture has a WebPage JSON-LD block, P04 (structured data) must match'
  assert 'P12' not in out['matched'], 'fixture has no local-business signal, P12 must not match'

@test
def score_is_deterministic():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  run(SCORE,p,ok=(0,1))  # first call establishes the regression baseline as a side effect; expected per --snapshot semantics
  r1=run(SCORE,p,ok=(0,1)); r2=run(SCORE,p,ok=(0,1))
  d1,d2=json.loads(r1),json.loads(r2); d1.pop('rubricHash',None); d2.pop('rubricHash',None)
  assert d1==d2, 'scoring the same stable project twice in a row must give identical output'

@test
def score_excludes_unevidenced_categories_from_denominator():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  out=json.loads(run(SCORE,p,ok=(0,1)))
  assert out['categories']['local']['status']=='unavailable', 'fixture has no local-business signal; local must be excluded, not scored zero'

@test
def score_drops_when_title_removed():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  before=json.loads(run(SCORE,p,ok=(0,1)))['categories']['onpage']['earned']
  page=p/'app/page.html'; page.write_text(page.read_text().replace('<title>Example</title>',''))
  after=json.loads(run(SCORE,p,ok=(0,1)))['categories']['onpage']
  assert after['checks'][0]['id']=='title-present' and after['checks'][0]['earned']==0.0
  assert after['earned']<before, 'removing the only title must lower the on-page score'

@test
def score_state_completeness_stub_detection():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  out=json.loads(run(SCORE,p,ok=(0,1)))
  strategy_check=next(c for c in out['categories']['content']['checks'] if c['id']=='strategy-keywords-not-stub')
  assert strategy_check['earned']==0.0, 'fresh init_state.py stubs must be flagged as not-started'
  kw=p/'.claude/seo/keywords.md'; kw.write_text(kw.read_text()+'\n| Pricing | pricing page | plans | commercial | mofu | /app | high | active | none | / |\n')
  st=p/'.claude/seo/strategy.md'; st.write_text(st.read_text()+'\n- Business and evidence source: verified brief\n')
  out2=json.loads(run(SCORE,p,ok=(0,1)))
  strategy_check2=next(c for c in out2['categories']['content']['checks'] if c['id']=='strategy-keywords-not-stub')
  assert strategy_check2['earned']==3.0, 'filled state files must no longer be flagged as stubs'

@test
def full_audit_score_flag_wires_in():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  out=json.loads(run(FULL,p,'--score',ok=(0,1)))
  assert 'score' in out and out['score']['label']=='internal prioritization, not a ranking prediction'
  assert any(f['check']=='state' for f in out['checks']['state']['result']['findings'])

@test
def policy_scenarios_present():
 # Policy scenarios remain explicit acceptance requirements where agent-run evaluation is unavailable.
 text=(ROOT/'SKILL.md').read_text(); required=['doorway/location pages','fabricate proof','Review first','A purely visual button-style change']
 assert all(x in text or x in (ROOT/'workflows/optimize.md').read_text() for x in required)

IMPACT=ROOT/'scripts/impact.py'; IMPACTFIX=ROOT/'tests/fixtures/impact'

def _impact_project():
 d=tempfile.mkdtemp(); p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p); return p

def _mark(p,id_,affected='/a',control=None,pre=28,settle=7,post=28,deployed='2026-01-01'):
 args=[IMPACT,'mark',p,'--id',id_,'--deployed-on',deployed,'--affected-urls',affected,'--metric','clicks','--direction','increase','--pre-days',str(pre),'--settle-days',str(settle),'--post-days',str(post),'--description','test']
 if control: args+=['--control-urls',control]
 return json.loads(run(*args,ok=(0,)))

@test
def impact_injected_effect_yields_consistent_with_hypothesis():
 p=_impact_project(); _mark(p,'t1',control='/b')
 run(IMPACT,'import',p,'t1',IMPACTFIX/'injected-effect/treated.json','--label','treated',ok=(0,))
 run(IMPACT,'import',p,'t1',IMPACTFIX/'injected-effect/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'t1','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='change-consistent-with-hypothesis', out

@test
def impact_seasonal_noise_yields_no_detectable_change():
 p=_impact_project(); _mark(p,'t2',control='/b')
 run(IMPACT,'import',p,'t2',IMPACTFIX/'null-seasonal/treated.json','--label','treated',ok=(0,))
 run(IMPACT,'import',p,'t2',IMPACTFIX/'null-seasonal/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'t2','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='no-detectable-change' and 'minimumDetectableChange' in out['placebo'], out

@test
def impact_overlapping_event_yields_confounded():
 p=_impact_project()
 events=json.loads((IMPACTFIX/'confounded/events.json').read_text())
 (p/'.claude/seo/external-events.json').write_text(json.dumps(events))
 _mark(p,'t3',control='/b')
 run(IMPACT,'import',p,'t3',IMPACTFIX/'confounded/treated.json','--label','treated',ok=(0,))
 run(IMPACT,'import',p,'t3',IMPACTFIX/'confounded/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'t3','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='confounded' and out['confounders'], out

@test
def impact_short_history_yields_insufficient_data():
 p=_impact_project(); _mark(p,'t4')
 run(IMPACT,'import',p,'t4',IMPACTFIX/'short-history/treated.json','--label','treated',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'t4','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='insufficient-data' and out['missing'], out

@test
def impact_sitewide_no_control_is_capped():
 p=_impact_project(); _mark(p,'t5')
 run(IMPACT,'import',p,'t5',IMPACTFIX/'sitewide-no-control/treated.json','--label','site',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'t5','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='observed-sitewide-not-separable', out

@test
def impact_evaluate_is_deterministic():
 p=_impact_project(); _mark(p,'t6',control='/b')
 run(IMPACT,'import',p,'t6',IMPACTFIX/'injected-effect/treated.json','--label','treated',ok=(0,))
 run(IMPACT,'import',p,'t6',IMPACTFIX/'injected-effect/control.json','--label','control',ok=(0,))
 r1=run(IMPACT,'evaluate',p,'t6','--allow-synthetic','--as-of','2026-02-09',ok=(0,))
 r2=run(IMPACT,'evaluate',p,'t6','--allow-synthetic','--as-of','2026-02-09',ok=(0,))
 assert r1==r2, 'evaluate must be byte-identical across repeated runs on unchanged data'

@test
def impact_refuses_synthetic_data_without_flag_and_window_change_without_amend():
 p=_impact_project(); _mark(p,'t7',control='/b')
 run(IMPACT,'import',p,'t7',IMPACTFIX/'injected-effect/treated.json','--label','treated',ok=(0,))
 r=subprocess.run([sys.executable,str(IMPACT),'evaluate',str(p),'t7','--as-of','2026-02-09'],capture_output=True,text=True)
 assert r.returncode==2 and 'synthetic' in (r.stdout+r.stderr).lower(), 'must refuse to evaluate synthetic data without --allow-synthetic'
 r=subprocess.run([sys.executable,str(IMPACT),'mark',str(p),'--id','t7','--deployed-on','2026-01-01','--affected-urls','/a','--pre-days','14'],capture_output=True,text=True)
 assert r.returncode==2 and 'amend' in (r.stdout+r.stderr).lower(), 'must refuse to silently change windows on an existing change record'
 r=json.loads(run(IMPACT,'mark',p,'--id','t7','--pre-days','14','--amend','testing amendment path',ok=(0,)))
 assert r['record']['amendments'] if 'record' in r else r['amendments'], 'window change with --amend must be recorded in amendments[]'

# --- Regression tests for a Fable-5.1 adversarial QA pass (C1-C4, H1-H3 in scripts/impact.py) ---

def _build_daily(label,start,end,base,treated_blip_from=None,treated_blip_mult=1.0):
 rows=[]; d=start
 while d<=end:
  v=base*treated_blip_mult if (treated_blip_from and d>=treated_blip_from) else base
  rows.append({'date':str(d),'clicks':v}); d+=timedelta(days=1)
 return {'schemaVersion':1,'source':'gsc','label':label,'provenance':{'method':'synthetic-fixture','fileSha256':None,'importedOn':'2026-01-01'},'dateRange':{'start':str(start),'end':str(end)},'grain':'daily','rows':rows,'synthetic':True}

@test
def impact_gap_inside_post_window_yields_insufficient_data():
 # C1: data SPANS the windows (first/last dates look fine) but has a large gap inside the post
 # window -- this must never be reported as a real directional movement.
 p=_impact_project(); _mark(p,'c1',control='/b')
 treated=json.loads((IMPACTFIX/'injected-effect/treated.json').read_text())
 deploy=datetime.strptime('2026-01-01','%Y-%m-%d').date()
 rows=[r for r in treated['rows'] if datetime.strptime(r['date'],'%Y-%m-%d').date()<deploy or r['date']=='2026-02-05']
 treated['rows']=rows
 tf=p/'c1-treated-gappy.json'; tf.write_text(json.dumps(treated))
 run(IMPACT,'import',p,'c1',tf,'--label','treated',ok=(0,))
 run(IMPACT,'import',p,'c1',IMPACTFIX/'injected-effect/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'c1','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='insufficient-data' and any('gap' in m.lower() for m in out['missing']), out

@test
def impact_overlapping_reimport_is_deduped_not_double_counted():
 # C2: a refreshed export that overlaps an earlier one, with no real underlying change, must
 # not silently double-count the overlapping dates into a fabricated effect.
 p=_impact_project(); _mark(p,'c2',control='/b')
 base=json.loads((IMPACTFIX/'null-seasonal/treated.json').read_text())
 run(IMPACT,'import',p,'c2',IMPACTFIX/'null-seasonal/treated.json','--label','treated',ok=(0,))
 post_start=datetime.strptime('2026-01-08','%Y-%m-%d').date()
 refresh={**base,'rows':[r for r in base['rows'] if datetime.strptime(r['date'],'%Y-%m-%d').date()>=post_start],'provenance':{**base['provenance'],'importedOn':'2026-02-08'}}
 rf=p/'c2-treated-refresh.json'; rf.write_text(json.dumps(refresh))
 run(IMPACT,'import',p,'c2',rf,'--label','treated',ok=(0,))
 run(IMPACT,'import',p,'c2',IMPACTFIX/'null-seasonal/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'c2','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='no-detectable-change', f'an overlapping same-data refresh import must not fabricate a directional verdict: {out}'
 assert abs(out['observed']['treatedRatio']-1)<0.3, f'deduped ratio should stay near the true no-change ratio, not double: {out}'

@test
def impact_flat_history_tiny_blip_is_bounded_by_mde_floor():
 # C3 (MDE floor): perfectly flat pre-change history collapses empirical variance to ~0; a
 # trivial 0.5% blip must not be reported as an unusual, directional result.
 p=_impact_project(); _mark(p,'c3a',control='/b')
 start=datetime.strptime('2025-05-26','%Y-%m-%d').date(); end=datetime.strptime('2026-02-05','%Y-%m-%d').date()
 blip_from=datetime.strptime('2026-01-08','%Y-%m-%d').date()
 treated=_build_daily('treated',start,end,100.0,blip_from,1.005); control=_build_daily('control',start,end,100.0)
 tf=p/'c3a-treated.json'; tf.write_text(json.dumps(treated)); cf=p/'c3a-control.json'; cf.write_text(json.dumps(control))
 run(IMPACT,'import',p,'c3a',tf,'--label','treated',ok=(0,)); run(IMPACT,'import',p,'c3a',cf,'--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'c3a','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='no-detectable-change', f'a 0.5% blip on perfectly flat history must be bounded by the MDE floor, not read as directional: {out}'
 assert out['placebo']['minimumDetectableChange']>=0.02, out

@test
def impact_insufficient_placebo_history_caps_verdict():
 # C3 (minimum placebo windows): with only ~1 real placebo window available, even a real,
 # sizeable 20% blip must be capped at no-detectable-change rather than trusted as directional
 # via an assumed distribution.
 p=_impact_project(); _mark(p,'c3b',control='/b')
 start=datetime.strptime('2025-10-27','%Y-%m-%d').date(); end=datetime.strptime('2026-02-09','%Y-%m-%d').date()
 blip_from=datetime.strptime('2026-01-08','%Y-%m-%d').date()
 treated=_build_daily('treated',start,end,100.0,blip_from,1.20); control=_build_daily('control',start,end,100.0)
 tf=p/'c3b-treated.json'; tf.write_text(json.dumps(treated)); cf=p/'c3b-control.json'; cf.write_text(json.dumps(control))
 run(IMPACT,'import',p,'c3b',tf,'--label','treated',ok=(0,)); run(IMPACT,'import',p,'c3b',cf,'--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'c3b','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['placebo']['windowCount']<8, out
 assert out['verdict']=='no-detectable-change', f'too few placebo windows must cap the verdict rather than trust an assumed distribution: {out}'

@test
def impact_confounder_touching_control_group_is_detected():
 # C4: another registered change that hits the CONTROL group (not the treated group) during
 # the window must still be flagged as a confounder.
 p=_impact_project(); _mark(p,'c4',affected='/a',control='/b')
 run(IMPACT,'mark',p,'--id','c4-other','--deployed-on','2026-01-15','--affected-urls','/b','--pre-days','7','--settle-days','1','--post-days','7','--description','damages control',ok=(0,))
 run(IMPACT,'import',p,'c4',IMPACTFIX/'injected-effect/treated.json','--label','treated',ok=(0,))
 run(IMPACT,'import',p,'c4',IMPACTFIX/'injected-effect/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'c4','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='confounded', f'a change overlapping the control group must be flagged: {out}'
 assert any(c.get('id')=='c4-other' for c in out['confounders']), out

@test
def impact_pre_deploy_event_is_detected_as_confounder():
 # H1: the confounder window must start at (deployedOn - preDays), not deployedOn -- an event
 # that hit the pre-change baseline is just as much a confounder as a post-deploy one.
 p=_impact_project(); _mark(p,'h1',control='/b')
 events={'events':[{'date':'2025-12-10','description':'core update, pre-deploy baseline dip','type':'algorithm-update','source':'manual'}]}
 (p/'.claude/seo/external-events.json').write_text(json.dumps(events))
 run(IMPACT,'import',p,'h1',IMPACTFIX/'injected-effect/treated.json','--label','treated',ok=(0,))
 run(IMPACT,'import',p,'h1',IMPACTFIX/'injected-effect/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'h1','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='confounded', f'an event inside the pre-change window must still be flagged: {out}'

@test
def impact_corrupt_events_file_fails_closed():
 # H2: a corrupt external-events.json must error out, never silently behave as "no events" and
 # thereby silently disable confounder detection.
 p=_impact_project(); _mark(p,'h2',control='/b')
 (p/'.claude/seo/external-events.json').write_text('{"events": [')
 run(IMPACT,'import',p,'h2',IMPACTFIX/'injected-effect/treated.json','--label','treated',ok=(0,))
 run(IMPACT,'import',p,'h2',IMPACTFIX/'injected-effect/control.json','--label','control',ok=(0,))
 r=subprocess.run([sys.executable,str(IMPACT),'evaluate',str(p),'h2','--allow-synthetic','--as-of','2026-02-09'],capture_output=True,text=True)
 assert r.returncode!=0, f'a corrupt external-events.json must fail closed, not silently proceed: {r.stdout}{r.stderr}'

@test
def impact_empty_control_window_yields_insufficient_data():
 # H3: a control group with no data in the evaluation window must never fall through to a
 # confident "no-detectable-change" -- it must be reported as insufficient-data instead.
 p=_impact_project(); _mark(p,'h3',control='/b')
 run(IMPACT,'import',p,'h3',IMPACTFIX/'injected-effect/treated.json','--label','treated',ok=(0,))
 empty_control={'schemaVersion':1,'source':'gsc','label':'control','provenance':{'method':'synthetic-fixture','fileSha256':None,'importedOn':'2026-01-01'},'dateRange':{'start':'2025-05-26','end':'2026-02-05'},'grain':'daily','rows':[],'synthetic':True}
 cf=p/'h3-control-empty.json'; cf.write_text(json.dumps(empty_control))
 run(IMPACT,'import',p,'h3',cf,'--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'h3','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='insufficient-data', f'an empty control window must never be reported as a confident no-detectable-change: {out}'

EX=ROOT/'examples/worked-example-nextjs'
import shutil
def _ci_pair():
 # full_audit.py --score (which ci_check.py runs on both sides) writes .claude/seo/baseline.json
 # into whatever directory it's pointed at -- copy the committed fixtures to a scratch dir first
 # so these tests never mutate examples/worked-example-nextjs in place (that corrupted the golden
 # `worked_example_before_after_matches_golden_summary` fixture during development of this test).
 td=Path(tempfile.mkdtemp()); before=td/'before'; after=td/'after'
 shutil.copytree(EX/'before',before); shutil.copytree(EX/'after',after)
 return before,after

@test
def ci_check_worked_example_before_to_after_has_no_new_findings_and_passes():
 before,after=_ci_pair()
 out=json.loads(run(CI,after,'--base-dir',before,ok=(0,)))
 assert out['diff']['newFindings']==[], f'fixing the issues must not introduce new findings: {out["diff"]["newFindings"]}'
 assert out['triggers']==[], f'an improving diff must not trigger any failOn rule: {out}'
 assert out['diff']['scoreDelta']>0, f'the after fixture should score higher than before: {out["diff"]["scoreDelta"]}'

@test
def ci_check_worked_example_after_to_before_is_a_regression_and_fails():
 before,after=_ci_pair()
 p=subprocess.run([sys.executable,str(CI),str(before),'--base-dir',str(after)],capture_output=True,text=True)
 assert p.returncode==1, f'reintroducing the before-fixture issues must fail the CI check: {p.stdout}{p.stderr}'
 dec=json.JSONDecoder(); out,_=dec.raw_decode(p.stdout)
 assert 'new-high' in out['triggers'], f'the reintroduced HIGH jsonld finding must trigger new-high: {out}'
 assert len(out['diff']['newFindings'])>0

@test
def ci_check_expired_ignore_still_fails_the_build():
 before,after=_ci_pair()
 # find one real new-finding fingerprint by running the regression comparison once, unfiltered
 raw=run(CI,before,'--base-dir',after,ok=(0,1))
 dec=json.JSONDecoder(); first,_=dec.raw_decode(raw)
 assert first['diff']['newFindings'], 'need at least one real new finding to build this fixture'
 f=first['diff']['newFindings'][0]
 fp='|'.join([f['tool'],str(f.get('severity','')),(f.get('issue') or '').strip(),(f.get('file') or '').strip()])
 cfg={'failOn':['new-critical','new-high'],'ignore':[{'fingerprint':fp,'reason':'test','expires':'2000-01-01'}]}
 # ci_check.py reads .claude/seo/ci.json relative to the PROJECT dir (the head), which here is `before`
 ci_json=before/'.claude/seo/ci.json'; ci_json.parent.mkdir(parents=True,exist_ok=True)
 ci_json.write_text(json.dumps(cfg))
 out2=subprocess.run([sys.executable,str(CI),str(before),'--base-dir',str(after)],capture_output=True,text=True)
 assert out2.returncode==1, 'an EXPIRED ignore must not suppress the finding -- the build must still fail'
 parsed,_=dec.raw_decode(out2.stdout)
 assert parsed['expiredIgnores'], f'the expired ignore must be reported, not silently dropped: {parsed}'

@test
def ci_check_sarif_has_required_keys():
 before,after=_ci_pair()
 out_path=before/'r.sarif'
 run(CI,before,'--base-dir',after,'--sarif',out_path,ok=(0,1))
 sarif=json.loads(out_path.read_text())
 assert sarif['version']=='2.1.0'
 run_=sarif['runs'][0]; assert run_['tool']['driver']['name']
 assert isinstance(run_['results'],list) and run_['results']
 assert run_['results'][0]['locations'][0]['physicalLocation']['artifactLocation']['uri']

@test
def scan_redirects_detects_chain_loop_and_unresolved_target():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)
  (p/'next.config.js').write_text("module.exports={async redirects(){return ["
   "{source:'/old',destination:'/mid',permanent:true},"
   "{source:'/mid',destination:'/new',permanent:true},"
   "{source:'/loopA',destination:'/loopB',permanent:true},"
   "{source:'/loopB',destination:'/loopA',permanent:true},"
   "{source:'/dead',destination:'/nowhere',permanent:true}"
   "]}}")
  (p/'app/new').mkdir(parents=True); (p/'app/new/page.html').write_text('<html><title>x</title></html>')
  (p/'app/page.html').write_text('<html><title>home</title></html>')
  out=json.loads(run(REDIRECTS,p,ok=(0,1)))
  issues=[f['issue'] for f in out['findings']]
  assert any('chain of 2 hop' in i for i in issues), issues
  assert any(f['severity']=='CRITICAL' and 'loop' in f['issue'].lower() for f in out['findings']), issues
  assert any('does not resolve to a known route' in i for i in issues), issues

@test
def scan_canonicals_flags_noindex_canonical_and_near_duplicates():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); (p/'app/a').mkdir(parents=True); (p/'app/b').mkdir(parents=True)
  body='<html><head><title>Widget City Downtown</title><link rel="canonical" href="https://x.com/a"/>'\
       '<meta name="robots" content="noindex"></head><body>'+' '.join(f'word{i}' for i in range(60))+'</body></html>'
  (p/'app/a/page.html').write_text(body)
  body_b=body.replace('href="https://x.com/a"','href="https://x.com/b"').replace('Downtown','Uptown')
  (p/'app/b/page.html').write_text(body_b)
  out=json.loads(run(CANONICALS,p,ok=(0,1)))
  rules={f['rule'] for f in out['findings'] if 'rule' in f}
  assert 'canonical-on-noindex' in rules, out['findings']
  assert 'near-duplicate-heuristic' in rules, out['findings']

@test
def scan_freshness_flags_declared_date_newer_than_last_real_change():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)
  subprocess.run(['git','init','-q'],cwd=p,check=True)
  subprocess.run(['git','config','user.email','t@example.com'],cwd=p,check=True)
  subprocess.run(['git','config','user.name','t'],cwd=p,check=True)
  (p/'app/a').mkdir(parents=True)
  f=p/'app/a/page.html'
  f.write_text('<html><head><title>A</title></head><body>real content here, first version</body></html>')
  subprocess.run(['git','add','-A'],cwd=p,check=True)
  env={'GIT_AUTHOR_DATE':'2024-01-01T00:00:00','GIT_COMMITTER_DATE':'2024-01-01T00:00:00'}
  import os; full_env=dict(os.environ); full_env.update(env)
  subprocess.run(['git','commit','-q','-m','initial'],cwd=p,check=True,env=full_env)
  # a second, trivial (whitespace-only) commit must NOT count as the "last significant change"
  f.write_text(f.read_text()+'  ')
  subprocess.run(['git','add','-A'],cwd=p,check=True)
  env2=dict(full_env); env2['GIT_AUTHOR_DATE']='2024-06-01T00:00:00'; env2['GIT_COMMITTER_DATE']='2024-06-01T00:00:00'
  subprocess.run(['git','commit','-q','-m','whitespace only'],cwd=p,check=True,env=env2)
  # now claim a much later "updated" date than any real content change
  f.write_text(f.read_text()+'<meta itemprop="dateModified" content="2026-01-01">'.replace('  <meta','<meta'))
  # rewrite with the dateModified actually embedded in a parseable spot
  f.write_text('<html><head><title>A</title><script type="application/ld+json">{"dateModified":"2026-01-01"}</script></head><body>real content here, first version</body></html>')
  out=json.loads(run(FRESHNESS,p,ok=(0,1)))
  assert any(f_['rule']=='freshness-date-mismatch' for f_ in out['findings']), out

@test
def render_diff_flags_canonical_title_and_render_only_links():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); (p/'response').mkdir(); (p/'rendered').mkdir()
  (p/'response/a.html').write_text('<html><head><title>A</title><link rel="canonical" href="https://x.com/a"/></head><body>hi</body></html>')
  (p/'rendered/a.html').write_text('<html><head><title>A - r</title><link rel="canonical" href="https://x.com/a-r"/></head><body>hi <a href="/extra">e</a></body></html>')
  out=json.loads(run(RENDERDIFF,'--response',p/'response','--rendered',p/'rendered',ok=(0,1)))
  issues=' '.join(f['issue'] for f in out['findings'])
  assert 'Canonical differs' in issues and 'Title differs' in issues and 'exist only after rendering' in issues, out

@test
def render_diff_without_rendered_only_flags_noindex_and_says_so():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); (p/'response').mkdir()
  (p/'response/a.html').write_text('<html><head><meta name="robots" content="noindex"></head><body>hi</body></html>')
  out=json.loads(run(RENDERDIFF,'--response',p/'response',ok=(0,)))
  assert any(f['severity']=='INFO' and 'noindex' in f['issue'].lower() for f in out['findings']), out
  assert any('No --rendered input given' in n for n in out['notes']), out

@test
def scan_logs_spoofed_googlebot_is_unverified_real_one_is_verified():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); log=p/'access.log'
  log.write_text('\n'.join([
   '66.249.66.1 - - [01/Jan/2026:00:00:00 +0000] "GET /a HTTP/1.1" 200 512 "-" "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"',
   '1.2.3.4 - - [01/Jan/2026:00:00:01 +0000] "GET /b HTTP/1.1" 200 512 "-" "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"',
   '203.0.113.5 - - [01/Jan/2026:00:00:02 +0000] "GET /c?utm=1 HTTP/1.1" 404 0 "-" "GPTBot/1.0"',
  ]))
  ranges=p/'ranges.json'; ranges.write_text(json.dumps({'prefixes':[{'ipv4Prefix':'66.249.64.0/19'}]}))
  out=json.loads(run(SCANLOGS,log,'--ranges',ranges,ok=(0,1)))
  gb=out['summary']['byBotStatus']['Googlebot']
  assert gb.get('200:verified')==1 and gb.get('200:unverified')==1, gb
  assert out['summary']['topParamUrls']==[['/c?utm=1',1]], out['summary']['topParamUrls']
  assert out['summary']['top404s']==[['/c',1]], out['summary']['top404s']

@test
def scan_logs_never_persists_a_raw_ip():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); log=p/'access.log'
  log.write_text('203.0.113.77 - - [01/Jan/2026:00:00:00 +0000] "GET /a HTTP/1.1" 200 512 "-" "GPTBot/1.0"')
  out=run(SCANLOGS,log,ok=(0,1))
  assert '203.0.113.77' not in out, 'a raw, untruncated IP must never appear in scan_logs.py output'

def main():
 failures=[]
 for fn in TESTS:
  try:
   fn(); print(f'PASS: {fn.__name__}')
  except Exception as e:
   failures.append((fn.__name__,e)); print(f'FAIL: {fn.__name__}: {e}')
 print(f'\n{len(TESTS)-len(failures)}/{len(TESTS)} tests passed.')
 return 1 if failures else 0
if __name__=='__main__': sys.exit(main())
