# Measure ("did it work", "impact")

Read [references/measurement-methodology.md](../references/measurement-methodology.md) before running or reporting anything here — the verdict vocabulary is fixed and non-negotiable.

**Before a change ships**: run `scripts/impact.py mark <project> --id <id> --deployed-on <date> --affected-urls <urls> [--control-urls <urls>] --metric clicks --direction increase --description "..."`. `--deployed-on` must be user-confirmed, not guessed. Prefer a real `--control-urls` (e.g. the rest of the site) whenever the change is scoped to specific pages — without one, the evaluation is capped and can never reach a directional verdict (see the methodology doc).

**After real time has passed and the user has real data**: only with the user's authorized export (never fetched automatically), run `scripts/live_data.py import-gsc-zip <project> <zip> --label treated` (and again with `--label control` for the control set, if separate), then `scripts/impact.py import <project> <id> <measurement-file> --label treated`.

**Check timing** with `scripts/impact.py status <project> <id>` — it prints the date the change becomes eligible for evaluation. Never evaluate before that date; offer the user `/schedule` or `/loop` for a reminder instead of implying this skill will check on its own.

**Evaluate** with `scripts/impact.py evaluate <project> <id>`. Report the verdict using its exact fixed wording — never soften `insufficient-data` into "looks promising" or upgrade `no-detectable-change` into "no change is normal." If the verdict is `confounded`, name the confounder and stop there; do not also report an effect number as if it were meaningful.

**Never**: forecast an outcome before it's measured, treat `average position` as a rank, present the result as caused by the change rather than observed alongside it, or change `--pre-days`/`--settle-days`/`--post-days` on an existing change record without `--amend` (which records the change in `amendments[]` and is always shown back to the user).
