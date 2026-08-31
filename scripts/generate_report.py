#!/usr/bin/env python3
from pathlib import Path
import json,sys
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve(); audit=root/'.claude/seo/audit.md'
if not audit.exists(): print('ERROR: run setup/audit or create .claude/seo/audit.md first.',file=sys.stderr);raise SystemExit(2)
print('# SEO Architect report\n\n## Latest audit\n\n'+audit.read_text())
