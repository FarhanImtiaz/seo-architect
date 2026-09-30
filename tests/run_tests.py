#!/usr/bin/env python3
import json, re, subprocess, sys, tempfile
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
ROOT=Path(__file__).resolve().parents[1]; TOOLS=ROOT/'scripts/seo_tools.py'; INIT=ROOT/'scripts/init_state.py'; FIX=ROOT/'tests/fixtures/site'; HOOK=ROOT/'scripts/guardian_hook.py'; LEDGER=ROOT/'scripts/evidence_ledger.py'; CONTRACT=ROOT/'scripts/validate_page_contract.py'; FRAMEWORK=ROOT/'scripts/framework_inspect.py'; ADAPTERS=ROOT/'scripts/framework_adapters.py'; AEO=ROOT/'scripts/validate_aeo.py'; FULL=ROOT/'scripts/full_audit.py'; CLAUDE=ROOT/'scripts/validate_claude_skill.py'; SCORE=ROOT/'scripts/score.py'; VALSRC=ROOT/'scripts/validate_sources.py'; PATTERNMATCH=ROOT/'scripts/pattern_match.py'; LINKGRAPH=ROOT/'scripts/scan_link_graph.py'; IMAGES=ROOT/'scripts/scan_images.py'; METAEXTRACT=ROOT/'scripts/metadata_extract.py'; HREFLANG=ROOT/'scripts/validate_hreflang.py'; LIVEDATA=ROOT/'scripts/live_data.py'; CI=ROOT/'scripts/ci_check.py'; REDIRECTS=ROOT/'scripts/scan_redirects.py'; CANONICALS=ROOT/'scripts/scan_canonicals.py'; FRESHNESS=ROOT/'scripts/scan_freshness.py'; RENDERDIFF=ROOT/'scripts/render_diff.py'; SCANLOGS=ROOT/'scripts/scan_logs.py'; PLATFORMS=ROOT/'scripts/platform_detect.py'; PLATFORMFIX=ROOT/'tests/fixtures/platforms'; AIACCESS=ROOT/'scripts/validate_ai_access.py'; COMPETITOR=ROOT/'scripts/competitor_diff.py'; BUILDDIST=ROOT/'scripts/build_dist.py'
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
 return {'schemaVersion':1,'source':'gsc','label':label,'provenance':{'method':'synthetic-fixture','fileSha256':None,'importedOn':'2026-02-09'},'dateRange':{'start':str(start),'end':str(end)},'grain':'daily','rows':rows,'synthetic':True}

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
 run(IMPACT,'import',p,'c2',rf,'--label','treated','--supersedes','treated.json',ok=(0,))
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
def impact_insufficient_placebo_history_yields_insufficient_data():
 # Round-2 QA, HIGH 3: with only ~1 real placebo window available, even a real, sizeable 20%
 # blip must NOT be reported as a confident 'no-detectable-change' (that asserts a null result
 # that was never actually measured) -- it must be insufficient-data instead.
 p=_impact_project(); _mark(p,'c3b',control='/b')
 start=datetime.strptime('2025-10-27','%Y-%m-%d').date(); end=datetime.strptime('2026-02-09','%Y-%m-%d').date()
 blip_from=datetime.strptime('2026-01-08','%Y-%m-%d').date()
 treated=_build_daily('treated',start,end,100.0,blip_from,1.20); control=_build_daily('control',start,end,100.0)
 tf=p/'c3b-treated.json'; tf.write_text(json.dumps(treated)); cf=p/'c3b-control.json'; cf.write_text(json.dumps(control))
 run(IMPACT,'import',p,'c3b',tf,'--label','treated',ok=(0,)); run(IMPACT,'import',p,'c3b',cf,'--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'c3b','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['placebo']['windowCount']<8, out
 assert out['verdict']=='insufficient-data', f'too few placebo windows must never assert a null result it did not measure: {out}'

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
 empty_control={'schemaVersion':1,'source':'gsc','label':'control','provenance':{'method':'synthetic-fixture','fileSha256':None,'importedOn':'2026-02-09'},'dateRange':{'start':'2025-05-26','end':'2026-02-05'},'grain':'daily','rows':[],'synthetic':True}
 cf=p/'h3-control-empty.json'; cf.write_text(json.dumps(empty_control))
 run(IMPACT,'import',p,'h3',cf,'--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'h3','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='insufficient-data', f'an empty control window must never be reported as a confident no-detectable-change: {out}'

# --- Regression tests for a SECOND Fable-5.1 adversarial QA pass, re-attacking the round-1 fixes ---

@test
def impact_direction_is_read_from_the_placebo_band_not_a_naive_effect_over_one():
 # CRITICAL 1: when the site has a pre-existing upward trend (placebo band median != 1.0),
 # deciding direction from a bare effect>1 comparison can invert the reported direction -- a
 # real deceleration (effect below the band, band centered above 1.0) must never be reported as
 # an "increase" just because effect happens to still be (barely) >1 in absolute terms.
 p=_impact_project(); _mark(p,'dir1',control='/b')  # _mark defaults to --direction increase
 start=datetime.strptime('2025-05-26','%Y-%m-%d').date(); end=datetime.strptime('2026-02-05','%Y-%m-%d').date()
 deploy=datetime.strptime('2026-01-01','%Y-%m-%d').date()
 # Treated pages ramp up steadily pre-deploy (a consistent per-window growth trend the placebo
 # distribution captures); post-deploy the ramp essentially stalls (a slight step DOWN from the
 # trend's trajectory), while control stays flat throughout. The resulting effect is still
 # numerically >1 (traffic is still higher than the pre-window average), but it sits BELOW the
 # placebo band established by the site's own historical growth rate -- a deceleration, not an
 # acceleration.
 t_rows=[]; c_rows=[]; d=start; pre_slope=0.08; post_extra=-0.8; base=90.0
 while d<=end:
  c_rows.append({'date':str(d),'clicks':100.0})
  if d<deploy: v=base+pre_slope*(d-start).days
  else: v=base+pre_slope*(deploy-start).days+post_extra
  t_rows.append({'date':str(d),'clicks':v})
  d+=timedelta(days=1)
 treated={'schemaVersion':1,'source':'gsc','label':'treated','provenance':{'method':'synthetic-fixture','fileSha256':None,'importedOn':'2026-02-09'},'dateRange':{'start':str(start),'end':str(end)},'grain':'daily','rows':t_rows,'synthetic':True}
 control={'schemaVersion':1,'source':'gsc','label':'control','provenance':{'method':'synthetic-fixture','fileSha256':None,'importedOn':'2026-02-09'},'dateRange':{'start':str(start),'end':str(end)},'grain':'daily','rows':c_rows,'synthetic':True}
 tf=p/'dir1-treated.json'; tf.write_text(json.dumps(treated)); cf=p/'dir1-control.json'; cf.write_text(json.dumps(control))
 run(IMPACT,'import',p,'dir1',tf,'--label','treated',ok=(0,)); run(IMPACT,'import',p,'dir1',cf,'--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'dir1','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['observed']['effect']>1.0, f'sanity check: effect should still be >1 in absolute terms: {out}'
 assert out['observed']['effect']<out['placebo']['band'][0], f'sanity check: effect should sit below the placebo band: {out}'
 assert out['verdict']=='change-opposite-to-hypothesis', f'a deceleration below the placebo band must never read as "increase" just because effect>1: {out}'

@test
def impact_unrelated_series_under_one_label_is_refused_not_fabricated():
 # CRITICAL 2: two DIFFERENT, unrelated exports (e.g. different pages) attached under the same
 # label with overlapping-but-inconsistent date coverage must be refused at import time, not
 # silently merged into a fabricated effect.
 p=_impact_project(); _mark(p,'c2b',control='/b')
 run(IMPACT,'import',p,'c2b',IMPACTFIX/'null-seasonal/treated.json','--label','treated',ok=(0,))
 base=json.loads((IMPACTFIX/'null-seasonal/treated.json').read_text())
 post_start=datetime.strptime('2026-01-08','%Y-%m-%d').date()
 # A different, unrelated series (3x the traffic) covering only the recent period, imported
 # later, with NEITHER --supersedes NOR --combine declared.
 other={**base,'rows':[{**r,'clicks':r['clicks']*3} for r in base['rows'] if datetime.strptime(r['date'],'%Y-%m-%d').date()>=post_start],'provenance':{**base['provenance'],'importedOn':'2026-02-08'}}
 of=p/'c2b-other.json'; of.write_text(json.dumps(other))
 r=subprocess.run([sys.executable,str(IMPACT),'import',str(p),'c2b',str(of),'--label','treated'],capture_output=True,text=True)
 assert r.returncode!=0, f'an overlapping, undeclared-relationship import must be refused, not silently merged: {r.stdout}{r.stderr}'
 assert 'supersedes' in (r.stdout+r.stderr).lower() and 'combine' in (r.stdout+r.stderr).lower()

@test
def impact_combine_sums_genuinely_additive_series():
 # The --combine escape hatch: two DIFFERENT pages' exports covering the SAME dates, both
 # declared additive, must sum (not fabricate a directional effect from a label switch).
 p=_impact_project(); _mark(p,'comb1',control='/b')
 start=datetime.strptime('2025-05-26','%Y-%m-%d').date(); end=datetime.strptime('2026-02-05','%Y-%m-%d').date()
 page_a=_build_daily('treated',start,end,60.0); page_b=_build_daily('treated',start,end,40.0)
 af=p/'comb-a.json'; af.write_text(json.dumps(page_a)); bf=p/'comb-b.json'; bf.write_text(json.dumps(page_b))
 run(IMPACT,'import',p,'comb1',af,'--label','treated','--combine',ok=(0,))
 run(IMPACT,'import',p,'comb1',bf,'--label','treated','--combine',ok=(0,))
 control=_build_daily('control',start,end,100.0); cf=p/'comb-control.json'; cf.write_text(json.dumps(control))
 run(IMPACT,'import',p,'comb1',cf,'--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'comb1','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='no-detectable-change', f'two flat, genuinely additive series (60+40=100, matching control) must not fabricate a directional effect: {out}'
 assert abs(out['observed']['treatedRatio']-1)<0.05, out

@test
def impact_confounder_detection_normalizes_url_variants():
 # HIGH 4: a registered confounding change on '/b/', 'https://example.com/b', '/B', or
 # '/b?utm=1' must still be recognized as touching a control URL of '/b' -- exact-string
 # matching silently missed all of these.
 p=_impact_project(); _mark(p,'url1',affected='/a',control='/b')
 run(IMPACT,'mark',p,'--id','url1-other','--deployed-on','2026-01-15','--affected-urls','https://example.com/b/?utm=1','--pre-days','7','--settle-days','1','--post-days','7','--description','damages control via a differently-formatted URL',ok=(0,))
 run(IMPACT,'import',p,'url1',IMPACTFIX/'injected-effect/treated.json','--label','treated',ok=(0,))
 run(IMPACT,'import',p,'url1',IMPACTFIX/'injected-effect/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'url1','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='confounded', f'a URL-variant confounder must still be detected after normalization: {out}'

@test
def impact_mark_refuses_overlapping_affected_and_control_urls():
 # MEDIUM 9: the same page cannot honestly be both the thing being measured and its own control.
 p=_impact_project()
 r=subprocess.run([sys.executable,str(IMPACT),'mark',str(p),'--id','ov1','--deployed-on','2026-01-01','--affected-urls','/a,/b','--control-urls','/b,/c'],capture_output=True,text=True)
 assert r.returncode!=0, f'overlapping affected/control URLs must be refused at mark time: {r.stdout}{r.stderr}'

@test
def impact_stale_export_cannot_be_laundered_via_a_future_as_of():
 # HIGH 5: data actually imported on 2026-02-05 (the export's own importedOn) must not be
 # treated as settled just because the caller passes a far-future --as-of -- the provisional-day
 # cutoff must be bounded by when the data was really pulled, not a caller-suppliable date.
 p=_impact_project(); _mark(p,'stale1',control='/b')
 treated=json.loads((IMPACTFIX/'injected-effect/treated.json').read_text())
 treated['provenance']=dict(treated['provenance'],importedOn='2026-02-05')
 control=json.loads((IMPACTFIX/'injected-effect/control.json').read_text())
 control['provenance']=dict(control['provenance'],importedOn='2026-02-05')
 tf=p/'stale-treated.json'; tf.write_text(json.dumps(treated)); cf=p/'stale-control.json'; cf.write_text(json.dumps(control))
 run(IMPACT,'import',p,'stale1',tf,'--label','treated',ok=(0,)); run(IMPACT,'import',p,'stale1',cf,'--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'stale1','--allow-synthetic','--as-of','2026-03-01',ok=(0,)))
 assert out['verdict']=='insufficient-data', f'a far-future --as-of must not launder a stale export into a settled result: {out}'

@test
def impact_date_key_normalization_prevents_double_counting():
 # MEDIUM 6: '2026-1-8' and '2026-01-08' must collapse to the same day, not double-count as two.
 p=_impact_project(); _mark(p,'dk1',control='/b')
 base=json.loads((IMPACTFIX/'null-seasonal/treated.json').read_text())
 unpadded={**base,'rows':[{**r,'date':re.sub(r'-0(\d)(?=-|$)',r'-\1',r['date'])} for r in base['rows']]}
 tf=p/'dk1-treated.json'; tf.write_text(json.dumps(unpadded))
 run(IMPACT,'import',p,'dk1',tf,'--label','treated',ok=(0,))
 run(IMPACT,'import',p,'dk1',IMPACTFIX/'null-seasonal/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'dk1','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='no-detectable-change', f'unpadded-vs-padded date strings for the same day must not double-count into a fabricated effect: {out}'

@test
def impact_ga4_yyyymmdd_dates_do_not_crash_evaluate():
 # MEDIUM 7: a raw GA4-shaped 'YYYYMMDD' date must be parsed, not raise an uncaught ValueError.
 p=_impact_project(); _mark(p,'ga4d1',control='/b')
 base=json.loads((IMPACTFIX/'null-seasonal/treated.json').read_text())
 ga4shaped={**base,'source':'ga4','rows':[{**r,'date':r['date'].replace('-','')} for r in base['rows']]}
 tf=p/'ga4d1-treated.json'; tf.write_text(json.dumps(ga4shaped))
 run(IMPACT,'import',p,'ga4d1',tf,'--label','treated',ok=(0,))
 run(IMPACT,'import',p,'ga4d1',IMPACTFIX/'null-seasonal/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'ga4d1','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']=='no-detectable-change', f'GA4 YYYYMMDD dates must be usable, not crash or dead-end: {out}'

@test
def impact_minimum_volume_gate_checks_clicks_not_the_chosen_metric():
 # MEDIUM 8: evaluating with --metric ctr must still gate on real click volume, not on the
 # tiny ctr values themselves (which can never reach a clicks-sized threshold).
 p=_impact_project()
 run(IMPACT,'mark',p,'--id','vol1','--deployed-on','2026-01-01','--affected-urls','/a','--control-urls','/b','--metric','ctr','--direction','increase','--pre-days','28','--settle-days','7','--post-days','28','--description','ctr test',ok=(0,))
 run(IMPACT,'import',p,'vol1',IMPACTFIX/'injected-effect/treated.json','--label','treated',ok=(0,))
 run(IMPACT,'import',p,'vol1',IMPACTFIX/'injected-effect/control.json','--label','control',ok=(0,))
 out=json.loads(run(IMPACT,'evaluate',p,'vol1','--allow-synthetic','--as-of','2026-02-09',ok=(0,)))
 assert out['verdict']!='insufficient-data' or not any('below the minimum' in m for m in out.get('missing',[])), f'a ctr evaluation must be gated on click volume, not summed ctr values: {out}'

@test
def live_data_import_gsc_strips_utf8_bom():
 # H4-round-2: a BOM'd 'Date' header must not silently produce zero usable dated rows.
 LD=ROOT/'tests/fixtures/live-data'
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  r=subprocess.run([sys.executable,str(LIVEDATA),'import-gsc',str(p),str(LD/'gsc-export-bom.csv'),'--start','2026-01-01','--end','2026-01-02'],capture_output=True,text=True)
  assert r.returncode==0, r.stderr
  assert 'WARNING' not in r.stderr, f'a BOM-only header issue must not still produce a no-usable-dates warning: {r.stderr}'
  out=json.loads(r.stdout); assert out['rowsImported']==2

@test
def live_data_secret_scanner_catches_broader_shapes():
 # H6/secret-bypass: shapes beyond the originally-reported ones (Stripe, AWS) must also be caught.
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True); run(INIT,'--project',p)
  csv_path=Path(d)/'secret.csv'
  csv_path.write_text('date,clicks,note\n2026-01-01,10,sk_live_ABCDEFGHIJ1234567890\n')
  r=subprocess.run([sys.executable,str(LIVEDATA),'import-gsc',str(p),str(csv_path),'--start','2026-01-01','--end','2026-01-01'],capture_output=True,text=True)
  assert r.returncode==2, f'a Stripe-shaped secret must still be refused: {r.stdout}{r.stderr}'

@test
def guardian_hook_catches_noindex_regardless_of_path():
 # MUST FIX: a noindex directive -- arguably the highest-risk SEO edit there is -- previously
 # had NO content-based coverage at all outside a literal "robots" file-path match.
 def ask(event):
  r=subprocess.run([sys.executable,str(HOOK)],input=json.dumps(event),capture_output=True,text=True,check=True)
  out=json.loads(r.stdout) if r.stdout.strip() else {}
  return out.get('hookSpecificOutput',{}).get('permissionDecision')
 cases=[
  {'tool_input':{'file_path':'/app/page.tsx','content':'<meta name="robots" content="noindex,nofollow" />'}},
  {'tool_input':{'file_path':'/app/layout.tsx','content':'export const metadata={robots:{index:false}}'}},
  {'tool_input':{'file_path':'/middleware.ts','content':'res.headers.set("X-Robots-Tag","noindex")'}},
 ]
 for event in cases: assert ask(event)=='ask', f'a noindex directive must always trigger review: {event}'
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
 # ci_check.py reads .claude/seo/ci.json from the BASE (trusted) side, never the head/PR being
 # audited -- otherwise a PR could ship its own {"failOn":[]} alongside a real regression and
 # silence the gate that's supposed to be checking it. Here `--base-dir after` is the base.
 ci_json=after/'.claude/seo/ci.json'; ci_json.parent.mkdir(parents=True,exist_ok=True)
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
def ci_check_a_pr_cannot_weaken_its_own_gate_via_head_side_config():
 # A malicious PR could add {"failOn":[]} to its OWN .claude/seo/ci.json alongside a real
 # regression, hoping to silence the gate that's supposed to be checking it. Config must be read
 # from the BASE (trusted) side only -- a head-side ci.json weakening failOn must have no effect.
 before,after=_ci_pair()
 (before/'.claude/seo/ci.json').parent.mkdir(parents=True,exist_ok=True)
 (before/'.claude/seo/ci.json').write_text(json.dumps({'failOn':[],'ignore':[]}))
 p=subprocess.run([sys.executable,str(CI),str(before),'--base-dir',str(after)],capture_output=True,text=True)
 assert p.returncode==1, 'a head-side ci.json weakening failOn to [] must NOT suppress a real regression'
 dec=json.JSONDecoder(); out,_=dec.raw_decode(p.stdout)
 assert 'new-high' in out['triggers'], f'the base side\'s default failOn rules must still apply: {out}'

@test
def ci_check_ignore_without_expires_is_never_active():
 before,after=_ci_pair()
 raw=run(CI,before,'--base-dir',after,ok=(0,1))
 dec=json.JSONDecoder(); first,_=dec.raw_decode(raw)
 f=first['diff']['newFindings'][0]
 fp='|'.join([f['tool'],str(f.get('severity','')),(f.get('issue') or '').strip(),(f.get('file') or '').strip()])
 cfg={'failOn':['new-critical','new-high'],'ignore':[{'fingerprint':fp,'reason':'no expiry set'}]}
 ci_json=after/'.claude/seo/ci.json'; ci_json.parent.mkdir(parents=True,exist_ok=True); ci_json.write_text(json.dumps(cfg))
 out2=subprocess.run([sys.executable,str(CI),str(before),'--base-dir',str(after)],capture_output=True,text=True)
 assert out2.returncode==1, 'an ignore with no expires field must never be treated as permanently active'
 parsed,_=dec.raw_decode(out2.stdout)
 assert parsed['expiredIgnores'], f'a missing-expires ignore must be reported as expired, not silently applied: {parsed}'

@test
def ci_check_annotation_output_escapes_workflow_command_injection():
 # A finding whose file path or issue text contains a newline plus a fake workflow command must
 # not let that text start a real, separate GitHub workflow command in the runner's log.
 import ci_check as cc
 d={'newFindings':[{'tool':'seo','severity':'HIGH','issue':'x\n::add-mask::INJECTED','file':'a\r::error::b'}]}
 lines=cc.annotations(d)
 assert len(lines)==1, f'one finding must produce exactly one annotation line, not an injected extra one: {lines}'
 assert '\n' not in lines[0] and '\r' not in lines[0], f'a raw newline/CR would let injected text start a second, separate workflow command: {lines[0]!r}'
 assert '%0A' in lines[0] and '%0D' in lines[0], f'the embedded newline/carriage-return must be percent-escaped, not stripped or passed through: {lines[0]!r}'

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
  out=json.loads(run(SCANLOGS,log,'--ranges',f'Googlebot={ranges}',ok=(0,1)))
  gb=out['summary']['byBotStatus']['Googlebot']
  assert gb.get('200:verified')==1 and gb.get('200:unverified')==1, gb
  # query VALUES are redacted (secrets/PII can ride in a querystring), but the param NAME survives
  assert out['summary']['topParamUrls']==[['/c?utm=<redacted>',1]], out['summary']['topParamUrls']
  assert out['summary']['top404s']==[['/c',1]], out['summary']['top404s']

@test
def scan_logs_never_persists_a_raw_ip():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); log=p/'access.log'
  log.write_text('203.0.113.77 - - [01/Jan/2026:00:00:00 +0000] "GET /a HTTP/1.1" 200 512 "-" "GPTBot/1.0"')
  out=run(SCANLOGS,log,ok=(0,1))
  assert '203.0.113.77' not in out, 'a raw, untruncated IP must never appear in scan_logs.py output'

@test
def scan_logs_ranges_are_scoped_per_vendor_not_pooled():
 # a GPTBot hit from an IP inside Google's (or Bing's) range must NOT be reported "verified" just
 # because SOME --ranges file was loaded for a different bot -- verification must be scoped to
 # the specific vendor's own ranges.
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); log=p/'access.log'
  log.write_text('66.249.66.1 - - [01/Jan/2026:00:00:00 +0000] "GET /a HTTP/1.1" 200 512 "-" "GPTBot/1.0"')
  ranges=p/'google-ranges.json'; ranges.write_text(json.dumps({'prefixes':[{'ipv4Prefix':'66.249.64.0/19'}]}))
  out=json.loads(run(SCANLOGS,log,'--ranges',f'Googlebot={ranges}',ok=(0,1)))
  gb=out['summary']['byBotStatus']['GPTBot']
  assert gb.get('200:verified') is None, f'a GPTBot hit must not be "verified" against Googlebot-scoped ranges: {gb}'
  assert gb.get('200:ua-claimed')==1, gb

@test
def scan_logs_malformed_ranges_file_is_a_hard_error_not_a_silent_drop():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); log=p/'access.log'; log.write_text('1.2.3.4 - - [01/Jan/2026:00:00:00 +0000] "GET /a HTTP/1.1" 200 512 "-" "GPTBot/1.0"')
  bad=p/'bad-ranges.json'; bad.write_text('{not valid json')
  r=subprocess.run([sys.executable,str(SCANLOGS),str(log),'--ranges',f'GPTBot={bad}'],capture_output=True,text=True)
  assert r.returncode==2 and 'could not parse' in (r.stdout+r.stderr).lower(), 'a --ranges file that fails to parse must be a hard, explicit error, not a silent drop that then falsely claims no ranges were given'

@test
def scan_logs_malformed_jsonl_line_is_skipped_not_a_crash():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); log=p/'access.jsonl'
  log.write_text('\n'.join(['["not","an","object"]','{"clientIP":"1.2.3.4","userAgent":"GPTBot/1.0","uri":"/a","status":200}']))
  out=json.loads(run(SCANLOGS,log,'--format','jsonl',ok=(0,1)))
  assert out['summary']['parsedLines']==1, out

@test
def platform_detect_ssg_frontmatter_flags_draft_in_sitemap_and_no_desc():
 out=json.loads(run(PLATFORMS,PLATFORMFIX/'ssg-frontmatter',ok=(0,1)))
 assert 'ssg-frontmatter' in out['detected']
 issues=[f['issue'] for f in out['platforms']['ssg-frontmatter']['findings']]
 assert any('draft:true' in i and 'sitemap' in i for i in issues), issues
 assert out['platforms']['ssg-frontmatter']['unavailable']==[]

@test
def platform_detect_wordpress_flags_missing_wp_head_and_reports_unavailable():
 out=json.loads(run(PLATFORMS,PLATFORMFIX/'wordpress',ok=(0,1)))
 assert 'wordpress' in out['detected']
 wp=out['platforms']['wordpress']
 assert any('wp_head()' in f['issue'] for f in wp['findings']), wp['findings']
 assert wp['unavailable'], 'WordPress adapter must report what it cannot see (plugin-owned SEO data), not stay silent about it'

@test
def platform_detect_shopify_flags_missing_theme_tags_and_reports_unavailable():
 out=json.loads(run(PLATFORMS,PLATFORMFIX/'shopify',ok=(0,)))
 assert 'shopify' in out['detected']
 sp=out['platforms']['shopify']
 assert any('canonical_url' in f['issue'] for f in sp['findings']), sp['findings']
 assert sp['unavailable']

@test
def platform_detect_webflow_flags_missing_title_and_reports_cms_collections_unavailable():
 out=json.loads(run(PLATFORMS,PLATFORMFIX/'webflow',ok=(0,)))
 assert 'webflow' in out['detected']
 wf=out['platforms']['webflow']
 assert any('no title' in f['issue'].lower() for f in wf['findings']), wf['findings']
 assert wf['unavailable']

@test
def platform_detect_headless_cms_flags_missing_slug_and_reports_unavailable():
 out=json.loads(run(PLATFORMS,PLATFORMFIX/'headless-cms',ok=(0,1)))
 assert 'headless-cms' in out['detected']
 hc=out['platforms']['headless-cms']
 assert any('slug field' in f['issue'] for f in hc['findings']), hc['findings']
 assert hc['unavailable']

@test
def platform_detect_finds_nothing_on_a_plain_nextjs_project():
 with tempfile.TemporaryDirectory() as td:
  before=Path(td)/'before'; import shutil as _sh; _sh.copytree(EX/'before',before)
  out=json.loads(run(PLATFORMS,before,ok=(0,)))
  assert out['detected']==[], out['detected']

@test
def validate_ai_access_respects_bot_specific_group_over_wildcard():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)
  (p/'robots.txt').write_text('User-agent: GPTBot\nDisallow: /\n\nUser-agent: *\nAllow: /\n')
  out=json.loads(run(AIACCESS,p,ok=(0,)))
  assert out['accessMatrix']['GPTBot']['blocked'] is True, out['accessMatrix']['GPTBot']
  assert out['accessMatrix']['ClaudeBot']['blocked'] is False, out['accessMatrix']['ClaudeBot']
  assert any('GPTBot' in f['issue'] for f in out['findings'])
  # never a recommendation to allow/block, only a report of the current policy and its documented
  # consequence (the tool's own disclaimer text legitimately contains "recommends", so check for
  # actual advisory phrasing rather than the bare substring)
  full=json.dumps(out).lower()
  assert 'you should' not in full and 'we recommend' not in full

@test
def competitor_diff_ssrf_guard_blocks_loopback_and_never_stores_body_text():
 out=json.loads(run(COMPETITOR,'http://127.0.0.1/internal',ok=(0,)))
 assert out['errors'] and out['errors'][0].get('blocked') is True, out['errors']
 assert out['competitors']==[]

@test
def competitor_diff_from_file_reports_structure_not_body_text():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)/'c.html'
  secret='xyzzy-secret-competitor-copy-do-not-leak'
  p.write_text(f'<html><head><title>Competitor Title</title></head><body><h1>H</h1>{secret} one two three four five six</body></html>')
  out=run(COMPETITOR,'--from-file',f'https://comp.example/x={p}',ok=(0,))
  assert secret not in out, 'competitor body text must never appear in the tool output'
  parsed=json.loads(out)
  assert parsed['competitors'][0]['titleLength']==len('Competitor Title')
  assert parsed['competitors'][0]['wordCount']>0
  full=parsed.copy(); full_text=json.dumps(full).lower()
  assert 'why they rank' not in full_text and 'will rank' not in full_text

@test
def competitor_diff_redirect_to_internal_target_is_refused_not_followed():
 # SSRF bypass 1: a host that passes the guard (simulating a real public host) must not be
 # allowed to then 302 to a private/loopback target -- each hop must be re-validated, not just
 # the first URL before urlopen's own redirect handler silently follows the rest.
 import http.server,threading
 import competitor_diff as cd
 class H(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   self.send_response(302); self.send_header('Location','http://127.0.0.2/admin'); self.end_headers()
  def log_message(self,*a): pass
 srv=http.server.HTTPServer(('127.0.0.1',0),H); port=srv.server_port
 t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
 real_guarded_ip=cd._guarded_ip
 def fake_guarded_ip(host):
  # 'public.example' stands in for a hostname that legitimately resolves to a public IP; every
  # OTHER host (including the redirect target below) still goes through the real, unmocked check.
  if host=='public.example': return '127.0.0.1'
  return real_guarded_ip(host)
 cd._guarded_ip=fake_guarded_ip
 try:
  try:
   cd.fetch(f'http://public.example:{port}/start','test-ua')
   raise AssertionError('a redirect to a loopback target must be refused, not followed')
  except cd.SSRFBlocked as e:
   assert '127.0.0.2' in str(e), f'must name the actual blocked hop, not the original host: {e}'
 finally:
  cd._guarded_ip=real_guarded_ip; srv.shutdown()

@test
def competitor_diff_connection_pins_to_the_ip_the_guard_checked():
 # SSRF bypass 2 (DNS rebinding): the IP the guard validates and the IP actually connected to
 # must be the SAME resolution -- if the code re-resolved the hostname a second time (as
 # urlopen's own resolver would), a hostname whose DNS answer differs between the two lookups
 # could present a safe IP to the guard and a private IP to the real connection. Assert
 # getaddrinfo is consulted exactly once per hostname per hop, proving no second, unpinned
 # resolution happens between the check and the connection.
 import http.server,threading,socket
 import competitor_diff as cd
 class H(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   self.send_response(200); self.send_header('Content-Type','text/html'); self.end_headers()
   self.wfile.write(b'<html><head><title>t</title></head><body>ok</body></html>')
  def log_message(self,*a): pass
 srv=http.server.HTTPServer(('127.0.0.1',0),H); port=srv.server_port
 t=threading.Thread(target=srv.serve_forever,daemon=True); t.start()
 calls=[]
 real_getaddrinfo=socket.getaddrinfo
 def counting_getaddrinfo(host,*a,**kw):
  calls.append(host)
  if host=='rebind.example': return [(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',0))]
  return real_getaddrinfo(host,*a,**kw)
 real_is_global=cd.ipaddress.IPv4Address.is_global
 def patched_is_global(self):
  if str(self)=='127.0.0.1': return True  # stand-in for "this resolved to a real public IP"
  return real_is_global.fget(self)
 socket.getaddrinfo=counting_getaddrinfo
 cd.ipaddress.IPv4Address.is_global=property(patched_is_global)
 try:
  # _guarded_get (not fetch()) isolates a single hop -- fetch() also checks robots.txt as a
  # separate, legitimately independent request, which would double-count resolutions here.
  body=cd._guarded_get(f'http://rebind.example:{port}/x','test-ua')
  assert '<title>t</title>' in body
  assert calls.count('rebind.example')==1, f'hostname must be resolved exactly once (pinned) for one hop, not re-resolved for the connection: {calls}'
 finally:
  socket.getaddrinfo=real_getaddrinfo; cd.ipaddress.IPv4Address.is_global=real_is_global; srv.shutdown()

@test
def competitor_diff_signals_are_not_inflated_by_incidental_matches():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)/'c.html'
  p.write_text('<html><head><title>t</title></head><body>'
               '<nav><a href="/faq">FAQ</a></nav><script>var faq_widget_author=1;</script>'
               '<style>.co-author-widget{color:red}</style>'
               '<h1>Hello</h1></body></html>')
  out=json.loads(run(COMPETITOR,'--from-file',f'https://comp.example/x={p}',ok=(0,)))
  c=out['competitors'][0]
  assert c['hasFAQ'] is False, 'a bare "/faq" nav link must not count as FAQ content'
  assert c['hasAuthorSignal'] is False, 'a class merely containing "author" (co-author-widget) must not count as an author signal'
  assert c['wordCount']<=3, f'script/style text must not be counted as visible words: {c["wordCount"]}'

@test
def competitor_diff_traversal_host_cannot_escape_the_competitors_directory():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)/'c.html'; p.write_text('<html><head><title>t</title></head><body>x</body></html>')
  proj=Path(td)/'proj'; proj.mkdir()
  run(COMPETITOR,'--from-file',f'https://../evil/x={p}','--out',str(proj),ok=(0,))
  assert not (proj.parent/'.claude').exists(), 'a ".." host must never let output escape .claude/seo/competitors/'
  assert (proj/'.claude/seo/competitors').exists()

@test
def live_data_import_ai_referrals_filters_to_known_ai_hosts_and_flags_undercount():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); run(INIT,'--project',p)
  csv=p/'ref.csv'; csv.write_text('date,source,sessions\n2026-01-01,chatgpt.com,12\n2026-01-01,google.com,500\n2026-01-02,perplexity.ai,3\n')
  out=json.loads(run(LIVEDATA,'import-ai-referrals',p,csv,'--start','2026-01-01','--end','2026-01-02',ok=(0,)))
  assert out['rowsImported']==2 and out['rowsInSource']==3, out
  written=json.loads(Path(out['wrote']).read_text())
  assert 'UNDERCOUNTS' in written['limits']

@test
def live_data_import_ai_referrals_host_matching_has_no_overcount_or_undercount():
 with tempfile.TemporaryDirectory() as td:
  p=Path(td); run(INIT,'--project',p)
  csv=p/'ref.csv'; csv.write_text(
   'date,source,sessions\n'
   '2026-01-01,claude.ai.evil.com,99\n'      # must NOT match (not a real claude.ai subdomain)
   '2026-01-01,chat.openai.com,7\n'          # must match (previously missed)
   '2026-01-01,sub.claude.ai,4\n')           # must match (real subdomain boundary)
  out=json.loads(run(LIVEDATA,'import-ai-referrals',p,csv,'--start','2026-01-01','--end','2026-01-01',ok=(0,)))
  assert out['rowsImported']==2, f'expected exactly chat.openai.com and sub.claude.ai to match: {out}'

@test
def build_dist_produces_a_valid_plugin_layout_without_duplicating_plugin_files():
 with tempfile.TemporaryDirectory() as td:
  out=Path(td)/'dist'
  run(BUILDDIST,out,ok=(0,))
  plugin=json.loads((out/'.claude-plugin/plugin.json').read_text())
  hooks=json.loads((out/'hooks/hooks.json').read_text())
  assert plugin['name']=='seo-architect'
  assert 'CLAUDE_PLUGIN_ROOT' in hooks['PreToolUse'][0]['hooks'][0]['command']
  assert (out/'skills/seo-architect/SKILL.md').exists()
  assert (out/'skills/seo-architect/scripts/guardian_hook.py').exists()
  assert not (out/'skills/seo-architect/.claude-plugin').exists(), 'plugin.json must not be duplicated inside skills/seo-architect'
  assert not (out/'skills/seo-architect/hooks').exists(), 'hooks.json must not be duplicated inside skills/seo-architect'

@test
def seo_tools_max_files_env_cap_bounds_scan_time_on_a_large_tree():
 import os,time
 with tempfile.TemporaryDirectory() as td:
  p=Path(td)
  for i in range(5000):
   d=p/f'app/page{i}'; d.mkdir(parents=True); (d/'page.html').write_text(f'<html><title>P{i}</title></html>')
  env=dict(os.environ); env['SEO_ARCHITECT_MAX_FILES']='200'
  t0=time.time()
  r=subprocess.run([sys.executable,str(TOOLS),'metadata',str(p)],capture_output=True,text=True,env=env)
  elapsed=time.time()-t0
  assert r.returncode in (0,1), r.stderr
  assert elapsed<30, f'a 5000-file tree with SEO_ARCHITECT_MAX_FILES=200 took {elapsed:.1f}s -- the cap is not bounding scan time'

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
