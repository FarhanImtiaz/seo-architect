# Changelog

All notable changes to this skill package are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/).

Rubric version: 2 (bumped from 1 on 2026-10-01, see below). `scripts/validate_claude_skill.py`
fails the build if `scripts/rubric.json`'s `version` field changes without a matching entry here —
when you bump the rubric, add a dated entry below that states the new rubric version number.

## [Unreleased]

### Changed — rubric version 2 (2026-10-01)
- Added a `platform` category (5 points, check `platform-content-visible`) to `scripts/rubric.json`
  and `scripts/score.py`: wires `platform_detect.py`'s `unavailable[]` entries (per-platform content
  gaps for Shopify/WordPress/Webflow/headless-CMS/SSG projects) into `coveragePct`, the same honesty
  model the framework-code adapters already use. Previously deferred (see the now-corrected
  `references/platform-coverage.md` and `platform_detect.py` docstring, which claimed this was
  wired in before it actually was). Excluded entirely, not scored zero, when no such platform is
  detected, so an ordinary framework-code-only project's `score` is unaffected -- its `coveragePct`
  denominator grows by 5 (the same way the pre-existing `local` category's 5 points already lower
  coveragePct for any non-local-business project), which is why `examples/worked-example-nextjs`'s
  golden `expected-audit*.json` coverage figures were updated alongside this change (71.0 -> 67.6,
  i.e. 71/105*100 -- `score` itself is unaffected, 58.3/73.2 unchanged, since `platform` is excluded
  from the denominator entirely for this plain-Next.js fixture, not scored zero; this is the rubric
  doing exactly what it's designed to do, not a regression).

### Documented
- `SKILL.md`, `references/assurance-model.md`: the Guardian hook's session scope does not extend
  into a Claude Code Task/Agent-tool subagent's isolated context, even when the subagent invokes
  this skill itself. Confirmed by direct testing: a fabricated `AggregateRating` schema edit
  inside a subagent produced no Guardian output at all, while the identical edit in a top-level
  session correctly triggered a review-required response. This was not a bug to fix — subagent
  hook isolation is how Claude Code's skill-frontmatter hooks are documented to work — but the
  prior wording ("runs... for the rest of the Claude Code session") didn't make the boundary
  clear enough for a real usage pattern (delegating SEO work to a subagent) to be safe by default.

### Fixed (adversarial QA pass on Phase 10-14: two confirmed SSRF vulnerabilities plus correctness bugs)
- `scripts/competitor_diff.py`: **SSRF, redirect not re-validated.** The guard checked only the
  first hostname before calling `urlopen`, which then followed 3xx redirects via its default
  handler with no re-check of the redirect target -- a "public" host could 302 to an internal
  address and its content would be returned. Every redirect hop (up to 5) is now independently
  re-guarded before being followed.
- `scripts/competitor_diff.py`: **SSRF, DNS-rebinding TOCTOU.** The guard resolved and validated
  a hostname, but `urlopen` then re-resolved the same hostname itself for the actual connection --
  a hostname that answers with a public IP at check-time and a private IP at connect-time bypassed
  the guard entirely. The connection is now pinned to the exact IP the guard validated (a direct
  `http.client` connection, with the real hostname sent only as the `Host` header and, for HTTPS,
  as the SNI/certificate-validation name), never re-resolving. The private/reserved check also
  switched from an explicit range allowlist to `not ip.is_global`, closing a gap where CGNAT/
  Tailscale addresses (`100.64.0.0/10`) previously passed.
- `scripts/competitor_diff.py`: `hasFAQ` matched a bare "faq" substring (e.g. a `/faq` nav link),
  `hasAuthorSignal` matched any class merely containing "author", and `wordCount` included
  `<script>`/`<style>` element text -- all three inflated structural signals beyond what the page
  actually shows. A URL host of `..` could also write output one directory outside
  `.claude/seo/competitors/`. All fixed.
- `scripts/scan_logs.py`: **cross-vendor false "verified".** `--ranges` files from different
  loaded vendors were pooled into one combined range set, so e.g. a GPTBot-labeled hit from an IP
  inside Bing's published range was reported "verified" -- claiming an identity the evidence
  didn't support. `--ranges` is now `BotName=path.json`, scoped per vendor; a hit is "verified"
  only against its own claimed bot's ranges. Also: `topParamUrls` printed raw querystring values
  verbatim (a real leak path for tokens/PII riding in a URL) -- values are now redacted, param
  names kept; a `--ranges` file that fails to parse is now a hard error instead of a silent drop
  that left the summary claiming "No --ranges given"; a JSONL line that parses but isn't an
  object no longer crashes with an uncaught `AttributeError`.
- `scripts/ci_check.py`: **a PR could weaken its own gate.** `.claude/seo/ci.json` was read from
  the head/PR being audited, so a PR could ship `{"failOn":[]}` alongside a real new HIGH finding
  and pass CI anyway. Config is now read from the BASE (trusted) ref only. `ignore[]` entries with
  no `expires` field were treated as permanently active; they're now always reported as expired,
  never silently applied. `annotations()` printed GitHub workflow-command annotations without
  escaping `%`/`\r`/`\n` in a finding's path or text, letting an embedded newline start a second,
  injected workflow command (confirmed reproducible) -- now percent-escaped per GitHub's own
  workflow-command escaping rules. Also: `--base-ref` values starting with `-` are now rejected
  (git-option-injection guard), and the base/head scratch copy now passes `symlinks=True` so a
  symlink pointing outside the repo is copied as a symlink, never followed and its target copied.
- `scripts/live_data.py` `import_ai_referrals`: substring host-matching overcounted
  (`claude.ai.evil.com` matched `claude.ai`) and undercounted (missed `chat.openai.com`). Now an
  exact-host-or-real-subdomain check, and `chat.openai.com` is in the known host list.
- `templates/github-action/seo-architect.yml`: added `persist-credentials: false` to the checkout
  step -- the workflow never needs the checkout token to persist afterward.
- `references/security.md`: corrected the SSRF-guard description to match the fix above (it
  previously claimed DNS-rebinding was "also refused," which was false until this pass).
- **Golden-fixture false alarm, not a real bug**: `worked_example_before_after_matches_golden_summary`
  appeared to regress (score 60.0 vs. golden 58.3) during this QA pass. Root cause: an earlier
  manual `full_audit.py --score` run had been pointed directly at the committed
  `examples/worked-example-nextjs/{before,after}` fixtures instead of a scratch copy, writing a
  stray `.claude/seo/baseline.json` into each and changing which `technical` checks were
  applicable. Removed the stray files; no code change was needed. (This is exactly the mutation
  `ci_check.py`'s own `run_audit()` scratch-copy discipline exists to prevent -- the fixtures
  themselves just aren't protected by that same discipline when run against directly.)

### Deferred (documented, not silently dropped)
- `references/platform-coverage.md` and `platform_detect.py`'s docstring claimed `score.py` lowers
  `coveragePct` for a platform adapter's `unavailable[]` entries; `score.py` never referenced
  platforms at all. Corrected both to state reality: platform `unavailable[]` entries appear in
  `full_audit.py`'s output but do not yet feed the score, since doing so needs a rubric version
  bump. Tracked here rather than implemented under this pass's time budget.
- Not yet addressed by this pass (found by the same QA pass, still open): `validate_ai_access.py`'s
  robots.txt group-merging doesn't fully implement RFC 9309 §2.2.1 multi-group merging, and its
  per-bot consequence text cites `references/sources.json` entries that don't yet exist for
  GPTBot/ClaudeBot/OAI-SearchBot/Perplexity/CCBot/Applebot; several platform adapters
  (`ssg_frontmatter.py`, `shopify.py`, `headless_cms.py`) have known false-positive/false-negative
  cases (Hugo page bundles, TOML frontmatter, Shopify over-detection on any `.liquid` file, a
  `Disallow: /` string-comparison bug); `render_diff.py`'s basename-fallback file pairing can pair
  unrelated files. Flagged for a follow-up pass.

### Added
- `scripts/ci_check.py`: PR/CI-time SEO regression check. Runs `full_audit.py --score` on a base
  ref (via `git archive`, no working-tree checkout needed) and on the current project inside
  disposable scratch copies (it never mutates either directory's real `.claude/seo/baseline.json`
  as a side effect of being run), diffs findings by a stable fingerprint, and reports new/resolved
  findings, removed routes without a matching redirect, and a score delta — or "not comparable" if
  the rubric version changed between base and head. Outputs JSON, a Markdown step summary, GitHub
  annotations, and optional SARIF. No network or secrets required by default. See
  `workflows/ci.md`, `templates/ci.json`, `templates/github-action/seo-architect.yml`, `action.yml`
  (a pin-by-SHA composite action; triggers on `pull_request` only, never `pull_request_target`),
  and `.pre-commit-hooks.yaml`.
- `scripts/seo_tools.py`: `regression()`'s per-page comparison now also tracks `noindex`, flagging
  a page newly set to noindex since the baseline as HIGH (previously silent).
- Site-wide technical depth: `scripts/scan_redirects.py` (redirect chains/loops/unresolved
  targets from `next.config.*`, `vercel.json`, `netlify.toml`, `_redirects`, `.htaccess`, nginx
  `.conf`; unparseable sources like Nuxt `routeRules` are reported `unavailable`, never silently
  treated as "no redirects"); `scripts/scan_canonicals.py` (canonical graph: missing/host-mismatch/
  chain/noindex-target, plus a shingle-overlap near-duplicate heuristic); `scripts/scan_freshness.py`
  (flags a declared "updated"/`dateModified` date newer than the actual last significant git
  change, skipping whitespace/year-only diffs; skipped entirely, with a note, outside a git repo);
  `scripts/render_diff.py` (response-vs-rendered HTML diff for canonical/title/links/JSON-LD that
  only exist after JavaScript runs; without `--rendered` it only checks for noindex-skips-rendering
  and says so); `scripts/scan_logs.py` (user-supplied access logs only, never fetched -- a bot
  user-agent is "ua-claimed" unless verified against a vendor's published IP ranges via `--ranges`;
  IPs are truncated before any aggregate is written, raw logs are never persisted). `validate_sitemap`
  (in `scripts/seo_tools.py`) now also checks lastmod format/future-dates/all-identical-lastmod,
  demotes priority/changefreq to INFO ("Google ignores these"), checks the 50k-URL/50MB limits,
  handles sitemap-index recursion, and checks for a robots.txt `Sitemap:` directive.
  `redirects`/`canonicals`/`freshness` are registered in `full_audit.py`'s `TOOLS`, so their
  findings appear in every audit; they don't yet feed `rubric.json`/`score.py` (that would need a
  rubric version bump, deferred to keep this phase additive and non-breaking to existing scores).
  `render_diff.py`/`scan_logs.py` need explicit input paths (real build output, a real log file) so
  they're standalone tools, not part of the default audit, matching how `live_data.py` works.
- Platform adapters for non-framework-code projects: `scripts/platform_detect.py` orchestrates
  `scripts/platforms/{ssg_frontmatter,headless_cms,webflow,shopify,wordpress}.py`. Each reports a
  real, checked `unavailable[]` list for content it cannot statically see (a headless CMS's actual
  entries, Webflow CMS Collection pages, Shopify's DB-owned catalog/sitemap, WordPress content
  usually owned by an SEO plugin) rather than silently guessing it's fine — `score.py` lowers
  `coveragePct` for those, matching the framework-code adapters' honesty model. See
  `references/platform-coverage.md` for the full per-platform matrix. Registered in
  `full_audit.py`'s `TOOLS` as `platforms`; not yet wired into `rubric.json` (additive, same
  reasoning as Phase 11's new tools).
- AEO access/eligibility, citation imports, competitor structural diff: `scripts/validate_ai_access.py`
  parses robots.txt with real per-group precedence (a bot-specific group correctly wins over a
  wildcard group, not just "does the token appear anywhere"), reports each named AI crawler's
  current access and the DOCUMENTED consequence of blocking it per that vendor's own crawler
  docs -- it never recommends allowing or blocking one, since that's the site owner's decision.
  `scripts/live_data.py` gained `import-bing-ai` (Bing Webmaster Tools AI Performance CSV) and
  `import-ai-referrals` (GA4 referral sessions filtered to known AI-assistant hosts, with an
  explicit systematic-undercount caveat since many AI clicks arrive referrer-less) -- both feed
  `impact.py` as ordinary metrics; no composite "AI visibility score" is ever computed.
  `scripts/competitor_diff.py` diffs a user-named PUBLIC page's structure (title length, heading
  outline, schema types, word count, FAQ/table/author/date signals, canonical, hreflang, internal
  links) against your own -- body text is never stored, only a content hash; an SSRF guard refuses
  private/loopback/link-local/reserved IPs (checked after DNS resolution, not just the literal
  hostname) before any fetch, robots.txt is respected, and requests are rate-limited to one per
  2 seconds. Output is always framed as "structural differences", never "why they rank" -- this
  tool has no ranking data and must never imply it does. `aiAccess` is registered in
  `full_audit.py`'s `TOOLS`; `competitor_diff.py` is a standalone tool (needs explicit URLs).
