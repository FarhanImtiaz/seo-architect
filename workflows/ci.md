# CI / PR integration

`scripts/ci_check.py <project> --base-ref <ref>` runs `full_audit.py --score` on the base ref (via `git archive`, no working-tree checkout needed) and on the current directory, diffs findings by a stable fingerprint (tool/severity/issue/file), and reports what's new. No network, no secrets, no paid API required — it reuses the same static evidence `audit`/`score` already produce locally.

Setup for a project:

1. `python3 scripts/ci_check.py . --base-dir <a clean checkout of main>` locally first, to confirm it runs cleanly before wiring it into CI.
2. Copy [templates/github-action/seo-architect.yml](../templates/github-action/seo-architect.yml) to `.github/workflows/` in the project (not in this skill package), and set `SKILL_DIR` to wherever the skill is installed there. It triggers on `pull_request` only — never `pull_request_target` — and needs only `permissions: contents: read`.
3. Optionally copy [templates/ci.json](../templates/ci.json) to `.claude/seo/ci.json` to set `failOn` rules, a `scoreDropTolerance`, and time-boxed `ignore[]` entries (each needs a `fingerprint`, `reason`, and `expires` date — an expired ignore stops being applied and its finding fails the build again).

If the base ref's `rubric.json` hash differs from the head's, `ci_check.py` reports the score as not comparable instead of a misleading delta — that's expected right after a rubric version bump, not a bug.

For performance budgets (Core Web Vitals, bundle size), pair this with [Lighthouse CI](https://github.com/treosh/lighthouse-ci-action) rather than expecting `ci_check.py` to reimplement it — this skill's Performance category is a static proxy (image dimensions, lazy-loading, file weight), not a lab measurement.

A `.pre-commit-hooks.yaml` entry (`seo-architect-guard`) is available for a fast staged-only check before the full PR-time comparison; it's not a substitute for the real CI job, which compares against an actual base ref.
