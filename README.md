# SEO Architect

A Claude Code skill for technical SEO and AEO (answer-engine) engineering: auditing, planning, implementing, and validating search visibility across a codebase.

It is built around one constraint: **it never fabricates a ranking, a traffic number, a result, a client, a review, or a citation.** Every finding traces to something observed in your source code, a named and cited external source, or data you explicitly imported. When it doesn't have evidence, it says so instead of guessing.

## Why this, and not another SEO tool

- **A reproducible score, not a vibe.** The 100-point audit score is computed by `scripts/score.py` from a versioned, documented rubric — the same site produces the same score every time, and any category with no evidence is excluded from the denominator rather than silently scored zero.
- **A safety net while Claude edits your code.** A `PreToolUse` hook inspects every `Write`/`Edit` call in-session and requires review before changes to routing, canonicalization, redirects, robots directives, or structured-data claims — while staying invisible for ordinary component and style work.
- **Recommendations cite real sources.** The winning-patterns library (`references/winning-patterns.md`) ties 16 pattern cards to 34 named, dated sources — Google's own documentation, published case studies from companies like Pinterest and Etsy, practitioner methodologies — with a validator that mechanically rejects unhedged promises ("will rank #1") and numbers borrowed from someone else's site.
- **It can tell you whether a change actually worked.** Register a change before you deploy it, import real Search Console/Analytics/CrUX data afterward, and `scripts/impact.py` returns one of a small set of honest verdicts — consistent with your hypothesis, no detectable change, confounded by something else that happened in the same window, or not enough data yet. It never claims causation it hasn't earned.

## Install

See [INSTALL.md](INSTALL.md) for the full walkthrough. In short:

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/seo-architect" ~/.claude/skills/seo-architect
```

## Quickstart

```
/seo-architect setup
/seo-architect audit
```

`setup` scaffolds project state under `.claude/seo/` (no credentials, ever). `audit` runs the full static analysis pass — routes, metadata, sitemap, robots, structured data, internal links, images, framework-specific checks — and reports a scored, evidence-labeled result.

## What it does

| Area | What you get |
|---|---|
| **Audit & scoring** | A reproducible 100-point score across technical, IA, on-page, content, links, schema, performance, local, and AEO categories, with per-check evidence and coverage reporting. |
| **Guardian hook** | Live review-gating on risky edits (canonicalization, redirects, robots, schema claims) — safe, ordinary edits pass through untouched. |
| **Structured data** | Per-schema-type validation against Google's required/recommended properties, plus a check that schema claims (price, rating) actually match the page's visible content. |
| **Links & images** | An internal link graph (orphan pages, click depth, generic anchors) and image SEO scanning (alt text, layout-shift risk, oversized files). |
| **Framework-aware metadata** | Real extraction across Next.js (App & Pages Router), Nuxt, SvelteKit, Astro, Remix, and Vue/Helmet — not regex guessing. |
| **hreflang / i18n** | Validation of locale alternates, reciprocity, and `x-default`. |
| **Winning patterns** | Cited, source-checked recommendations tied to your project's detected signals — never generic advice. |
| **Live measurement** | Mark a change, import real analytics data later, get an honest verdict on whether it moved anything. |
| **Optional live data** | Opt-in Search Console / Analytics / PageSpeed Insights / CrUX integration — never required, never automatic. |

## What this deliberately does not do

- No rank tracking, keyword-volume data, or SERP scraping.
- No fabricated case studies or invented statistics — every external claim in `references/winning-patterns.md` is cited to a real, named source.
- No guaranteed results, forecasts, or "#1 on Google" language, from the skill or about the skill.
- No automatic or unattended data pulls — live data import is always something you explicitly ask for.
- No composite "AI visibility score" or similar unfalsifiable metric.

## Test

```bash
python3 tests/run_tests.py
python3 scripts/validate_claude_skill.py .
python3 scripts/validate_sources.py .
```

Scripts are dependency-free Python 3 standard library, run entirely offline by default, and report unsupported inspection explicitly rather than treating it as a pass.

## More

- [INSTALL.md](INSTALL.md) — installation and Guardian hook setup
- [SKILL.md](SKILL.md) — full operating contract, command routing, and script reference
- [CHANGELOG.md](CHANGELOG.md) — what's changed, in order
- [examples/worked-example-nextjs](examples/worked-example-nextjs) — a worked before/after audit on a small fixture project

## License

MIT — see [LICENSE](LICENSE).