- Distribution, performance, ongoing verification: `.claude-plugin/plugin.json` + `hooks/hooks.json`
  (using `${CLAUDE_PLUGIN_ROOT}`, the reliably-expanded plugin-root variable — see the Phase-1
  fix history below for why `${CLAUDE_SKILL_DIR}` was never safe to rely on) + `scripts/build_dist.py`,
  which assembles a plugin-shaped distribution (`skills/seo-architect/...`) from this repo's
  standalone-skill layout without duplicating or forking the source of truth; the standalone
  install path in `INSTALL.md` is unaffected. `.github/workflows/test.yml` runs the suite and
  both validators across Python 3.9-3.13 (agent-evals need real `claude -p` auth and are
  deliberately not run in CI). `scripts/seo_tools.py`'s `files()` now honors a
  `SEO_ARCHITECT_MAX_FILES` environment variable to bound scan time on very large trees (default:
  unlimited, unchanged behavior). New `workflows/verify-sources.md` (the process for clearing a
  `lastVerified:"pending"` source) and `references/security.md` (the credential/network/SSRF/
  IP-truncation rules this skill follows, collected in one place).
- Live-measurement feedback loop (`scripts/impact.py`): register a change before deploying it,
  import real GSC/GA4/CrUX data afterward, and get a deterministic, honesty-constrained verdict
  (never a forecast, never a causal claim) via gate checks, a difference-in-differences effect
  estimate, a placebo-window distribution, and automatic confounder flagging. See
  `references/measurement-methodology.md` and `workflows/measure.md`.
