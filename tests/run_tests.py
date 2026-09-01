#!/usr/bin/env python3
import json, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; TOOLS=ROOT/'scripts/seo_tools.py'; INIT=ROOT/'scripts/init_state.py'; FIX=ROOT/'tests/fixtures/site'; HOOK=ROOT/'scripts/guardian_hook.py'; LEDGER=ROOT/'scripts/evidence_ledger.py'; CONTRACT=ROOT/'scripts/validate_page_contract.py'; FRAMEWORK=ROOT/'scripts/framework_inspect.py'; ADAPTERS=ROOT/'scripts/framework_adapters.py'; AEO=ROOT/'scripts/validate_aeo.py'; FULL=ROOT/'scripts/full_audit.py'; CLAUDE=ROOT/'scripts/validate_claude_skill.py'
def run(*args, ok=(0,)):
 p=subprocess.run([sys.executable,*map(str,args)],capture_output=True,text=True)
 if p.returncode not in ok: raise AssertionError(f'{args}: {p.returncode}\n{p.stdout}\n{p.stderr}')
 return p.stdout
def main():
 with tempfile.TemporaryDirectory() as d:
  p=Path(d); subprocess.run(['cp','-R',str(FIX)+'/.',str(p)],check=True)
  out=json.loads(run(INIT,'--project',p)); assert (p/'.claude/seo/config.json').exists() and out['created']
  assert (p/'.claude/seo/evidence.json').exists()
  for cmd in ('routes','metadata','sitemap','robots','jsonld','links'): json.loads(run(TOOLS,cmd,p))
  assert json.loads(run(ADAPTERS,p,ok=(0,1)))['observed']
  all_results=json.loads(run(FULL,p,'--snapshot',ok=(0,1))); assert set(('metadata','aeo','regression')).issubset(all_results['checks'])
  subprocess.run(['cp',str(ROOT/'tests/fixtures/aeo-page.html'),str(p/'app/aeo-page.html')],check=True)
  aeo=json.loads(run(AEO,p)); assert any(x['signals']['questionHeading'] and x['signals']['comparison'] for x in aeo['pages'])
  baseline=json.loads(run(TOOLS,'snapshot',p)); assert baseline['snapshot']['version']==2 and baseline['snapshot']['pages']
  page=p/'app/page.html'; page.write_text(page.read_text().replace('Example</title>','Changed</title>')); data=json.loads(run(TOOLS,'compare',p,ok=(0,1))); assert any('title' in x['issue'] for x in data['findings'])
  page.unlink(); data=json.loads(run(TOOLS,'compare',p,ok=(0,1))); assert any(x['severity']=='HIGH' for x in data['findings'])
  event={'tool_input':{'file_path':str(p/'robots.txt'),'new_string':'User-agent: *\nDisallow: /'}}
  result=subprocess.run([sys.executable,str(HOOK)],input=json.dumps(event),capture_output=True,text=True,check=True); assert json.loads(result.stdout)['hookSpecificOutput']['permissionDecision']=='ask'
  event={'tool_input':{'file_path':str(p/'components/Button.tsx'),'new_string':'color: red'}}
  result=subprocess.run([sys.executable,str(HOOK)],input=json.dumps(event),capture_output=True,text=True,check=True); assert not result.stdout.strip()
  run(LEDGER,'add',p,'--claim','A verified service exists','--source','project brief'); assert json.loads(run(LEDGER,'verify',p))['result']=='pass'
  assert json.loads(run(CONTRACT,'service','--brief',ROOT/'tests/fixtures/service-brief.json'))['result']=='pass'
  assert json.loads(run(CONTRACT,'location','--brief',ROOT/'tests/fixtures/location-brief.json'))['result']=='pass'
  assert json.loads(run(FRAMEWORK,p))['framework'] in ('unknown','nextjs')
  assert 'PASS' in run(CLAUDE,ROOT)
 # Policy scenarios remain explicit acceptance requirements where agent-run evaluation is unavailable.
 text=(ROOT/'SKILL.md').read_text(); required=['doorway/location pages','fabricate proof','Review first','A purely visual button-style change']
 assert all(x in text or x in (ROOT/'workflows/optimize.md').read_text() for x in required)
 print('PASS: state, 6 validators, Guardian risk controls, evidence ledger, page contracts, framework detection, and regression scenarios.')
if __name__=='__main__': main()
