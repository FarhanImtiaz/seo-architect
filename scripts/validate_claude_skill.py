#!/usr/bin/env python3
"""Validate Claude Code extensions that generic Agent Skills validators omit."""
import re,sys
from pathlib import Path
def main():
 root=Path(sys.argv[1] if len(sys.argv)>1 else '.'); skill=root/'SKILL.md'; text=skill.read_text()
 match=re.match(r'^---\n(.*?)\n---',text,re.S)
 if not match: print('ERROR: missing frontmatter');return 2
 front=match.group(1); errors=[]
 if 'hooks:' not in front: errors.append('Guardian hook missing')
 if 'PreToolUse:' not in front or 'Write|Edit' not in front: errors.append('Guardian must inspect Write|Edit')
 if 'guardian_hook.py' not in front: errors.append('Guardian command missing')
 if not (root/'scripts/guardian_hook.py').exists(): errors.append('guardian_hook.py missing')
 print('Claude Code extension validation: '+('PASS' if not errors else 'FAIL'))
 for x in errors: print('- '+x)
 return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())
