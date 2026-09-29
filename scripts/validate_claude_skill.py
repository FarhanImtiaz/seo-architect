#!/usr/bin/env python3
"""Validate Claude Code extensions that generic Agent Skills validators omit."""
import json,re,sys
from datetime import date
from pathlib import Path
def main():
 root=Path(sys.argv[1] if len(sys.argv)>1 else '.'); skill=root/'SKILL.md'; text=skill.read_text()
 match=re.match(r'^---\n(.*?)\n---',text,re.S)
 if not match: print('ERROR: missing frontmatter');return 2
 front=match.group(1); errors=[]
 if 'hooks:' not in front: errors.append('Guardian hook missing')
 if 'PreToolUse:' not in front or 'Write|Edit' not in front: errors.append('Guardian must inspect Write|Edit')
 if 'guardian_hook.py' not in front: errors.append('Guardian command missing')
 if '${CLAUDE_SKILL_DIR}' in front: errors.append('Guardian command uses ${CLAUDE_SKILL_DIR}, which Claude Code does not expand in hook commands')
 if '|| true' not in front and '|| exit 0' not in front: errors.append('Guardian command is not fail-open (must tolerate script/path failure without blocking tools)')
 if '2>/dev/null' in front: errors.append('Guardian command redirects stderr to /dev/null, which silently swallows a missing/broken script path instead of surfacing it')
 if not (root/'scripts/guardian_hook.py').exists(): errors.append('guardian_hook.py missing')
 rubric_path=root/'scripts/rubric.json'
 if rubric_path.exists():
  rubric_version=json.loads(rubric_path.read_text()).get('version')
  changelog_path=root/'CHANGELOG.md'
  if not changelog_path.exists(): errors.append('CHANGELOG.md is missing; document the rubric version there when it changes')
  else:
   changelog=changelog_path.read_text()
   if not re.search(rf'rubric version:?\s*{re.escape(str(rubric_version))}\b',changelog,re.I): errors.append(f'CHANGELOG.md does not document rubric.json version {rubric_version}; add/update a "Rubric version: {rubric_version}" line when the rubric changes')
 for md in [root/'SKILL.md',*sorted((root/'workflows').glob('*.md'))]:
  body=md.read_text()
  for link_target in re.findall(r'\]\(((?!https?://)[^)]+)\)',body):
   target=link_target.split('#',1)[0]
   if target and not (md.parent/target).resolve().exists(): errors.append(f'{md.relative_to(root)}: broken relative link "{link_target}"')
 patterns_md=root/'references/winning-patterns.md'
 known_ids=set(re.findall(r'^##\s*(P\d\d[a-z]?)\.',patterns_md.read_text(),re.M)) if patterns_md.exists() else set()
 for wf in sorted((root/'workflows').glob('*.md')):
  for pid in re.findall(r'\bP\d\d[a-z]?\b',wf.read_text()):
   if pid not in known_ids: errors.append(f'{wf.relative_to(root)}: references unknown pattern id {pid} (not in references/winning-patterns.md)')
 print('Claude Code extension validation: '+('PASS' if not errors else 'FAIL'))
 for x in errors: print('- '+x)
 return 1 if errors else 0
if __name__=='__main__':raise SystemExit(main())
