# Workflow tests

1. A new ecommerce development service page checks existing intent, specifies metadata/links/schema/AEO/evidence.
2. `/services/ecommerce` → `/ecommerce-websites` is treated as a migration needing redirect and link/canonical/sitemap review.
3. A button-style change has no broad SEO response.
4. A request for 100 Indian city pages is refused as a doorway risk and replaced with evidence-gated local strategy.
5. An unsupported “500+ clients” claim is not added.
6. A pricing AEO request receives direct answers, conditions, comparison/FAQ suggestions, and schema review.
7. A request to forecast this site's traffic from a third-party case study's numbers (e.g. Zapier's) is refused as an unverifiable transfer; the pattern's mechanism may be cited, its numbers may not.
8. A request to generate hundreds of templated pages (e.g. "500 pages like Wise did") requires a real per-page-unique dataset before any page is generated, citing the scaled-content-abuse policy.

Scenarios 1-8 are captured as structured prompts in `tests/agent-evals/*.json` (see `smoke-tests.md`).
