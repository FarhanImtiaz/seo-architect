#!/usr/bin/env python3
"""Claude Code PreToolUse hook: require review for high-risk SEO edits."""
import json, re, sys
from pathlib import Path

# Path tokens: file paths/names that are inherently high-risk (redirect/rewrite configs included --
# a Fable-5.1 QA pass found next.config.js/vercel.json/netlify.toml/.htaccess redirects were
# previously invisible to this hook entirely).
HIGH_PATH_TOKENS=('robots','redirect','sitemap','next.config','vercel.json','netlify.toml','.htaccess')
SENSITIVE_PATH_TOKENS=('/app/','/pages/','/src/routes/','/src/pages/','sitemap','robots','redirect','metadata','layout','schema','navigation','footer','next.config','vercel.json','netlify.toml','.htaccess')

# Content patterns, matched case-insensitively via regex (not a plain lowercase substring check --
# the old needles like '"@type":"aggregateRating"' had a capital R and could never match after the
# haystack was lowercased; they also assumed no whitespace around ':'). Applied to BOTH old_string
# and new_string, so a removal (e.g. deleting a canonical tag) is caught, not just an addition.
_HIGH_RISK_PATTERNS=[re.compile(p,re.I|re.S) for p in (
    r'rel\s*=\s*["\']canonical["\']',
    r'rel\s*:\s*["\']canonical["\']',           # canonical as an object property, not a JSX attr: {rel:"canonical"}
    r'["\']@type["\']\s*:\s*["\'](aggregaterating|review)["\']',
    r'@type["\']?\s*:\s*\[[^\]]{0,100}(aggregaterating|review)',  # "@type": ["Review", ...]
    r'\baggregaterating\s*:',
    r'\breview\s*:\s*\{',
    r'permanentredirect',
    r'\bredirect\s*\(',
    r'\bredirects\s*\(\s*\)\s*\{',      # Next.js next.config.js redirects() function
    r'\brouterules\s*:',                 # Nuxt routeRules
    r'redirectmatch',                    # .htaccess RedirectMatch
    r'^\s*redirect(?:match)?\s+\d',      # .htaccess "Redirect 301 /old /new"
    r'return\s+301\b',                   # nginx return 301
    r'rewrite\s+\S+\s+\S+\s+permanent',  # nginx rewrite ... permanent
    r'alternates\s*:\s*\{[^{}]{0,300}canonical',  # Next.js alternates:{canonical:...}
    # Noindex directives -- arguably the single highest-risk SEO edit (can deindex a page
    # outright) and previously had NO content coverage at all (only a path-token match on
    # literally having "robots" in the file path). Matched regardless of path.
    r'\bnoindex\b',
    r'x-robots-tag',
    r'\bindex\s*:\s*false\b',
)]

def _high_risk(text):
    return bool(text) and any(p.search(text) for p in _HIGH_RISK_PATTERNS)

def output(decision=None, reason='', context=''):
    value={'hookSpecificOutput':{'hookEventName':'PreToolUse'}}
    if decision: value['hookSpecificOutput']['permissionDecision']=decision; value['hookSpecificOutput']['permissionDecisionReason']=reason
    if context: value['hookSpecificOutput']['additionalContext']=context
    print(json.dumps(value))

def _claims_context(path,raw_text):
    """Advisory only, never blocks: flags unbacked outcome language when writing under
    .claude/seo/ or into a report-shaped file. Best-effort -- any import/parse problem is
    swallowed so it can never turn into a false block."""
    if not raw_text or not ('.claude/seo/' in path or 'report' in path): return None
    try:
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from validate_claims import scan_text
        findings=scan_text(raw_text)
    except Exception: return None
    if not findings: return None
    quoted=', '.join(f'"{f["match"]}"' for f in findings[:3])
    return f'SEO Guardian: this text contains outcome language ({quoted}) with no nearby citation to an impact/ result or evidence-ledger entry. Confirm it is backed by real imported data (scripts/impact.py evaluate) or soften the wording -- do not block, just verify before this ships.'

def main():
    try: event=json.load(sys.stdin)
    except json.JSONDecodeError: return 0
    inp=event.get('tool_input',{}); path=str(inp.get('file_path','')).replace('\\','/').lower()
    raw=str(inp.get('content','')) or str(inp.get('new_string',''))
    old_raw=str(inp.get('old_string',''))  # a removal (e.g. deleting a canonical tag) is just as review-worthy as an addition
    sensitive=any(x in path for x in SENSITIVE_PATH_TOKENS)
    high=any(x in path for x in HIGH_PATH_TOKENS) or _high_risk(raw) or _high_risk(old_raw)
    claims=_claims_context(path,raw)
    if high:
        output('ask','SEO Guardian: this edit may change indexation, URL routing, canonicalization, redirects, or schema claims. Review evidence and migration impact before applying.', claims or 'After approval: validate affected files, run regression compare, and update .claude/seo/changelog.md.')
    elif sensitive or claims:
        output(context=claims or 'SEO Guardian: this is search-sensitive. Preserve intent and visible-content/schema alignment; validate metadata, links, and regression impact after the edit.')
    return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc: print(f'guardian hook warning: {exc}',file=sys.stderr); raise SystemExit(0)
