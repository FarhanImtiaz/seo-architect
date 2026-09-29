# Install SEO Architect for Claude Code

From this repository, install globally:

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/seo-architect" ~/.claude/skills/seo-architect
```

Or install in one client repository:

```bash
mkdir -p /path/to/client/.claude/skills
cp -R "$(pwd)/seo-architect" /path/to/client/.claude/skills/seo-architect
cd /path/to/client
claude
```

Use `/seo-architect setup` first, then `/seo-architect audit`. This package uses Claude Code skill hooks for the in-session Guardian; use a current Claude Code release that supports the `hooks` SKILL.md frontmatter field. Existing sessions detect `SKILL.md` changes in already-watched skill directories; restart if the top-level skill directory was created after the session started.

The Guardian hook command checks for a project-local install first
(`$CLAUDE_PROJECT_DIR/.claude/skills/seo-architect/scripts/guardian_hook.py`), then falls back to a
global install (`$HOME/.claude/skills/seo-architect/scripts/guardian_hook.py`). Either install
method above works with no extra configuration. If neither path resolves, the hook prints a
visible warning to stderr and allows the edit unreviewed — it never blocks a `Write`/`Edit` call on
its own path failure, only on an actual review-worthy finding.

See [CHANGELOG.md](CHANGELOG.md) for what's currently implemented.
