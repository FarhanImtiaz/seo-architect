---
name: seo-architect
description: >-
  SEO and AEO engineering skill for auditing, planning, implementing, and
  validating search visibility across web projects. Use when creating,
  changing, launching, migrating, or reviewing pages, routes, metadata,
  structured data, content, internal links, performance, local SEO, or AI
  search readiness.
hooks:
  PreToolUse:
    - matcher: "Write|Edit"
      hooks:
        - type: command
          command: "( p=\"$CLAUDE_PROJECT_DIR/.claude/skills/seo-architect/scripts/guardian_hook.py\"; [ -f \"$p\" ] || p=\"$HOME/.claude/skills/seo-architect/scripts/guardian_hook.py\"; if [ -f \"$p\" ]; then python3 \"$p\"; else echo 'SEO Guardian: guardian_hook.py not found (checked project-local .claude/skills and $HOME/.claude/skills); allowing the edit unreviewed.' >&2; fi ) || true"
          timeout: 5
---

# SEO Architect

Use this skill as a search-visibility engineering layer, not a keyword-density or content-spam generator. It applies to explicit `/seo-architect <command>` requests and to normal development work only when the change affects routes, URLs, page content, metadata, navigation, images, sitemap/robots, redirects, schema, locale, or CMS models. Do not interrupt ordinary visual-only work unless an actual search-sensitive regression is apparent.

## Operating contract

1. Inspect the project before recommending or changing it. Prefer the project’s existing framework conventions.
2. Follow: inspect → identify intent and impact → make the smallest safe change → validate → re-scan → update `.claude/seo/` → summarize.
3. Optimize for crawlability, useful intent-aligned information, clear entities, internal linking, valid structured data, accessible performance, and answer extraction. Never optimize for keyword density.
4. Separate observed facts, inferences, recommendations, and hypotheses. Do not invent rankings, volume, reviews, clients, credentials, results, citations, or facts. When citing a documented external pattern from [references/winning-patterns.md](references/winning-patterns.md), use its required citation form and never transfer another site's numbers to this one as a forecast.
5. Local checks are evidence about source code, not proof of indexation, rendering, rankings, rich results, or AI citations. Use current web research when the question depends on live SERPs or platform guidance.

## Guardian decisions

Classify search-sensitive changes before editing:

- **Safe auto-fix:** deterministic missing metadata, a deterministic canonical, obvious descriptive image alt text, an omitted known sitemap route, or an explicit breadcrumb hierarchy. Validate afterward.
- **Review first:** primary title/query changes, URL changes, merges/deletions, redirect or canonical strategy, major rewrites, and localization.
- **Never silently:** delete indexed pages, generate doorway/location pages, fabricate proof, use cloaking/deceptive redirects, hide crawler-only content, keyword stuff, assert unsupported schema, present another site's documented results as a forecast for this one, claim an `impact.py evaluate` result caused a change (it reports observed correlation against the site's own history, never causation), change a registered measurement window after the fact without recording it in `amendments[]`, claim a competitor's ranking or why they rank from `competitor_diff.py`'s structural output (it has no ranking data), invent a composite "AI visibility" score, or recommend allowing/blocking a specific AI crawler in robots.txt as if it were not the site owner's own business decision.

For an URL change, preserve the old URL in `.claude/seo/changelog.md`, determine indexability, add a suitable redirect when approved, update internal links/sitemap/canonical/breadcrumbs, and run a regression comparison. Do not rename URLs merely to sound more SEO-friendly.

## Commands and routing

Read the named workflow before acting. Natural-language equivalents use the same routing.

| Intent | Workflow |
|---|---|
| `setup`, `status` | [workflows/setup.md](workflows/setup.md) |
| `audit`, `technical`, `fix` | [workflows/audit.md](workflows/audit.md) |
| `page <topic>`, `optimize <path>`, `optimize-page` | [workflows/new-page.md](workflows/new-page.md), [workflows/optimize-page.md](workflows/optimize-page.md) |
| `keywords`, `content` | [workflows/keywords.md](workflows/keywords.md), [workflows/content-plan.md](workflows/content-plan.md) |
| `schema`, `links`, `aeo` | [workflows/schema.md](workflows/schema.md), [workflows/internal-links.md](workflows/internal-links.md), [workflows/aeo.md](workflows/aeo.md) |
| `local`, `ecommerce` | [workflows/local.md](workflows/local.md), [workflows/ecommerce.md](workflows/ecommerce.md) |
| `launch`, `report` | [workflows/launch.md](workflows/launch.md), [workflows/report.md](workflows/report.md) |
| `playbook`, "what's working for others" | [workflows/playbook.md](workflows/playbook.md) |
| `measure`, "did it work", "impact" | [workflows/measure.md](workflows/measure.md) |
| `ci`, "set up CI", "PR check" | [workflows/ci.md](workflows/ci.md) |
| `verify-sources`, "check pending sources" | [workflows/verify-sources.md](workflows/verify-sources.md) |
| general implementation | [workflows/optimize.md](workflows/optimize.md) |

