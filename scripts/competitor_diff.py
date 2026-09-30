#!/usr/bin/env python3
"""Structural diff against a user-named PUBLIC competitor page: title length, heading outline,
schema types, word count, FAQ/table/comparison presence, author/date signals, canonical,
hreflang, internal-link count. Output is framed as "structural differences vs. your page",
explicitly NEVER "why they rank" -- this tool has no ranking data and must never imply it does.
Body text is never stored, only hashes/outlines. Actual rank data must come from the user, a
dated WebSearch observation, or a connected rank-tracking import -- never invented here."""
import argparse,hashlib,http.client,ipaddress,json,re,socket,ssl,sys,time
from pathlib import Path
from urllib.parse import urlparse,urljoin

MAX_BYTES=3*1024*1024
MIN_INTERVAL=2.0
MAX_REDIRECTS=5
_last_fetch=[0.0]

class SSRFBlocked(Exception): pass

def _guarded_ip(host):
    """Resolves host and refuses it if ANY address it resolves to is non-global (private,
    loopback, link-local, reserved, multicast, CGNAT, etc. -- `is_global` is the correct inverse
    of "safe to fetch", not an allowlist of specific ranges, which is how 100.64.0.0/10 (CGNAT/
    Tailscale) previously slipped through). Returns ONE validated IP: the guard and the actual
    TCP connection MUST use the same IP the check ran against, never a fresh DNS lookup -- urlopen
    re-resolving the hostname itself is exactly the DNS-rebinding TOCTOU this replaces."""
    try: infos=socket.getaddrinfo(host,None)
    except socket.gaierror as e: raise SSRFBlocked(f'DNS resolution failed for {host}: {e}')
    ips=[]
    for info in infos:
        ip=info[4][0]
        addr=ipaddress.ip_address(ip)
        if not addr.is_global:
            raise SSRFBlocked(f'{host} resolves to {ip}, a non-global (private/loopback/link-local/reserved/CGNAT) address; refusing to fetch it.')
        ips.append(ip)
    if not ips: raise SSRFBlocked(f'DNS resolution for {host} returned no usable addresses.')
    return ips[0]

class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connects to a pre-validated IP (self.host) but presents the real hostname for SNI and
    certificate validation (self._sni_host) -- so a normal cert on the real hostname still
    verifies correctly even though the TCP connection goes to the IP the guard already checked,
    not to whatever a second DNS lookup might return."""
    def __init__(self,ip,sni_host,port,timeout,context):
        super().__init__(ip,port,timeout=timeout,context=context)
        self._sni_host=sni_host
    def connect(self):
        sock=socket.create_connection((self.host,self.port),self.timeout)
        self.sock=self._context.wrap_socket(sock,server_hostname=self._sni_host)

def _one_hop(url,ua,timeout,max_bytes):
    """Performs exactly one HTTP request against a URL whose host has just been guarded, using
    the SAME resolved IP the guard checked (never delegating resolution/connection to
    urllib.request.urlopen, which would re-resolve the hostname and reopen the rebinding gap).
    Returns (status, headers, body); does NOT follow redirects -- the caller re-guards each hop."""
    u=urlparse(url)
    if u.scheme not in ('http','https'): raise SSRFBlocked(f'Refusing non-http(s) scheme: {u.scheme}')
    if not u.hostname: raise SSRFBlocked('URL has no hostname.')
    ip=_guarded_ip(u.hostname)
    port=u.port or (443 if u.scheme=='https' else 80)
    path=(u.path or '/')+(('?'+u.query) if u.query else '')
    headers={'User-Agent':ua,'Host':u.hostname}
    if u.scheme=='https':
        conn=_PinnedHTTPSConnection(ip,u.hostname,port,timeout,ssl.create_default_context())
    else:
        conn=http.client.HTTPConnection(ip,port,timeout=timeout)
    try:
        conn.request('GET',path,headers=headers)
        resp=conn.getresponse()
        body=resp.read(max_bytes+1)
        loc=resp.getheader('Location')
        status=resp.status
    finally:
        conn.close()
    if len(body)>max_bytes: raise SSRFBlocked(f'Response exceeded the {max_bytes}-byte cap; refusing to process further.')
    return status,loc,body

def _guarded_get(url,ua,timeout=15,max_bytes=MAX_BYTES,max_redirects=MAX_REDIRECTS):
    """Fetches a URL, re-guarding and re-resolving every redirect hop before following it -- a
    302 from an allowed public host to a private/internal target is refused at the hop that
    reveals it, not silently followed the way urlopen's default redirect handler would."""
    for _ in range(max_redirects+1):
        status,loc,body=_one_hop(url,ua,timeout,max_bytes)
        if status in (301,302,303,307,308) and loc:
            url=urljoin(url,loc)
            continue
        return body.decode(errors='ignore')
    raise SSRFBlocked(f'Too many redirects (>{max_redirects}) while fetching; refusing to follow further.')

