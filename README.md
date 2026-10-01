# SEO Architect

A Claude Code skill for technical SEO and AEO (answer-engine) engineering: auditing, planning, implementing, and validating search visibility across a codebase.

It is built around one constraint: **it never fabricates a ranking, a traffic number, a result, a client, a review, or a citation.** Every finding traces to something observed in your source code, a named and cited external source, or data you explicitly imported. When it doesn't have evidence, it says so instead of guessing.

## See it work

This is the real output from the worked example in [`examples/worked-example-nextjs`](examples/worked-example-nextjs) — a small, deliberately flawed four-page Next.js fixture, not a cherry-picked demo.

```
$ claude
> /seo-architect audit
```

```
HIGH   jsonld        /product's Product schema has none of offers/review/aggregateRating —
                      Google requires at least one for rich-result eligibility
MEDIUM metadata      /about has no statically detectable title or description
MEDIUM images        /product's <img> has no alt attribute and no width/height
MEDIUM graph         /orphan has no inbound internal links
MEDIUM state         .claude/seo/keywords.md and strategy.md are still template-stub-only

Score: 58.3/100 (internal prioritization, not a ranking prediction — evidenced coverage 71%)
```

Ask it to fix the safe ones, and rescan:

```
Score: 73.2/100 (up from 58.3)   HIGH/CRITICAL findings: 0 (down from 1)
```

Full transcript, including exactly which fixes the Guardian classified as safe-to-auto-apply vs. review-first, is in [`examples/worked-example-nextjs/walkthrough.md`](examples/worked-example-nextjs/walkthrough.md).

## Install

```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/seo-architect" ~/.claude/skills/seo-architect
```

Then, in any project: `/seo-architect setup` once, then `/seo-architect audit`. Full options (per-project install, plugin packaging) in [INSTALL.md](INSTALL.md).

## What you can ask it

| You say | It does |
|---|---|
| `/seo-architect audit` (or "run an SEO audit") | Full technical/on-page/content/schema/AEO pass, scored |
| `/seo-architect fix` | Applies only the evidenced, auto-safe findings from the last audit |
| "optimize this page" / `optimize-page` | Metadata, schema, and internal-link review for one route |
| `/seo-architect schema` | Structured-data validation + safe additions, gated on visible content |
| `/seo-architect playbook` | Shows which of 16 cited, real-world patterns (Pinterest, Etsy, HubSpot, Google's own case studies, etc.) apply to your project |
| `/seo-architect measure` | Registers a change before you deploy it, then gives an honest after-the-fact verdict from real Search Console/Analytics data — never a forecast |
| `/seo-architect ci` | Sets up a PR-time regression check (no network, no secrets required) |
| `/seo-architect report` | A plain-language summary of current state for a non-technical stakeholder |

Natural language works too — the skill routes "fix the broken canonical on /pricing" the same as the equivalent slash command. Full routing table in [SKILL.md](SKILL.md).

## What protects you while it works

A `PreToolUse` hook inspects every file edit for the rest of the session once the skill is invoked, and classifies it:

```
Editing JSON-LD to add a star rating        → STOPS for review (schema claims need evidence)
Tweaking a page's <h1> wording               → advisory note only, proceeds
Editing an unrelated component               → silent, no interruption
```

It cannot be bypassed by asking nicely — it's a hook, not an instruction the model can talk itself out of. **One real limitation, confirmed by direct testing**: this protection is scoped to the session you invoke the skill in. If you delegate SEO-sensitive edits to a Claude Code subagent, the hook does not follow it there — review that work yourself before it ships. See [references/assurance-model.md](references/assurance-model.md).

## FAQ

**Does this need API keys or internet access?** No, by default. Every audit/score/fix command runs entirely offline against your local source. Optional integrations (Search Console, Analytics, PageSpeed Insights, CrUX, Bing AI Performance) exist, but nothing calls out or asks for credentials unless you explicitly invoke them and point them at a key you provide.

**What frameworks does it actually understand?** Framework-aware metadata extraction covers Next.js (App and Pages Router), Nuxt, SvelteKit, Astro, Remix, and Vue/Helmet. Static-site generators (Hugo, Jekyll, Eleventy, Astro content, Docusaurus, Gatsby), headless CMS content models, Webflow exports, Shopify themes, and WordPress themes are covered by separate adapters with an honestly-reported coverage matrix — see [references/platform-coverage.md](references/platform-coverage.md) for exactly what's checked vs. what's structurally invisible to static analysis on each platform.

**What does the 100-point score actually mean?** It's computed by `scripts/score.py` from a versioned, documented rubric ([references/scoring-rubric.md](references/scoring-rubric.md)) — never hand-waved by the model. The same project produces the same score every run. A category with no evidence is excluded from the denominator, never silently scored zero, and the `coveragePct` next to the score tells you how much of the full rubric had evidence at all. It is explicitly **not** a Google/Bing ranking prediction — nothing in this skill can produce one honestly, and it says so every time.

**Will it make up SEO advice?** No — or rather, that's the entire design constraint. Recommendations that reference a general pattern (e.g. "add internal links to orphan pages") cite a real, named, dated external source in [references/winning-patterns.md](references/winning-patterns.md), with a validator that mechanically rejects unhedged promises and numbers borrowed from someone else's site. If it can't find evidence for a claim, it labels it a hypothesis or says it's unavailable — it does not guess.

**What if I disagree with a Guardian decision?** The hook only ever asks for review or adds advisory context — it never silently blocks a legitimate edit. If it's wrong about something being sensitive, you can proceed past the review prompt; the point is forcing a second look before a search-sensitive claim or structural change ships unreviewed, not removing your judgment.

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

- [INSTALL.md](INSTALL.md) — installation, plugin packaging, and Guardian hook setup
- [SKILL.md](SKILL.md) — full operating contract, command routing, and script reference (what the model itself reads)
- [CHANGELOG.md](CHANGELOG.md) — what's changed, in order
- [examples/worked-example-nextjs](examples/worked-example-nextjs) — the full before/after walkthrough behind the numbers above
- [references/](references) — the domain knowledge and policy docs the skill reads before acting (scoring rubric, winning-patterns citations, platform coverage, measurement methodology, security posture)

## License

MIT — see [LICENSE](LICENSE).