- `scripts/validate_claims.py`: scans `.claude/seo/` and generated reports for outcome language
  ("increased traffic", "will rank", a bare "%" near clicks/traffic/rankings) that isn't backed by
  an `impact/` result or evidence-ledger citation.
- `scripts/live_data.py`: `import-gsc-zip` (parses the GSC UI's ZIP export and derives a real date
  range from `Dates.csv`), `--start`/`--end`/`--label` on CSV imports, content-hash-addressed,
  never-collide filenames under `.claude/seo/measurement/raw/` plus a `measurement/index.json`
  catalog, and API keys sent via the `X-goog-api-key` header instead of a URL query parameter.
- `scripts/seo_tools.py`: `snapshot --name` writes a non-overwritten, date+git-sha-named file
  under `.claude/seo/snapshots/` (in addition to the existing overwritten `baseline.json`).
- `scripts/score.py`: each check now reports `evidenceMix` (source-static/field-data/attested),
  and the output includes an `unavailableChecks` list with a plain-language reason and how to
  unlock each one.

### Fixed (second adversarial QA pass, re-attacking the fixes below)
- `scripts/impact.py`: the reported direction (`increase`/`decrease`) was decided by a bare
  `effect>1` comparison, but "unusual" was decided by comparing against a band centered on the
  placebo *median* -- when the site has a pre-existing trend (median != 1.0), the two could
  disagree and the reported direction was inverted (e.g. a real deceleration, still numerically
  >1, reported as "increase"). Direction is now read from which side of the placebo band the
  effect actually falls on.
