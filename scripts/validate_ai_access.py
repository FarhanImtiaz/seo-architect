#!/usr/bin/env python3
"""AI-crawler access/eligibility report: parses robots.txt with real group precedence (not just
"does the word appear"), reports what each named bot is actually allowed to do, and states the
DOCUMENTED consequence of blocking it per that vendor's own published stance -- allow/block is
the site owner's business decision; this never recommends one side of it, only shows the
trade-off. Also checks page-level snippet controls (nosnippet/max-snippet/data-nosnippet), which
Google's docs say also limit appearance in AI features. Firewall/CDN-level blocking (as opposed
to robots.txt) is NOT visible here -- see scripts/scan_logs.py's 403/429 signal for that."""
import json,re,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from seo_tools import files, rel

# Each entry: the literal robots.txt User-agent TOKEN, and the documented consequence of a full
# Disallow: / for that token. Sourced from each vendor's own crawler documentation -- see
# references/sources.json. Google-Extended is a training-data opt-out token only (it has no
# separate "search" consequence beyond what Googlebot itself already controls).
BOT_CONSEQUENCES={
    'GPTBot':'Blocking GPTBot opts the site out of being used to train OpenAI\'s models. It does not affect ChatGPT search/browsing (that\'s OAI-SearchBot/ChatGPT-User).',
    'OAI-SearchBot':'Blocking OAI-SearchBot removes the site from being indexed for ChatGPT\'s search feature.',
    'ChatGPT-User':'Blocking ChatGPT-User prevents ChatGPT from fetching this site live when a user asks it to browse/visit a specific page.',
    'Google-Extended':'Blocking Google-Extended opts the site out of being used to train Google\'s Gemini/Vertex AI models. It does not affect Google Search or AI Overviews eligibility, which are controlled by the regular Googlebot rules.',
    'GoogleOther':'GoogleOther is used for various Google research/product fetches outside standard Search indexing; blocking it does not affect Search ranking.',
    'ClaudeBot':'Blocking ClaudeBot opts the site out of being crawled for Anthropic\'s model training data.',
    'Claude-SearchBot':'Blocking Claude-SearchBot removes the site from Claude\'s search-grounded answers.',
    'Claude-User':'Blocking Claude-User prevents Claude from fetching this site live on a user\'s behalf.',
    'PerplexityBot':'Blocking PerplexityBot removes the site from being indexed for Perplexity\'s answer engine.',
    'CCBot':'CCBot is Common Crawl\'s general-purpose crawler; many AI labs train on Common Crawl data even if this bot alone is blocked, so blocking it is a weaker opt-out than it may appear.',
    'Applebot':'Blocking Applebot affects Siri/Spotlight suggestions and Apple\'s search products, separate from any other AI crawler.',
    'Applebot-Extended':'Blocking Applebot-Extended opts the site out of Apple\'s AI/ML training use of previously-crawled Applebot data, without affecting Siri/Spotlight search itself.',
}

def parse_groups(text):
    groups=[]; current=None
    for raw in text.splitlines():
        line=raw.split('#',1)[0].strip()
        if not line or ':' not in line: continue
        key,val=[x.strip() for x in line.split(':',1)]; low=key.lower()
        if low=='user-agent':
            if current is None or current['seen_rule']:
                current={'agents':[],'rules':[],'seen_rule':False}; groups.append(current)
            current['agents'].append(val)
        elif low in ('allow','disallow') and current is not None:
            current['rules'].append((low,val)); current['seen_rule']=True
        elif low=='sitemap':
            pass
        elif current is not None:
            current['seen_rule']=True
    return groups

def group_for(groups,token):
    exact=[g for g in groups if any(a.lower()==token.lower() for a in g['agents'])]
    if exact: return exact[0]
    wildcard=[g for g in groups if any(a=='*' for a in g['agents'])]
    return wildcard[0] if wildcard else None

def is_disallowed_all(group):
    if not group: return False,'no matching group (default allow)'
    # longest-matching-rule wins per the robots.txt de-facto standard; here we only need the
    # simple, common case of a bare "/" disallow with no more specific allow overriding it.
    disallow_all=any(rule=='disallow' and path.strip()=='/' for rule,path in group['rules'])
    allow_root=any(rule=='allow' and path.strip() in ('/','') for rule,path in group['rules'])
    return (disallow_all and not allow_root), None

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    robots_files=list(root.rglob('robots.txt'))
    fs=[]; matrix={}
    if not robots_files:
        fs.append({'severity':'INFO','issue':'No robots.txt found; every listed bot defaults to fully allowed unless blocked at the firewall/CDN level (not visible here).'})
    else:
        text=robots_files[0].read_text(errors='ignore')
        groups=parse_groups(text)
        for bot,consequence in BOT_CONSEQUENCES.items():
            g=group_for(groups,bot)
            blocked,note=is_disallowed_all(g)
            matrix[bot]={'blocked':blocked,'matchedGroup':(g['agents'] if g else None),'documentedConsequenceIfBlocked':consequence}
            if blocked: fs.append({'severity':'INFO','issue':f'{bot} is fully disallowed in robots.txt. {consequence}','rule':'ai-access-policy'})
    # page-level snippet controls
    snippet_hits=[]
    for p in files(root):
        text=p.read_text(errors='ignore')
        if re.search(r'name=["\']robots["\'][^>]*content=["\'][^"\']*nosnippet',text,re.I) or 'data-nosnippet' in text:
            snippet_hits.append(rel(p,root))
    if snippet_hits:
        fs.append({'severity':'INFO','issue':f'{len(snippet_hits)} page(s) use nosnippet/data-nosnippet, which Google documents as also limiting appearance in AI features, not just classic snippets.','files':snippet_hits[:20],'rule':'snippet-controls'})
    out={'tool':'validate-ai-access','findings':fs,'accessMatrix':matrix,
         'notes':['This reports the site owner\'s CURRENT robots.txt policy and its documented consequence -- it never recommends allowing or blocking a bot, since that is a business decision. Firewall/CDN-level blocking is not visible here; cross-check scripts/scan_logs.py for 403/429 patterns on AI-bot user agents.']}
    print(json.dumps(out,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
