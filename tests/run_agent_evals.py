#!/usr/bin/env python3
"""Optional: runs tests/agent-evals/*.json prompts through `claude -p` (an agent-evaluated
check, not a mechanical one) and prints a human-reviewable transcript per scenario. SKIPs
entirely when the `claude` CLI isn't on PATH -- never part of the default test gate
(tests/run_tests.py does not import or call this)."""
import json,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EVALS=ROOT/'tests/agent-evals'

def main():
    if not shutil.which('claude'):
        print('SKIP: `claude` CLI not found on PATH; agent-evaluated scenarios were not run.')
        print('This is expected in CI/sandboxed environments -- see tests/smoke-tests.md for the mechanical gate.')
        return 0
    scenarios=sorted(EVALS.glob('*.json'))
    if not scenarios:
        print('SKIP: no scenarios found in tests/agent-evals/.'); return 0
    for path in scenarios:
        scenario=json.loads(path.read_text())
        print(f"\n=== {scenario['id']} ===")
        print(f"Prompt: {scenario['prompt']}")
        result=subprocess.run(['claude','-p',scenario['prompt']],cwd=ROOT,capture_output=True,text=True,timeout=120)
        print('--- response ---')
        print(result.stdout.strip() or '(no stdout)')
        print('--- required behaviors (read the response above and judge each) ---')
        for b in scenario['requiredBehaviors']: print(f'  [ ] {b}')
        print('--- forbidden outputs (must NOT appear above) ---')
        for f in scenario['forbiddenOutputs']: print(f'  [ ] {f}')
    print('\nThese scenarios require human/agent judgment, not a pass/fail assertion -- review each transcript above.')
    return 0
if __name__=='__main__': raise SystemExit(main())