- `scripts/impact.py`: two different, unrelated measurement files attached under the same label
  (e.g. two different pages' exports with overlapping-but-inconsistent date coverage) were
  silently merged by a "newest `importedOn` wins per date" rule, fabricating an effect out of a
  label mix-up. `import` now refuses an overlapping import unless the caller explicitly declares
  the relationship: `--supersedes <prior file>` for a refreshed copy of the same series (only the
  dates they actually share are overridden; the older file's unique dates still contribute), or
  `--combine` for genuinely additive series (summed on shared dates). An undeclared overlap is a
  hard error at import time, and `evaluate` re-checks the same invariant as defense in depth.
- `scripts/impact.py`: with fewer than 8 real placebo windows, the verdict was capped at
  `no-detectable-change` -- but that still asserted a null result that was never actually
  measured (a real +30% effect with 0 placebo windows read as "within this site's own normal
  variation"). Now correctly reports `insufficient-data` instead.
- `scripts/impact.py`: confounder-URL matching used exact string equality, so a registered
  change on `/b/`, `https://example.com/b`, `/B`, or `/b?utm=1` was never recognized as touching
  a control URL of `/b`, and a leading space from `--control-urls "/a, /b"` broke matching
  entirely. URLs are now normalized (scheme/host/query/trailing-slash/case) before comparison,
  and `--affected-urls`/`--control-urls` are trimmed on parse. `mark` also now refuses when
  affected and control URLs overlap after normalization.
- `scripts/impact.py`: the "last 3 days are provisional" cutoff was computed from a
  caller-suppliable `--as-of`, so a far-future `--as-of` could launder a stale, actually-incomplete
  export into a "settled" result. The cutoff is now bounded by the measurement files' own
  `importedOn` dates -- a caller cannot claim to know more than what was actually imported.
- `scripts/impact.py`: daily totals were keyed by the raw date string, so `2026-1-8` and
  `2026-01-08` counted as two different days and could double-count an overlapping re-import with
  inconsistent zero-padding. Dates are now parsed and normalized before use as a merge key (this
  also fixes GA4's bare `YYYYMMDD` format, which previously crashed `evaluate` with an uncaught
  `ValueError`).
- `scripts/impact.py`: the minimum-pre-window-volume gate summed whatever `--metric` was being
  evaluated (clicks/impressions/ctr/position) against a clicks-sized threshold, so a `ctr`
  evaluation could never pass the gate and a `position` evaluation passed regardless of actual
  traffic. The gate now always checks real click volume, independent of the primary metric.
- `scripts/live_data.py`: plain (non-ZIP) `import-gsc`/`import-ga4` didn't strip a UTF-8 BOM, so a
  BOM'd `Date` header became `'﻿Date'`, silently producing zero usable dated rows forever. Now
  opens with `utf-8-sig`, and both import paths print a visible warning if zero rows end up with a
  usable date after normalization (instead of failing silently).
- `scripts/live_data.py`: the secret scanner was fitted to the originally-reported shapes only;
  broadened to also catch AWS access keys, Google OAuth access/refresh tokens, Stripe live keys,
  GitHub personal access tokens, Slack tokens, and JWTs.
- `scripts/guardian_hook.py`: noindex directives (`<meta name="robots" content="noindex">`, Next's
  `robots:{index:false}`, an `X-Robots-Tag` header) had no content-based coverage at all -- arguably
  the single highest-risk SEO edit, since it can deindex a page outright, and it silently passed
  through unless the file path happened to contain the literal word "robots". Also added:
  single-quoted and array-form `@type`, canonical written as an object property
  (`{rel:"canonical"}`) rather than a JSX attribute, and nginx `rewrite ... permanent`.
- Every fix above has a new regression test reproducing the exact scenario a second, independent
  adversarial QA pass used to find it.

### Fixed
- `scripts/impact.py`: an independent adversarial QA pass found the evaluation pipeline could be
  pushed into a false directional verdict by realistic, non-adversarial situations. Fixed:
  missing data days inside a window silently reading as a real traffic move rather than
  `insufficient-data`; overlapping/refreshed imports double-counting an overlapping date instead
  of deduping to the most-recently-imported file; a directional verdict being allowed with fewer
  than 8 real placebo windows (previously falling back to an assumed +/-15%-of-median band,
  which `references/measurement-methodology.md` explicitly says this method never does) or with
  a near-zero minimum-detectable-change on flat history (now floored at 0.02); a confounding
  change to the *control* group going undetected (only the treated group's URLs were checked);
  the confounder-check window starting at `deployedOn` instead of `deployedOn - preDays`, missing
  pre-deploy events/changes that depress the baseline; a corrupt `external-events.json` or
  malformed change record silently disabling confounder detection instead of failing closed; and
  an empty/incomplete control-group window silently producing a confident `no-detectable-change`
  instead of `insufficient-data`. Each fix has a regression test reproducing the exact original
  failure mode.
- `scripts/live_data.py`: `import-gsc-zip` only stored Pages.csv/Queries.csv rows (which have no
  `date` column), using `Dates.csv` solely to derive a date range -- every real GSC import
  therefore produced zero usable rows and `impact.py evaluate` could never advance past
  `insufficient-data` on real data. It now stores Dates.csv's date-keyed daily rows (the data
  `impact.py` actually evaluates against) and refuses to import a ZIP with no Dates.csv, with or
  without an explicit `--start`/`--end`. `import-gsc`/`import-ga4`/`import-gsc-zip` also now
  normalize capitalized GSC/GA4 CSV headers (`Date`, `Clicks`, `CTR` as `"5.5%"`) onto the
  lowercase keys `impact.py` expects.
- `scripts/live_data.py`: the secret scanner ran its regex against `json.dumps(row)`, but the
  pattern `api[_-]?key\s*[:=]` could never match the resulting quoted-key JSON shape
  (`"api_key": "..."`), so a CSV column literally named `api_key`/`password`/`client_secret`
  went undetected. Broadened to match the quoted form and to also catch `sk-`-style keys, Bearer
  tokens, `GOCSPX-` client secrets, and PEM private-key blocks, while requiring a real
  value-shaped string (not a bare keyword) to avoid flagging a harmless `?token=` URL parameter.
- `scripts/guardian_hook.py`: the sensitive-content check lowercased the edit text but not its
  own needles (`'"@type":"aggregateRating"'` has a capital R and could never match after
  lowering), assumed no whitespace around `:`, and never inspected `old_string` -- so removing a
  canonical tag, or editing `next.config.js` redirects, `vercel.json`, `netlify.toml`, `.htaccess`,
  or a whitespace/case-variant JSON-LD `AggregateRating`/`Review` block, all silently passed
  through as "allow." Now matches case-insensitively via regex, covers those file types and the
  `alternates.canonical` pattern, and scans removals as well as additions.
- `scripts/score.py`: a site with zero images scored a flawless 5/5 on the image-based
  Performance checks (`total=... or 1` forced a fake denominator instead of letting the
  zero-total case report as unavailable). Fixed to report `unavailable` with no evidence, per the
  skill's own "never invents a number" rule.
- `SKILL.md`: the documented `validate_page_contract.py service .` invocation doesn't match the
  script's actual argument parser (it takes `--brief <path>`, not a trailing project path, and
  exits 2 with "unrecognized arguments" as written) -- corrected to the working form.
- `references/winning-patterns.md`: removed internal build-plan references ("Phase 4", "Phase 5",
  "Phase 7") and a description of hreflang validation as a "subcommand" when it is the separate
  `validate_hreflang.py` script -- these described the build plan, not the shipped capability.

### Added
- Live-measurement feedback loop (`scripts/impact.py`): register a change before deploying it,
  import real GSC/GA4/CrUX data afterward, and get a deterministic, honesty-constrained verdict
  (never a forecast, never a causal claim) via gate checks, a difference-in-differences effect
  estimate, a placebo-window distribution, and automatic confounder flagging. See
  `references/measurement-methodology.md` and `workflows/measure.md`.
- `scripts/validate_claims.py`: scans `.claude/seo/` and generated reports for outcome language
  ("increased traffic", "will rank", a bare "%" near clicks/traffic/rankings) that isn't backed by
  an `impact/` result or evidence-ledger citation.
- `scripts/live_data.py`: `import-gsc-zip` (parses the GSC UI's ZIP export and derives a real date
  range from `Dates.csv`), `--start`/`--end`/`--label` on CSV imports, content-hash-addressed,
  never-collide filenames under `.claude/seo/measurement/raw/` plus a `measurement/index.json`
  catalog, and API keys sent via the `X-goog-api-key` header instead of a URL query parameter.
- `scripts/seo_tools.py`: `snapshot --name` writes a non-overwritten, date+git-sha-named file
  under `.claude/seo/snapshots/` (in addition to the existing overwritten `baseline.json`).
- `scripts/score.py`: each check now reports `evidenceMix` (source-static/field-data/attested),
  and the output includes an `unavailableChecks` list with a plain-language reason and how to
  unlock each one.

### Fixed
- `scripts/live_data.py`: GSC/GA4 imports previously recorded `dateRange: 'unspecified'` and
  same-day imports silently overwrote each other; PSI/CrUX API keys were sent in the URL query
  string rather than a header (a leak risk via logs); the secret scanner only checked the first 5
  CSV rows rather than all of them.
- `scripts/seo_tools.py`: `page_record()`'s noindex detection matched any occurrence of the word
  "noindex" anywhere in a file's text (including in prose), producing false positives; it's now
  scoped to an actual meta-robots tag, an `X-Robots-Tag` config value, or Next's
  `robots: { index: false }`.
- `SKILL.md`: the Guardian hook command only resolved for a global (`$HOME`) skill install; a
  project-local install (`INSTALL.md`'s second option) made the hook a silent no-op. It now checks
  both locations, and a still-missing script now prints a visible stderr warning instead of being
  swallowed by `2>/dev/null` — it still never blocks a tool call on its own path failure.

## [1.1.0] - 2026-09-27

### Added
- Reproducible 100-point audit scoring (`scripts/score.py`, `scripts/rubric.json`,
  `references/scoring-rubric.md`) — previously the score was prose-only with no code computing it.
- Per-schema-type JSON-LD validation against Google's required/recommended properties
  (`scripts/schema_rules.json`), including visible-content alignment checks.
- The winning-patterns library: 16 cited pattern cards (`references/winning-patterns.md`) tied to
  34 real, named sources (`references/sources.json`) with a tiered (A/B/C) citation-discipline
  validator (`scripts/validate_sources.py`) and deterministic signal matching
  (`scripts/pattern_match.py`).
- Internal link graph and image SEO scanning (`graph`/`images` subcommands in
  `scripts/seo_tools.py`).
- Framework-aware metadata extraction (`scripts/metadata_extract.py`) across Next.js (App and
  Pages Router), Nuxt, SvelteKit, Astro, Remix, and Vue/Helmet, replacing regex-only guessing.
- hreflang validation (`scripts/validate_hreflang.py`).
- A worked before/after example (`examples/worked-example-nextjs/`) and agent-eval test scenarios
  (`tests/agent-evals/`).
- Optional, opt-in live-data adapters (`scripts/live_data.py`): GSC/GA4 CSV import, PageSpeed
  Insights, CrUX.

### Fixed
- `scripts/framework_adapters.py`: a stray tuple literal (`'<title', text` instead of
  `'<title' in text`) made a MEDIUM "missing Next.js metadata" finding's guard condition always
  truthy, so it could never fire.
- `scripts/framework_adapters.py`: a Next.js/Nuxt project could be classified as both frameworks
  because both matched any `pages/` directory.
- `scripts/seo_tools.py`: the loose `title:` regex matched any JavaScript object with a `title`
  property (component props, CMS objects), not just page metadata.
- `SKILL.md`: the Guardian hook referenced `${CLAUDE_SKILL_DIR}`, which Claude Code does not
  expand in hook commands, silently blocking every `Write`/`Edit` call; the hook is also now
  fail-open (`|| true`) so a path/exec problem can never again block edits.

## [1.0.0] - initial

### Added
- Initial SEO Architect skill: guardian hook, evidence ledger, static route/metadata/sitemap/
  robots/JSON-LD/link scanning, framework detection, AEO signal checks, and full-audit
  orchestration.
