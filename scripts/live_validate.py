#!/usr/bin/env python3
"""Optional rendered-page validator. Uses only Python stdlib against a running URL."""
import argparse,json,sys
from html.parser import HTMLParser
from urllib.request import Request,urlopen
class Page(HTMLParser):
 def __init__(self): super().__init__();self.title='';self.h1=0;self.canon=[];self.desc=[];self.jsonld=0;self._title=False
 def handle_starttag(self,t,a):
  d=dict(a)
  if t=='title':self._title=True
  if t=='h1':self.h1+=1
  if t=='link' and d.get('rel')=='canonical':self.canon.append(d.get('href'))
  if t=='meta' and d.get('name','').lower()=='description':self.desc.append(d.get('content'))
  if t=='script' and d.get('type')=='application/ld+json':self.jsonld+=1
 def handle_endtag(self,t):
  if t=='title':self._title=False
 def handle_data(self,d):
  if self._title:self.title+=d
def main():
 q=argparse.ArgumentParser();q.add_argument('url');q.add_argument('--timeout',type=int,default=15);a=q.parse_args()
 try:
  with urlopen(Request(a.url,headers={'User-Agent':'SEO-Architect-Validator/1.1'}),timeout=a.timeout) as r: body=r.read().decode(r.headers.get_content_charset() or 'utf-8','replace');status=r.status;final=r.url
 except Exception as e:print('ERROR: rendered request failed:',e,file=sys.stderr);return 2
 p=Page();p.feed(body); findings=[]
 if not p.title.strip():findings.append('missing rendered title')
 if p.h1!=1:findings.append('rendered H1 count is not one')
 if not p.canon:findings.append('missing rendered canonical')
 print(json.dumps({'url':a.url,'finalUrl':final,'status':status,'title':p.title.strip(),'h1Count':p.h1,'canonical':p.canon,'descriptionPresent':bool(p.desc),'jsonldBlocks':p.jsonld,'findings':findings,'limit':'This validates one fetched response, not indexation, ranking, or JavaScript execution beyond server output.'},indent=2));return 1 if status>=400 else 0
if __name__=='__main__':raise SystemExit(main())
