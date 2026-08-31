#!/usr/bin/env python3
"""Claude Code PreToolUse hook: require review for high-risk SEO edits."""
import json, sys
from pathlib import Path

def output(decision=None, reason='', context=''):
    value={'hookSpecificOutput':{'hookEventName':'PreToolUse'}}
    if decision: value['hookSpecificOutput']['permissionDecision']=decision; value['hookSpecificOutput']['permissionDecisionReason']=reason
    if context: value['hookSpecificOutput']['additionalContext']=context
    print(json.dumps(value))

def main():
    try: event=json.load(sys.stdin)
    except json.JSONDecodeError: return 0
    inp=event.get('tool_input',{}); path=str(inp.get('file_path','')).replace('\\','/').lower()
    changed=(str(inp.get('content',''))+'\n'+str(inp.get('new_string',''))).lower()
    sensitive=any(x in path for x in ('/app/','/pages/','/src/routes/','/src/pages/','sitemap','robots','redirect','metadata','layout','schema','navigation','footer'))
    high=any(x in path for x in ('robots','redirect','sitemap')) or any(x in changed for x in ('rel="canonical"','rel=\'canonical\'','"@type":"review"','"@type":"aggregateRating"','permanentredirect','redirect('))
    if high:
        output('ask','SEO Guardian: this edit may change indexation, URL routing, canonicalization, redirects, or schema claims. Review evidence and migration impact before applying.', 'After approval: validate affected files, run regression compare, and update .claude/seo/changelog.md.')
    elif sensitive:
        output(context='SEO Guardian: this is search-sensitive. Preserve intent and visible-content/schema alignment; validate metadata, links, and regression impact after the edit.')
    return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc: print(f'guardian hook warning: {exc}',file=sys.stderr); raise SystemExit(0)
