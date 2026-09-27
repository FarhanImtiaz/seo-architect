# Worked example: audit → fix → rescan

Synthetic fixture. No real client, traffic, or ranking outcomes — this demonstrates the skill's mechanics on a made-up four-page site (`before/`), not a case study.

## 1. Audit

```
python3 scripts/init_state.py --project <copy of before/>
python3 scripts/full_audit.py <copy of before/> --score
```

Findings (see `expected-audit.json` for the full golden summary):

- **HIGH** (`jsonld`, rule `missing-required`): `/product`'s `Product` schema has none of `offers`/`review`/`aggregateRating` — Google requires at least one for rich-result eligibility (see [references/structured-data.md](../../references/structured-data.md)).
- **MEDIUM** (`metadata`): `/about` has no statically detectable title or description.
- **MEDIUM** (`images`): `/product`'s `<img>` has no `alt` attribute and no width/height.
- **MEDIUM** (`graph`): `/orphan` has no inbound internal links.
- **MEDIUM** (`state`): `.claude/seo/keywords.md` and `strategy.md` are still template-stub-only — "Content/keyword strategy: NOT STARTED."

Score: **58.3** (evidenced max coverage 71% — `local` is excluded, not scored zero, since this fixture has no local-business signal).

## 2. Guardian classification

Per SKILL.md's Guardian decisions:

- Adding a missing title/description to `/about` → **safe auto-fix**.
- Adding descriptive alt text + width/height to `/product`'s image → **safe auto-fix**.
- Adding a schema `offers` block to `/product` → **safe auto-fix**, since the price/availability are already visible in the page copy (never add schema values that aren't visible — see [references/structured-data.md](../../references/structured-data.md)).
- Adding a contextual link from `/` to `/orphan` → **safe auto-fix** (a real `<a href>`, not link-stuffing).
- Filling in `keywords.md`/`strategy.md` → out of scope for `fix`; flagged as an open backlog item for the `keywords`/`content` commands, not silently left empty.

## 3. Apply the safe fixes

See `after/` for the result: `/about` has a title+description, `/product`'s schema has a complete `Offer` matching the visible price, its image has descriptive alt text and dimensions, and `/` now links to `/orphan`.

## 4. Rescan

```
python3 scripts/full_audit.py <copy of after/> --score
```

- **HIGH/CRITICAL findings: 0** (down from 1).
- **Score: 73.2** (up from 58.3; same 71% coverage — the fixes didn't change which categories have evidence, only how well they score).
- `content` stays at 3.0/9 in both runs: the stub-state finding is intentionally NOT part of `fix`'s scope — this is the "flag it explicitly across sessions" behavior from the `state` check, not something a `fix` pass silently resolves.

## 5. Applicable winning patterns

Running `scripts/pattern_match.py` against this fixture would match **P04** (structured data — the Product/offers fix) and **P08** (contextual internal links — the orphan fix), each citable in the required form from [references/winning-patterns.md](../../references/winning-patterns.md).
