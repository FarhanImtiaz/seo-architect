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

Use `/seo-architect setup` first, then `/seo-architect audit`. This v1.1 package uses Claude Code skill hooks for the in-session Guardian; use a current Claude Code release that supports the `hooks` SKILL.md frontmatter field. Existing sessions detect `SKILL.md` changes in already-watched skill directories; restart if the top-level skill directory was created after the session started.