def _robots_allows(base,path,ua):
    try: text=_guarded_get(base+'/robots.txt',ua,timeout=5,max_bytes=200_000)
    except SSRFBlocked: raise
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
    if not _robots_allows(f'{u.scheme}://{u.netloc}',u.path or '/',ua): raise SSRFBlocked(f'robots.txt disallows {ua} on {u.path}')
    elapsed=time.time()-_last_fetch[0]
    if elapsed<MIN_INTERVAL: time.sleep(MIN_INTERVAL-elapsed)
    body=_guarded_get(url,ua,timeout=15)
    _last_fetch[0]=time.time()
    return body

def _visible_text(html):
    """Strips <script>/<style> element CONTENT (not just tags) before counting words or hashing
    body text -- otherwise wordCount/bodyContentHash reflect JS/CSS source, not the page's actual
    visible content, and can wildly overcount (confirmed: 19 counted vs. 3 visible words)."""
    stripped=re.sub(r'<(script|style)\b[^>]*>.*?</\1>',' ',html,flags=re.I|re.S)
    return re.sub(r'<[^>]+>',' ',stripped)

def structural_summary(html,url):
    title=re.search(r'<title[^>]*>(.*?)</title>',html,re.I|re.S)
    title_text=(title.group(1).strip() if title else None)
    headings=[(m.group(1),re.sub('<[^>]+>','',m.group(2)).strip()[:80]) for m in re.finditer(r'<h([1-6])[^>]*>(.*?)</h\1>',html,re.I|re.S)]
    schema_types=sorted(set(re.findall(r'"@type"\s*:\s*"([^"\n]+)',html)))
    canon=re.search(r'rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',html,re.I)
    hreflangs=sorted(set(re.findall(r'hreflang=["\']([^"\']+)',html,re.I)))
    visible=_visible_text(html)
    words=len(visible.split())
    # A bare "faq" substring matches nav links like "/faq" that aren't FAQ CONTENT -- require
    # actual FAQPage schema or a heading whose text plausibly reads as a question/FAQ label.
    has_faq=('"@type":"faqpage"' in html.lower().replace(' ','')
              or any(re.search(r'\b(faq|frequently asked questions)\b',h[1],re.I) for h in headings))
    has_table=bool(re.search(r'<table\b',html,re.I))
    # A class containing "author" anywhere (e.g. "co-author-widget", "authoritative") is too loose
    # -- require a structured author signal: JSON-LD "author", rel=author, an itemprop=author, or
    # a class token that IS "author"/"byline", not merely contains the substring.
    author=bool(re.search(r'"author"\s*:|rel=["\']author["\']|itemprop=["\']author["\']|class=["\'][^"\']*\b(author|byline)\b[^"\']*["\']',html,re.I))
    date_signal=bool(re.search(r'"datePublished"|"dateModified"|<time\b',html,re.I))
    internal_links=len(re.findall(r'href=["\']/(?!/)',html))
    # bodyContentHash is a hash only -- the actual body text is never included in the summary or
    # written to disk, per the "never store competitor body text" rule.
    body_hash=hashlib.sha256(re.sub(r'\s+',' ',visible).encode()).hexdigest()[:16]
    return {'url':url,'titleLength':len(title_text) if title_text else 0,'headingOutline':headings[:30],
            'schemaTypes':schema_types,'canonical':canon.group(1) if canon else None,'hreflangs':hreflangs,
            'wordCount':words,'hasFAQ':has_faq,'hasTable':has_table,'hasAuthorSignal':author,'hasDateSignal':date_signal,
            'internalLinkCount':internal_links,'bodyContentHash':body_hash}

def _safe_host_dir(host):
    """A URL host of '..' (or containing a path separator) could otherwise write the output file
    one level outside .claude/seo/competitors/ -- reject anything that isn't a plausible hostname
    rather than trusting it as a path segment."""
    host=host or 'local'
    if not re.match(r'^[A-Za-z0-9](?:[A-Za-z0-9.\-]*[A-Za-z0-9])?(?::\d+)?$',host) or '..' in host:
        return hashlib.sha256(host.encode()).hexdigest()[:16]
    return host

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
            host=_safe_host_dir(_up(s['url']).netloc)
            d=root/'.claude/seo/competitors'/host; d.mkdir(parents=True,exist_ok=True)
            (d/f'{date.today()}.json').write_text(json.dumps(s,indent=2))
    print(json.dumps(out,indent=2))
    return 0
if __name__=='__main__': raise SystemExit(main())
