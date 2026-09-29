#!/usr/bin/env python3
"""Assembles a Claude Code PLUGIN-shaped distribution from this repo's standalone-skill layout
(SKILL.md/scripts/workflows/etc. at the repo root -- the layout INSTALL.md's standard install
uses and this script never changes). Output: <out>/.claude-plugin/plugin.json,
<out>/hooks/hooks.json, and <out>/skills/seo-architect/<everything else>. The standalone-skill
install path (symlink or copy of the repo root into ~/.claude/skills/) is unaffected by this
script and remains the default, documented way to install."""
import shutil,sys
from pathlib import Path

HERE=Path(__file__).resolve().parent.parent
SKIP={'.git','.claude','.github','dist','__pycache__','node_modules','.claude-plugin','hooks'}

def main():
    out=Path(sys.argv[1] if len(sys.argv)>1 else 'dist').resolve()
    if out.exists(): shutil.rmtree(out)
    skill_dir=out/'skills/seo-architect'; skill_dir.mkdir(parents=True)
    for item in HERE.iterdir():
        if item.name in SKIP or item.name=='dist': continue
        dest=skill_dir/item.name
        if item.is_dir(): shutil.copytree(item,dest)
        else: shutil.copy2(item,dest)
    shutil.copytree(HERE/'.claude-plugin',out/'.claude-plugin')
    shutil.copytree(HERE/'hooks',out/'hooks')
    print(f'Plugin-shaped distribution written to {out}')
    return 0
if __name__=='__main__': raise SystemExit(main())
