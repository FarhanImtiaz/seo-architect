#!/usr/bin/env python3
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; TOOLS=ROOT/'scripts/seo_tools.py'; INIT=ROOT/'scripts/init_state.py'; FIX=ROOT/'tests/fixtures/site'; HOOK=ROOT/'scripts/guardian_hook.py'; LEDGER=ROOT/'scripts/evidence_ledger.py'; CONTRACT=ROOT/'scripts/validate_page_contract.py'; FRAMEWORK=ROOT/'scripts/framework_inspect.py'; ADAPTERS=ROOT/'scripts/framework_adapters.py'; AEO=ROOT/'scripts/validate_aeo.py'; FULL=ROOT/'scripts/full_audit.py'; CLAUDE=ROOT/'scripts/validate_claude_skill.py'; SCORE=ROOT/'scripts/score.py'; VALSRC=ROOT/'scripts/validate_sources.py'; PATTERNMATCH=ROOT/'scripts/pattern_match.py'; LINKGRAPH=ROOT/'scripts/scan_link_graph.py'; IMAGES=ROOT/'scripts/scan_images.py'; METAEXTRACT=ROOT/'scripts/metadata_extract.py'; HREFLANG=ROOT/'scripts/validate_hreflang.py'; LIVEDATA=ROOT/'scripts/live_data.py'
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
  out=json.loads(run(LIVEDATA,'import-gsc',p,LD/'gsc-export.csv',ok=(0,)))
  assert out['rowsImported']==2
  written=list((p/'.claude/seo/measurement').glob('*-search-console.json'))
  assert len(written)==1
  saved=json.loads(written[0].read_text())
  assert saved['source']=='search-console' and len(saved['rows'])==2
  r=subprocess.run([sys.executable,str(LIVEDATA),'import-gsc',str(p),str(LD/'gsc-export-with-secret.csv')],capture_output=True,text=True)
  assert r.returncode==2 and 'secret' in (r.stdout+r.stderr).lower()
  env=dict(**{k:v for k,v in __import__('os').environ.items() if k!='CRUX_API_KEY'})
  r=subprocess.run([sys.executable,str(LIVEDATA),'crux',str(p),'example.com'],capture_output=True,text=True,env=env)
  assert r.returncode==2, 'crux without CRUX_API_KEY must fail closed, never silently fabricate field data'
  assert 'CRUX_API_KEY' in r.stdout

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