Commands may share a workflow: `technical` is a technical audit; `fix` fixes only evidenced, approved-safe findings; `page` means `new-page`; `links` means `internal-links`.

## Project state and tools

Project-specific facts and recommendations live under `.claude/seo/`, never in this skill. Initialize or repair it with:

```bash
python3 /path/to/seo-architect/scripts/init_state.py --project .
```

Use the scripts from the target project root. They report unsupported inspection rather than treating it as success:

```bash
python3 /path/to/seo-architect/scripts/scan_routes.py .
python3 /path/to/seo-architect/scripts/scan_metadata.py .
python3 /path/to/seo-architect/scripts/validate_sitemap.py .
python3 /path/to/seo-architect/scripts/validate_robots.py .
python3 /path/to/seo-architect/scripts/validate_jsonld.py .
python3 /path/to/seo-architect/scripts/scan_links.py .
python3 /path/to/seo-architect/scripts/scan_link_graph.py .
python3 /path/to/seo-architect/scripts/scan_images.py .
python3 /path/to/seo-architect/scripts/seo_regression.py snapshot .
python3 /path/to/seo-architect/scripts/seo_regression.py compare .
python3 /path/to/seo-architect/scripts/framework_inspect.py .
python3 /path/to/seo-architect/scripts/framework_adapters.py .
python3 /path/to/seo-architect/scripts/evidence_ledger.py verify .
python3 /path/to/seo-architect/scripts/validate_page_contract.py service --brief <brief.json>   # omit --brief to print the required-fields template
python3 /path/to/seo-architect/scripts/validate_aeo.py .
python3 /path/to/seo-architect/scripts/validate_hreflang.py .
python3 /path/to/seo-architect/scripts/metadata_extract.py .
python3 /path/to/seo-architect/scripts/full_audit.py . --initialize --snapshot --score
python3 /path/to/seo-architect/scripts/score.py .
python3 /path/to/seo-architect/scripts/pattern_match.py .
python3 /path/to/seo-architect/scripts/live_data.py import-gsc . <csv>   # only when the user has authorized data and asks
python3 /path/to/seo-architect/scripts/impact.py mark . --id <id> ...     # register a change BEFORE deploying it (see workflows/measure.md)
python3 /path/to/seo-architect/scripts/impact.py evaluate . <id>          # only after real time and real imported data exist
python3 /path/to/seo-architect/scripts/validate_claims.py .               # advisory scan for unbacked outcome language in .claude/seo/
python3 /path/to/seo-architect/scripts/ci_check.py . --base-ref <ref>     # PR/CI-time regression check; see workflows/ci.md
python3 /path/to/seo-architect/scripts/render_diff.py --response <dir> --rendered <dir>  # only with real build output and, optionally, a real rendered DOM dump
python3 /path/to/seo-architect/scripts/scan_logs.py <access.log> --ranges <ranges.json>  # only with a real, user-supplied log file -- never fetched
python3 /path/to/seo-architect/scripts/competitor_diff.py <public-url>    # structural diff only, never a rank claim -- see references/assurance-model.md
python3 /path/to/seo-architect/scripts/live_data.py import-bing-ai . <csv>       # only when the user has authorized data and asks
python3 /path/to/seo-architect/scripts/live_data.py import-ai-referrals . <csv>  # only when the user has authorized data and asks
```

Read [references/seo-principles.md](references/seo-principles.md) for shared quality rules, then only the relevant one-hop reference for technical work, content, IA, links, schema, AEO, local/ecommerce, images, performance, research, migration, measurement, or international/hreflang. Read [references/platform-coverage.md](references/platform-coverage.md) before reporting on a WordPress/Shopify/Webflow/headless-CMS project, so `unavailable` findings are explained rather than treated as silent gaps. Read [references/scoring-rubric.md](references/scoring-rubric.md) before reporting a category score, [references/winning-patterns.md](references/winning-patterns.md) plus [references/sources.json](references/sources.json) before citing a documented growth pattern, and [references/measurement-methodology.md](references/measurement-methodology.md) before running or reporting an `impact.py evaluate` result. Use templates in `templates/` when creating state or reports.

## Assurance model

After first invocation, the Guardian hook runs before `Write` and `Edit` operations for the rest of the Claude Code session. It injects validation context for SEO-sensitive files and requires review before edits that appear to remove routes or change redirects, canonical URLs, robots directives, or structured-data assertions. It intentionally does not block ordinary component/style work. Read [references/assurance-model.md](references/assurance-model.md) for evidence levels, framework/static limits, and rendered checks.

## Output

Keep outputs compact. Audits show the transparent 100-point category score computed by `scripts/score.py` — never hand-computed — only when there is enough evidence, severity, evidence, impact, fix, automation level, and file/path. State that it is an internal prioritization score over the evidenced maximum (report `coveragePct` too), not a Google/Bing score or ranking prediction. Implementations list Changed, Validated, SEO impact, and Remaining.

On first call in a project, run `full_audit.py <project> --initialize --snapshot --score` before strategy work. It is the deterministic baseline—not a substitute for judgment, rendered checks, or authorized measurement data.
