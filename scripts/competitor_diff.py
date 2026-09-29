#!/usr/bin/env python3
"""Structural diff against a user-named PUBLIC competitor page: title length, heading outline,
schema types, word count, FAQ/table/comparison presence, author/date signals, canonical,
hreflang, internal-link count. Output is framed as "structural differences vs. your page",
explicitly NEVER "why they rank" -- this tool has no ranking data and must never imply it does.
Body text is never stored, only hashes/outlines. Actual rank data must come from the user, a
dated WebSearch observation, or a connected rank-tracking import -- never invented here."""
import argparse,hashlib,ipaddress,json,re,socket,sys,time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request,urlopen

MAX_BYTES=3*1024*1024
MIN_INTERVAL=2.0
_last_fetch=[0.0]

class SSRFBlocked(Exception): pass

def _resolve_and_guard(host):
    """Refuses private, loopback, and link-local addresses -- both the hostname's literal form
    (if it's already an IP) and every address DNS resolves it to, so a DNS-rebinding or
    IP-literal attempt to reach internal infrastructure is refused before any request is made."""
    try: infos=socket.getaddrinfo(host,None)
    except socket.gaierror as e: raise SSRFBlocked(f'DNS resolution failed for {host}: {e}')
    for info in infos:
        ip=info[4][0]
        addr=ipaddress.ip_address(ip)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast:
            raise SSRFBlocked(f'{host} resolves to {ip}, a private/loopback/link-local/reserved address; refusing to fetch it.')
    return True

def _robots_allows(base,path,ua):
    try:
        r=urlopen(Request(base+'/robots.txt',headers={'User-Agent':ua}),timeout=5)
        text=r.read(200_000).decode(errors='ignore')
    except Exception: return True  # no robots.txt or unreachable -- default allow
    active=False; disallowed=[]
    for line in text.splitlines():
        s=line.split('#',1)[0].strip()
        if not s or ':' not in s: continue
        k,v=[x.strip() for x in s.split(':',1)]; low=k.lower()
        if low=='user-agent': active=(v=='*')
        elif low=='disallow' and active and v: disallowed.append(v)
    return not any(path.startswith(d) for d in disallowed)

def fetch(url,ua):
    u=urlparse(url)
    if u.scheme not in ('http','https'): raise SSRFBlocked(f'Refusing non-http(s) scheme: {u.scheme}')
    _resolve_and_guard(u.hostname)
    if not _robots_allows(f'{u.scheme}://{u.netloc}',u.path or '/',ua): raise SSRFBlocked(f'robots.txt disallows {ua} on {u.path}')
    elapsed=time.time()-_last_fetch[0]
    if elapsed<MIN_INTERVAL: time.sleep(MIN_INTERVAL-elapsed)
    req=Request(url,headers={'User-Agent':ua})
    with urlopen(req,timeout=15) as r:
        body=r.read(MAX_BYTES+1)
    _last_fetch[0]=time.time()
    if len(body)>MAX_BYTES: raise SSRFBlocked(f'Response exceeded the {MAX_BYTES}-byte cap; refusing to process further.')
    return body.decode(errors='ignore')

def structural_summary(html,url):
    title=re.search(r'<title[^>]*>(.*?)</title>',html,re.I|re.S)
    title_text=(title.group(1).strip() if title else None)
    headings=[(m.group(1),re.sub('<[^>]+>','',m.group(2)).strip()[:80]) for m in re.finditer(r'<h([1-6])[^>]*>(.*?)</h\1>',html,re.I|re.S)]
    schema_types=sorted(set(re.findall(r'"@type"\s*:\s*"([^"\n]+)',html)))
    canon=re.search(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',html,re.I)
    hreflangs=sorted(set(re.findall(r'hreflang=["\']([^"\']+)',html,re.I)))
    words=len(re.sub(r'<[^>]+>',' ',html).split())
    has_faq='faq' in html.lower() or '"@type":"FAQPage"'.lower() in html.lower().replace(' ','')
    has_table=bool(re.search(r'<table\b',html,re.I))
    author=bool(re.search(r'"author"\s*:|rel=["\']author["\']|class=["\'][^"\']*author',html,re.I))
    date_signal=bool(re.search(r'"datePublished"|"dateModified"|<time\b',html,re.I))
    internal_links=len(re.findall(r'href=["\']/(?!/)',html))
    # bodyContentHash is a hash only -- the actual body text is never included in the summary or
    # written to disk, per the "never store competitor body text" rule.
    body_hash=hashlib.sha256(re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',html)).encode()).hexdigest()[:16]
    return {'url':url,'titleLength':len(title_text) if title_text else 0,'headingOutline':headings[:30],
            'schemaTypes':schema_types,'canonical':canon.group(1) if canon else None,'hreflangs':hreflangs,
            'wordCount':words,'hasFAQ':has_faq,'hasTable':has_table,'hasAuthorSignal':author,'hasDateSignal':date_signal,
            'internalLinkCount':internal_links,'bodyContentHash':body_hash}

def main():
    q=argparse.ArgumentParser()
    q.add_argument('urls',nargs='*',help='public competitor URL(s) named by the user')
    q.add_argument('--from-file',action='append',default=[],help='local HTML file(s) instead of fetching, as url=path pairs')
    q.add_argument('--your-page',help='local HTML file for your own page, to compare against')
    q.add_argument('--out',help='project root to write .claude/seo/competitors/<host>/<date>.json into')
    q.add_argument('--user-agent',default='seo-architect-competitor-diff/1.0 (+static structural check; contact via site owner)')
    a=q.parse_args()
    summaries=[]; errors=[]
    for pair in a.from_file:
        url,_,path=pair.partition('=')
        try: summaries.append(structural_summary(Path(path).read_text(errors='ignore'),url))
        except OSError as e: errors.append({'url':url,'error':str(e)})
    for url in a.urls:
        try: summaries.append(structural_summary(fetch(url,a.user_agent),url))
        except SSRFBlocked as e: errors.append({'url':url,'error':str(e),'blocked':True})
        except Exception as e: errors.append({'url':url,'error':str(e)})
    your=None
    if a.your_page: your=structural_summary(Path(a.your_page).read_text(errors='ignore'),'(your page)')
    out={'tool':'competitor-diff','yourPage':your,'competitors':summaries,'errors':errors,
         'notes':['Structural differences only -- this is not evidence of why any page ranks, and this tool has no ranking data. Body text is never stored, only a content hash. Rank/traffic data must come from the user, a dated WebSearch observation, or a connected rank-tracking import.']}
    if a.out:
        from datetime import date
        from urllib.parse import urlparse as _up
        root=Path(a.out)
        for s in summaries:
            host=_up(s['url']).netloc or 'local'
            d=root/'.claude/seo/competitors'/host; d.mkdir(parents=True,exist_ok=True)
            (d/f'{date.today()}.json').write_text(json.dumps(s,indent=2))
    print(json.dumps(out,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
