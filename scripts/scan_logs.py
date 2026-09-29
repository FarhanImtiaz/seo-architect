#!/usr/bin/env python3
"""Crawl-budget analysis from a USER-SUPPLIED access log (never fetched by this script). A
user-agent string alone is a claim, not proof -- a hit is only "verified" as a given bot when its
source IP is checked against that vendor's published IP ranges via --ranges (offline CIDR match,
no network call here). Without --ranges, every hit is "ua-claimed" only. Raw IPs are never
persisted: they are truncated (IPv4: last octet zeroed; IPv6: last 80 bits zeroed) before any
aggregate is written out, and the full raw log is never copied or stored."""
import argparse,ipaddress,json,re,sys
from collections import Counter,defaultdict
from pathlib import Path

BOTS={'Googlebot':'googlebot','Bingbot':'bingbot','GPTBot':'gptbot','OAI-SearchBot':'oai-searchbot',
      'ChatGPT-User':'chatgpt-user','ClaudeBot':'claudebot','Claude-SearchBot':'claude-searchbot',
      'Claude-User':'claude-user','PerplexityBot':'perplexitybot','Applebot':'applebot','CCBot':'ccbot'}
# Google-Extended is a robots.txt opt-out token only -- it is never a User-Agent string that
# appears in access logs, so it is deliberately absent from BOTS above.

COMBINED_RE=re.compile(r'^(?P<ip>\S+)\s+\S+\s+\S+\s+\[(?P<time>[^\]]+)\]\s+"(?P<request>[^"]*)"\s+(?P<status>\d{3})\s+(?P<size>\S+)(?:\s+"(?P<referrer>[^"]*)"\s+"(?P<ua>[^"]*)")?')

def truncate_ip(ip):
    try:
        addr=ipaddress.ip_address(ip)
        if addr.version==4:
            parts=ip.split('.'); return '.'.join(parts[:3]+['0'])
        net=ipaddress.ip_network(f'{ip}/48',strict=False); return str(net.network_address)
    except ValueError: return 'unparseable'

def parse_line(line):
    m=COMBINED_RE.match(line)
    if not m: return None
    d=m.groupdict()
    parts=d['request'].split(' ')
    path=parts[1] if len(parts)>=2 else d['request']
    return {'ip':d['ip'],'path':path,'status':d['status'],'ua':d.get('ua') or ''}
def parse_jsonl(line):
    try: row=json.loads(line)
    except json.JSONDecodeError: return None
    ip=row.get('clientIP') or row.get('ip') or row.get('client_ip')
    ua=row.get('userAgent') or row.get('ua') or ''
    path=(row.get('uri') or row.get('path') or row.get('url') or '')
    status=str(row.get('status') or row.get('edgeResponseStatus') or '')
    if not ip: return None
    return {'ip':ip,'path':path,'status':status,'ua':ua}

def load_ranges(paths):
    nets=[]
    for pth in paths or []:
        try: data=json.loads(Path(pth).read_text())
        except (json.JSONDecodeError,OSError): continue
        prefixes=data.get('prefixes',data if isinstance(data,list) else [])
        for entry in prefixes:
            cidr=entry.get('ipv4Prefix') or entry.get('ipv6Prefix') or entry.get('prefix') if isinstance(entry,dict) else entry
            if cidr:
                try: nets.append(ipaddress.ip_network(cidr))
                except ValueError: pass
    return nets

def verify(ip,nets):
    if not nets: return None
    try: addr=ipaddress.ip_address(ip)
    except ValueError: return False
    return any(addr in n for n in nets)

def bot_of(ua):
    for name,key in BOTS.items():
        if name.lower() in ua.lower(): return name
    return None

def main():
    q=argparse.ArgumentParser()
    q.add_argument('logfile'); q.add_argument('--format',choices=['combined','jsonl'],default='combined')
    q.add_argument('--ranges',action='append',default=[],help='JSON file(s) of a bot vendor\'s published IP ranges, for offline CIDR verification')
    q.add_argument('--sitemap',help='sitemap.xml to cross-check for zero-verified-hit URLs')
    a=q.parse_args()
    nets=load_ranges(a.ranges)
    hits=[]
    lines=Path(a.logfile).read_text(errors='ignore').splitlines()
    parser=parse_jsonl if a.format=='jsonl' else parse_line
    for line in lines:
        row=parser(line)
        if row: hits.append(row)
    bot_hits=[]
    for row in hits:
        b=bot_of(row['ua'])
        if not b: continue
        v=verify(row['ip'],nets)
        bot_hits.append({'bot':b,'ip_truncated':truncate_ip(row['ip']),'path':row['path'].split('?',1)[0],'status':row['status'],'verified':v})
    by_bot_status=defaultdict(Counter)
    for h in bot_hits: by_bot_status[h['bot']][f"{h['status']}:{'verified' if h['verified'] else ('unverified' if h['verified'] is False else 'ua-claimed')}"]+=1
    param_urls=Counter(row['path'] for row in hits if '?' in row['path'])
    not_found=Counter(row['path'].split('?',1)[0] for row in hits if row['status']=='404')
    redirects=Counter(row['path'].split('?',1)[0] for row in hits if row['status'].startswith('3'))
    ai_blocked=[h for h in bot_hits if h['bot'] in ('GPTBot','OAI-SearchBot','ChatGPT-User','ClaudeBot','Claude-SearchBot','Claude-User','PerplexityBot') and h['status'] in ('403','429')]
    fs=[]
    if not nets and bot_hits: fs.append({'severity':'INFO','issue':f'No --ranges given; all {len(bot_hits)} bot-labeled hit(s) are "ua-claimed" only (a user agent string is not proof of identity).'})
    spoofed=[h for h in bot_hits if h['verified'] is False]
    if spoofed: fs.append({'severity':'MEDIUM','issue':f'{len(spoofed)} hit(s) claim a known bot user-agent but come from an IP outside that vendor\'s published ranges (spoofed or stale range list).'})
    if ai_blocked: fs.append({'severity':'LOW','issue':f'{len(ai_blocked)} AI-crawler hit(s) got 403/429 -- possible WAF/firewall blocking not visible in robots.txt.'})
    zero_hit_sitemap_urls=[]
    if a.sitemap and Path(a.sitemap).exists():
        import xml.etree.ElementTree as ET
        try:
            tree=ET.parse(a.sitemap); urls=[n.text.strip() for n in tree.findall('.//{*}loc') if n.text]
            from urllib.parse import urlparse as _up
            hit_paths={h['path'] for h in bot_hits if h['bot']=='Googlebot' and h['verified']}
            zero_hit_sitemap_urls=[u for u in urls if _up(u).path not in hit_paths]
            if zero_hit_sitemap_urls: fs.append({'severity':'LOW','issue':f'{len(zero_hit_sitemap_urls)} sitemap URL(s) have zero verified Googlebot hits in this log window.'})
        except ET.ParseError: pass
    out={'tool':'scan-logs','findings':fs,
         'summary':{'totalLines':len(lines),'parsedLines':len(hits),'botHits':len(bot_hits),
                     'byBotStatus':{b:dict(c) for b,c in by_bot_status.items()},
                     'topParamUrls':param_urls.most_common(10),'top404s':not_found.most_common(10),'topRedirectedUrls':redirects.most_common(10)},
         'notes':['IPs are truncated before any aggregate here; the raw log is never copied into project state.']}
    print(json.dumps(out,indent=2))
    return 1 if spoofed else 0
if __name__=='__main__': raise SystemExit(main())
