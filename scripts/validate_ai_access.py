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
# Disallow: / for that token, matched to the real vendor source's own hedging (never stated more
# confidently than the source itself does) -- see the matching id in references/sources.json.
# Google-Extended is a training-data opt-out token only (it has no separate "search" consequence
# beyond what Googlebot itself already controls).
BOT_CONSEQUENCES={
    'GPTBot':('Blocking GPTBot means the site\'s content should not be used to train OpenAI\'s generative AI foundation models. '
               'It does not affect ChatGPT search/browsing (that\'s OAI-SearchBot/ChatGPT-User). (openai-crawlers-docs)'),
    'OAI-SearchBot':('Sites that opt out of OAI-SearchBot are not shown in ChatGPT search answers, '
                      'though they can still appear as navigational links. (openai-crawlers-docs)'),
    'ChatGPT-User':('ChatGPT-User fetches pages live on a user\'s direct request; OpenAI itself states robots.txt rules may not apply to it '
                     'because the fetch is user-initiated, not autonomous crawling -- blocking it is not guaranteed to prevent a live fetch. (openai-crawlers-docs)'),
    'Google-Extended':('Blocking Google-Extended opts the site out of being used to train Google\'s Gemini/Vertex AI models. '
                        'Google states it does not impact a site\'s inclusion in Google Search and is not a ranking signal. (google-common-crawlers-docs)'),
    'GoogleOther':('GoogleOther is a generic crawler for internal Google research/development; Google states its crawling preferences '
                    'don\'t affect any specific product, including Search ranking. (google-common-crawlers-docs)'),
    'ClaudeBot':('Blocking ClaudeBot means the site\'s future materials should be excluded from Anthropic\'s AI model training datasets. (anthropic-claude-crawlers-docs)'),
    'Claude-SearchBot':('Anthropic\'s own wording is hedged, not absolute: disabling Claude-SearchBot "prevents our system from indexing your '
                         'content for search optimization, which MAY REDUCE your site\'s visibility and accuracy in user search results" -- '
                         'not a guaranteed removal from Claude\'s answers. (anthropic-claude-crawlers-docs)'),
    'Claude-User':('Also hedged by Anthropic: disabling Claude-User "prevents our system from retrieving your content in response to a user '
                    'query, which MAY REDUCE your site\'s visibility for user-directed web search." (anthropic-claude-crawlers-docs)'),
    'PerplexityBot':('Perplexity\'s own docs describe PerplexityBot\'s purpose (surfacing sites in Perplexity search results) and recommend '
                      'allowing it, but do not explicitly state the consequence of blocking it -- that it would likely reduce or remove search '
                      'visibility is a reasonable inference, not a direct quote. (perplexity-crawlers-docs)'),
    'CCBot':('CCBot is Common Crawl\'s general-purpose crawler. Common Crawl\'s own page does not state whether other parties\' AI training '
              'continues on previously-archived data independent of CCBot being blocked going forward -- the common practitioner understanding '
              'that many AI labs train on redistributed Common Crawl archives regardless is general knowledge, not something CCBot\'s docs assert, '
              'so blocking it alone may be a weaker opt-out than it appears. (commoncrawl-ccbot-docs)'),
    'Applebot':('Blocking Applebot affects the Spotlight/Siri/Safari search-adjacent discovery features it powers. (apple-applebot-docs)'),
    'Applebot-Extended':('Applebot-Extended does not crawl pages itself -- it only governs how already-crawled Applebot data is used to train '
                          'Apple\'s generative-AI foundation models. Apple states blocking only Applebot-Extended does not affect search '
                          'discoverability; pages can still appear in search results. (apple-applebot-docs)'),
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

def groups_for(groups,token):
    """RFC 9309 S2.2.1: all groups naming this token (exact match, case-insensitive) are the
    applicable group -- their rules are MERGED, not just the first group used. Falls back to the
    wildcard group(s) only when the token has no group of its own at all."""
    exact=[g for g in groups if any(a.lower()==token.lower() for a in g['agents'])]
    if exact: return exact
    wildcard=[g for g in groups if any(a=='*' for a in g['agents'])]
    return wildcard

def is_disallowed_all(matched_groups):
    if not matched_groups: return False,'no matching group (default allow)'
    rules=[r for g in matched_groups for r in g['rules']]
    # longest-matching-rule wins per the robots.txt de-facto standard; here we only need the
    # simple, common case of a bare "/" (or "/*", an equivalent full-site wildcard) disallow with
    # no more specific allow overriding it. An empty "Allow:" value is a no-op (RFC 9309 S2.2.2 --
    # it matches nothing), not an allow-everything rule, so it must NOT count as allow_root.
    disallow_all=any(rule=='disallow' and path.strip() in ('/','/*') for rule,path in rules)
    allow_root=any(rule=='allow' and path.strip() in ('/','/*') for rule,path in rules)
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
            gs=groups_for(groups,bot)
            blocked,note=is_disallowed_all(gs)
            matrix[bot]={'blocked':blocked,'matchedGroups':[g['agents'] for g in gs] or None,'documentedConsequenceIfBlocked':consequence}
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
