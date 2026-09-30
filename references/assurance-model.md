# Assurance model

Use four evidence labels: **observed** (source, tool output, or dated first-party data), **inference** (reasoned from observations), **hypothesis** (requires validation), and **unavailable**. Never render an inference as a fact.

Static checks prove only source-level properties. Framework adapters increase coverage but cannot prove deployed responses. A rendered check can prove one fetched build at one time, not indexing, rankings, rich-result eligibility, citations, or traffic. Use live Search Console/analytics only as dated evidence.

The Guardian hook is session-scoped after this skill is invoked. It requests review for likely indexation, redirect, canonical, sitemap, or unsupported schema changes. It is not a substitute for code review or production monitoring. This scope is the top-level interactive session only — a Task/Agent-tool subagent's isolated context does not inherit it, and invoking the skill from inside a subagent does not register it there either (confirmed by direct testing, not assumed). Treat any SEO-sensitive edit made by a subagent as unreviewed until a human or the top-level session checks it.
