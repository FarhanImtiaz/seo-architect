#!/usr/bin/env python3
"""Enforce citation discipline for references/winning-patterns.md against references/sources.json.
Never lets an invented statistic or an unverifiable claim pass silently."""
import argparse,json,re,sys
from datetime import date,datetime
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_HEADINGS=['Documented evidence','Mechanism','Applies when','Verify here','Skill action','Do not claim']
FORBIDDEN_PHRASES=['guarantee','will rank','will increase traffic','#1 on google','boost rankings by']
NEGATION=re.compile(r'\b(never|not|no|cannot|don\'t|does not|doesn\'t|isn\'t|without a)\b',re.I)

def promised_phrases(text):
    """Returns forbidden phrases that appear WITHOUT a nearby negation, i.e. read as an actual promise
    rather than the skill's own required 'never guarantee X' safety language."""
    lower=text.lower(); found=[]
    for phrase in FORBIDDEN_PHRASES:
        for m in re.finditer(re.escape(phrase),lower):
            window=lower[max(0,m.start()-100):m.start()]
            if not NEGATION.search(window): found.append(phrase)
    return found

def parse_cards(text):
    cards=[]
    for block in re.split(r'\n(?=## )',text)[1:]:
        title_line=block.splitlines()[0]
        m=re.match(r'##\s*(P\d\d[a-z]?)\.\s*(.+)',title_line)
        if not m: continue
        cards.append({'id':m.group(1),'title':m.group(2).strip(),'body':block})
    return cards

def check_card(card,sources):
    errors=[]; warnings=[]
    for h in REQUIRED_HEADINGS:
        if f'**{h}:**' not in card['body']: errors.append(f'{card["id"]}: missing required heading "{h}"')
    ev=re.search(r'\*\*Documented evidence:\*\*\s*(.+)',card['body'])
    cited=[]
    if ev:
        cited=[x.strip() for x in ev.group(1).split(',')]
        for sid in cited:
            if sid not in sources: errors.append(f'{card["id"]}: cites unknown source id "{sid}"')
    else:
        errors.append(f'{card["id"]}: no Documented evidence line to parse')
    cited_sources=[sources[s] for s in cited if s in sources]
    if cited_sources and all(not s.get('numbersQuotable',True) for s in cited_sources):
        if re.search(r'\d+(\.\d+)?%',card['body']): errors.append(f'{card["id"]}: quotes a percentage figure but every cited source is non-quotable (tier C)')
    for phrase in promised_phrases(card['body']): errors.append(f'{card["id"]}: contains unhedged promise phrase "{phrase}"')
    return errors,warnings

def check_sources(sources):
    errors=[]; warnings=[]
    for sid,s in sources.items():
        url=s.get('url','')
        if urlparse(url).scheme!='https': errors.append(f'{sid}: url is not https: {url}')
        if s.get('tier')=='C' and s.get('numbersQuotable',True): errors.append(f'{sid}: tier C source must have numbersQuotable:false')
        lv=s.get('lastVerified')
        if lv=='pending': warnings.append(f'{sid}: lastVerified is "pending" — a human has not confirmed this source yet')
        else:
            try:
                if (date.today()-datetime.strptime(lv,'%Y-%m-%d').date()).days>365: warnings.append(f'{sid}: lastVerified is over 12 months old ({lv})')
            except (ValueError,TypeError): errors.append(f'{sid}: lastVerified is not a valid ISO date or "pending": {lv!r}')
    return errors,warnings

def check_repo_forbidden_phrases(root):
    errors=[]
    for pattern in ('references/*.md','workflows/*.md','SKILL.md'):
        for p in root.glob(pattern):
            for phrase in promised_phrases(p.read_text()): errors.append(f'{p.relative_to(root)}: contains unhedged promise phrase "{phrase}"')
    return errors

def check_ids_referenced_exist(root,pattern_ids):
    errors=[]
    for p in root.glob('workflows/*.md'):
        for pid in re.findall(r'\bP\d\d[a-z]?\b',p.read_text()):
            if pid not in pattern_ids: errors.append(f'{p.relative_to(root)}: references unknown pattern id {pid}')
    return errors

def main():
    q=argparse.ArgumentParser(); q.add_argument('project',nargs='?',default='.'); q.add_argument('--check-urls',action='store_true'); a=q.parse_args()
    root=Path(a.project).resolve()
    sources_path=root/'references/sources.json'; patterns_path=root/'references/winning-patterns.md'
    if not sources_path.exists() or not patterns_path.exists():
        print(json.dumps({'result':'fail','errors':['references/sources.json or references/winning-patterns.md not found'],'warnings':[]},indent=2)); return 2
    sources={s['id']:s for s in json.loads(sources_path.read_text())['sources']}
    cards=parse_cards(patterns_path.read_text())
    errors=[]; warnings=[]
    se,sw=check_sources(sources); errors+=se; warnings+=sw
    for card in cards:
        ce,cw=check_card(card,sources); errors+=ce; warnings+=cw
    errors+=check_repo_forbidden_phrases(root)
    errors+=check_ids_referenced_exist(root,{c['id'] for c in cards})
    if a.check_urls:
        import urllib.request
        for sid,s in sources.items():
            try: urllib.request.urlopen(urllib.request.Request(s['url'],method='HEAD'),timeout=5)
            except Exception as e: warnings.append(f'{sid}: URL check failed: {e}')
    pending_ids=[sid for sid,s in sources.items() if s.get('lastVerified')=='pending']
    result={'result':'pass' if not errors else 'fail','cardsChecked':len(cards),'sourcesChecked':len(sources),'pendingCount':len(pending_ids),'pendingSourceIds':sorted(pending_ids),'errors':errors,'warnings':warnings}
    print(json.dumps(result,indent=2))
    return 1 if errors else 0
if __name__=='__main__': raise SystemExit(main())
