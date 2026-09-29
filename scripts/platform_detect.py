#!/usr/bin/env python3
"""Detects which non-framework-code platforms (SSG frontmatter, headless CMS, Webflow, Shopify,
WordPress) are present and runs each detected platform's static scan. Every platform's
`unavailable[]` list is preserved in the output unchanged -- score.py uses it to lower
coveragePct rather than silently treating unscannable content as "fine"."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from platforms import ssg_frontmatter,headless_cms,webflow,shopify,wordpress

MODULES={'ssg-frontmatter':ssg_frontmatter,'headless-cms':headless_cms,'webflow':webflow,'shopify':shopify,'wordpress':wordpress}

def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
    if not root.is_dir(): print(f'ERROR: project directory does not exist: {root}',file=sys.stderr); return 2
    detected=[name for name,mod in MODULES.items() if mod.detect(root)]
    results={}; all_findings=[]
    for name in detected:
        r=MODULES[name].scan(root); results[name]=r; all_findings+=r['findings']
    out={'tool':'platform-detect','detected':detected,'platforms':results,
         'findings':all_findings,
         'notes':[f'Detected platform(s): {", ".join(detected) if detected else "none (framework-code adapters in framework_adapters.py cover this project instead)"}.']}
    print(json.dumps(out,indent=2))
    return 1 if any(f['severity'] in ('CRITICAL','HIGH') for f in all_findings) else 0
if __name__=='__main__': raise SystemExit(main())
