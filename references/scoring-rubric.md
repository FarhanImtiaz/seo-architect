# Scoring rubric (v1)

The 100-point audit score is computed by `scripts/score.py`, never hand-computed by the model. It consumes `full_audit.py --score` and reads the exact point breakdown from `scripts/rubric.json` (this file must stay in sync with it).

A category with no supporting evidence (no sitemap found, no local-business signal, no image scan wired in yet) is **excluded from the denominator**, never scored zero. The reported `score` is earned points over the evidenced maximum; `coveragePct` shows how much of the full 100 was actually evidenced. Always present both numbers, and the label "internal prioritization, not a ranking prediction."

| Category | Max | Checks (points) |
|---|---|---|
| Technical | 20 | robots not blocking all crawling (4) · sitemap parses with absolute URLs (3) · sitemap covers static routes (3) · canonical present ratio (4) · no noindex on discovered routes (3) · no routes missing vs. baseline (3) |
| IA | 10 | orphan ratio (4, requires link graph) · % routes within 3 clicks of home (4, requires link graph) · breadcrumbs on nested routes (2) |
| On-page | 15 | title present (4) · titles unique (3) · description present (2) · descriptions unique (2) · exactly one H1 (2) · title length 15-65 chars (2) |
| Content | 15 | strategy/keywords not stub (3) · keyword target URLs resolve (3) · thin-content ratio, ≥150 words (3) · no duplicate template text (3) · no business-potential-0 cluster (3, attested) |
| Links | 10 | no unresolved internal links (4) · no orphans (3, requires link graph) · generic-anchor ratio (3, requires link graph) |
| Schema | 10 | JSON-LD parses (3) · required properties present per type (4) · Organization/WebSite on home (1) · visible-content alignment (2) |
| Performance | 5 | images have dimensions (2, requires image scan) · no lazy-load on first image (1, requires image scan) · image weight ok (2, requires image scan) |
| Local | 5 | NAP consistency (2) · LocalBusiness schema with address (2) · contact route exists (1) — whole category excluded unless a local-business signal (LocalBusiness schema or a phone number) is observed |
| AEO | 10 | direct-answer signal (3) · author/org identity (2) · date signal (2) · schema/visible alignment (3, attested) |

## Partial credit

Every check is one of:
- **ratio** — `points × (pass_count / applicable_count)`. Not applicable (denominator is zero) → excluded, not zero.
- **binary** — full points or zero, only when the underlying data source exists (e.g. a sitemap was actually found).
- **attested** — full points only when a human supplies `--attest <check-id>=<evidence-ledger-index>` pointing at an active evidence-ledger entry. Never assumed true by default.

## Reproducibility

`scripts/rubric.json` has a version and this file's content is derived from it. `score.py` reports `rubricHash` so two audits can be diffed even across a rubric change. Running `score.py` twice against an unchanged project produces byte-identical category output.
