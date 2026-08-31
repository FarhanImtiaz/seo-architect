#!/usr/bin/env python3
"""Check a supplied page brief against evidence-gated page-type requirements."""
import argparse,json,sys
REQUIRED={
 'service':['intent','audience','title','h1','description','cta','internalLinks','evidence'],
 'article':['intent','audience','title','h1','outline','authorOrOrganization','internalLinks','evidence'],
 'product':['intent','title','h1','description','priceOrPricePolicy','availabilityPolicy','evidence'],
 'location':['intent','locationEvidence','serviceAvailability','localDifferentiation','evidence'],
 'pricing':['intent','title','h1','pricingDefinitions','conditions','evidence']}
def main():
 p=argparse.ArgumentParser();p.add_argument('type',choices=REQUIRED);p.add_argument('--brief');a=p.parse_args()
 if not a.brief: print(json.dumps({'type':a.type,'required':REQUIRED[a.type],'result':'template'},indent=2));return 0
 try: data=json.loads(open(a.brief).read())
 except (OSError,json.JSONDecodeError) as e: print('ERROR:',e,file=sys.stderr);return 2
 missing=[x for x in REQUIRED[a.type] if not data.get(x)]
 print(json.dumps({'type':a.type,'missing':missing,'result':'pass' if not missing else 'review'},indent=2));return 1 if missing else 0
if __name__=='__main__': raise SystemExit(main())
