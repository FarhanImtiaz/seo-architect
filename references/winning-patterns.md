# Winning patterns

Every pattern below is traceable to a real, publicly documented source in [references/sources.json](sources.json) — never an invented statistic or a fabricated case study. Cite a pattern using exactly this form:

> Documented pattern (Source, tier X): mechanism. Applicability here: [observed/inference]. Expected effect on this site: unknown until measured.

Rules that apply to every card:

- Never transfer another company's numbers to the user's site as a forecast. A tier-A/B source's numbers may be quoted as "on their site, self-reported"; a tier-C source's numbers are never quoted at all — only the observable structure/mechanism.
- A pattern is context for a decision. It never overrides an evidence gate in SKILL.md ("Never silently: ... fabricate proof," doorway pages, unsupported schema, etc.).
- A source marked `lastVerified:"pending"` in `sources.json` has not been opened and confirmed by a human yet — treat its mechanism as provisional, and say so if asked to lean on it heavily.

Each card: `Pattern` (one line) → `Documented evidence` (source IDs) → `Mechanism` → `Applies when` → `Verify here` → `Skill action` → `Do not claim`.

## P01. Test template-level changes on groups of pages, don't assume they work

**Documented evidence:** pinterest-seo-experiments, pinterest-summary-gigazine, etsy-title-tag-optimization, etsy-multivariate-seo-testing, airbnb-seo-experimentation, searchpilot-case-studies-index
**Mechanism:** Split templated pages (not users) into control/variant groups — by hashing the URL, or by market — and compare organic traffic over 1-2 weeks. Pinterest found some accepted best practices (e.g. making duplicate board titles unique) had no measurable effect.
**Applies when:** A site has many pages sharing one template (dynamic route segments) and authorized analytics access.
**Verify here:** `full_audit.py` route scan shows dynamic routes; `.claude/seo/config.json` `tracking.analytics` is true.
**Skill action:** Propose a split-test plan for a template-level change instead of rolling it out unmeasured; record the plan in `.claude/seo/content-plan.md`.
**Do not claim:** That a specific change "will" lift traffic. Offer an experiment, not a forecast.

## P02. Server-render main content and links; treat JS-rendering changes as high-risk

**Documented evidence:** pinterest-seo-experiments, searchpilot-ssr-internal-links, google-crawlable-links-docs
**Mechanism:** Pinterest's move to JS-rendered content measurably hurt traffic for about a month before recovering. SearchPilot's own test of exposing JS-only links as server-rendered anchors was inconclusive at 95% confidence — SearchPilot itself says there's no universal rule.
**Applies when:** A rendering-mode change (CSR↔SSR, hydration strategy) is proposed for indexable routes.
**Verify here:** Guardian hook classification (rendering/link changes route through "review first").
**Skill action:** Treat rendering-mode changes as review-first, not safe auto-fix, regardless of the theoretical SEO argument either way.
**Do not claim:** That server-side rendering improves rankings — the evidence is mixed/inconclusive, not a guarantee either direction.

## P03. Fix missing/duplicate titles and descriptions before tuning their wording

**Documented evidence:** pinterest-seo-experiments, etsy-title-tag-optimization
**Mechanism:** Pinterest found filling in missing meta descriptions helped; Etsy found shorter titles did better, but that was an Etsy-specific experimental result, not a universal formatting rule.
**Applies when:** Any audit finds missing/duplicate title or description.
**Verify here:** `seo_tools.py metadata` findings.
**Skill action:** Missing/duplicate metadata is a deterministic safe-auto-fix. Changing title *wording/format* for an already-present title is an experiment (see P01), not a silent edit.
**Do not claim:** "Shorter titles rank better" as a general rule — that was observed at Etsy, not proven universally.

## P04. Structured data that matches visible content, for types with a documented search feature

**Documented evidence:** google-structured-data-intro, google-eventbrite-case-study, google-jobrapido-case-study, google-howto-faq-changes-2023
**Mechanism:** Structured data makes a page *eligible* for a search feature (rich result); Eventbrite and Jobrapido both adopted type-appropriate schema (Event, JobPosting).
**Applies when:** A page has visible content matching an available schema.org type in `scripts/schema_rules.json`.
**Verify here:** `seo_tools.py jsonld` per-type validation; Eventbrite's own case study explicitly notes multiple concurrent SEO projects made attribution difficult — quote that caveat when citing it.
**Skill action:** Implement schema per [references/structured-data.md](structured-data.md); check FAQPage/HowTo eligibility status before implementing either (both have had eligibility restricted/removed — see google-howto-faq-changes-2023, marked `volatile`).
**Do not claim:** A ranking or traffic gain from adding schema. Schema affects feature eligibility, not rankings, and guarantees nothing.

## P05. Topic clusters: one pillar page, linked cluster pages

**Documented evidence:** hubspot-topic-clusters
**Mechanism:** A pillar page covering a broad topic, linked bidirectionally to narrower cluster pages, each cluster page owning one URL.
**Applies when:** `keywords.md` groups queries into clusters, or a content area has 5+ related pages with no hub.
**Verify here:** `.claude/seo/keywords.md` maps each cluster to one target URL; link graph (Phase 4) shows pillar↔cluster links both directions.
**Skill action:** In `new-page.md`/`content-plan.md`, propose the pillar/cluster structure before creating a new standalone page in an existing topic area.
**Do not claim:** A specific ranking outcome from restructuring into clusters.

## P06. Prioritize topics by "business potential," not raw search volume

**Documented evidence:** ahrefs-seo-content-marketing
**Mechanism:** Score each topic 0-3 (3 = the product is the indispensable solution to the topic; 0 = no natural way to mention the product). Only publish topics scored 2-3.
**Applies when:** Building or reviewing `.claude/seo/keywords.md` or `content-plan.md`.
**Verify here:** The Business-potential column in `templates/keywords.md` / `templates/content-plan.md`.
**Skill action:** Reject topics scored 0; require a stated rationale for the score.
**Do not claim:** A specific traffic number for a given score — it's a prioritization heuristic, not a traffic model.

## P06b. Cautionary case: a large content footprint on off-topic subjects can decline

**Documented evidence:** searchengineland-hubspot-decline, aleyda-solis-hubspot-analysis
**Mechanism:** Analysts attribute much of HubSpot's 2024-25 organic-traffic decline to popular topics unrelated to HubSpot's core business.
**Applies when:** A content plan proposes topics scored 0-1 on business potential (see P06) purely for traffic volume.
**Verify here:** Cross-reference proposed topics against the business-potential column.
**Skill action:** Use this as the negative case for P06 — cite it when a stakeholder pushes for off-topic "traffic plays."
**Do not claim:** Causation. This is analysts' inference from public data, not HubSpot's own attribution — always label it that way (tier C, `numbersQuotable:false`).

## P07. Refresh posts that already earn traffic instead of only publishing new ones

**Documented evidence:** hubspot-historical-optimization
**Mechanism:** HubSpot found most blog views/leads came from older posts, so they update those posts for accuracy/completeness rather than letting them go stale, keeping the URL stable.
**Applies when:** Analytics/Search Console data (or evidence-ledger entries) identify existing pages with traffic but stale content.
**Verify here:** Requires authorized measurement data (Phase 7 live-data adapters) or an evidence-ledger entry; otherwise this is a hypothesis, not an observed fact.
**Skill action:** Propose a refresh candidate list in `content-plan.md`; update `dateModified` only when content substantively changes, never cosmetically.
**Do not claim:** That refreshing guarantees renewed traffic.

## P08. Add contextual internal links to under-linked pages

**Documented evidence:** searchpilot-nearby-location-links, searchpilot-increasing-internal-linking, searchpilot-internal-linking-tag, google-crawlable-links-docs
**Mechanism:** SearchPilot's split tests added contextual links (to nearby location pages; to lower-level category pages) and measured organic-traffic impact; both used real `<a href>` elements with descriptive anchors, per Google's own crawlable-links guidance.
**Applies when:** The link graph (Phase 4) finds an under-linked commercially important page.
**Verify here:** `.claude/seo/link-graph.json` inbound-link counts.
**Skill action:** Propose specific source→target→anchor additions in `internal-links.md`; avoid sidebar/footer link-stuffing (see [references/internal-linking.md](internal-linking.md)).
**Do not claim:** A specific traffic lift from adding links on this site.

## P09. "Programmatic" pages are legitimate only when each page has unique, query-answering data

**Documented evidence:** salt-agency-zapier-traffic, omnius-wise-case-study, google-spam-policies-2024
**Mechanism:** Observable structure (not verified traffic outcomes): Zapier's app/app-pair integration pages and Wise's currency-pair pages each carry real, per-page-unique data (a specific integration's setup steps; a live exchange rate) rather than templated filler.
**Applies when:** A request proposes generating many similar pages from a template (locations, integrations, comparisons, currency/unit pairs).
**Verify here:** Does the project have a real per-page dataset with distinct values? At Phase 5, the `--built-dir` uniqueness check on rendered output.
**Skill action:** Require a concrete uniqueness source before proposing template-generated pages; this directly enforces the existing "Never silently: generate doorway/location pages" rule and Google's scaled-content-abuse policy (google-spam-policies-2024).
**Do not claim:** Any of the third-party traffic estimates for Zapier/Wise — they're tier C and `numbersQuotable:false`. Cite structure only.

## P10. Build a genuinely better linkable asset (Skyscraper)

**Documented evidence:** backlinko-skyscraper-technique
**Mechanism:** Make a more complete, current, and better asset than the best-ranking existing page on a topic. Outreach to sites that could reasonably link to it is a separate, non-code activity.
**Applies when:** A content gap analysis finds a topic where competitors' existing content is outdated or shallow.
**Verify here:** Manual competitive content review; this pattern's scope for this skill is limited to *building the asset*, not outreach.
**Skill action:** Propose the asset in `content-plan.md`, scoped to genuinely more complete/current/accurate content — not filler padding.
**Do not claim:** The self-reported outreach-result numbers in the source as a forecast. A published critique of this technique exists and hasn't been read this session — flag that if the user wants to lean heavily on it.

## P11. Core Web Vitals: real user-experience/business impact, not a direct ranking lever

**Documented evidence:** webdev-vodafone-case-study, webdev-yahoo-japan-case-study, webdev-economic-times-case-study, webdev-vitals-business-impact
**Mechanism:** Vodafone's controlled A/B test moved a widget's rendering server-side, measuring better LCP and a documented sales increase. Yahoo! JAPAN News fixed layout shift (CLS) by reserving image space before load.
**Applies when:** Images are missing dimensions, or a page has late-loading above-the-fold content (Phase 4 image scan).
**Verify here:** `seo_tools.py images` findings (Phase 4).
**Skill action:** Fix missing width/height and defer non-critical lazy-loading, framed as user-experience/conversion work.
**Do not claim:** A ranking improvement — the documented outcomes are engagement/conversion, not search position.

## P12. Local search: complete, accurate, consistent business information

**Documented evidence:** google-local-ranking-support, searchpilot-nearby-location-links
**Mechanism:** Google's own guidance names relevance, distance, and prominence as the ranking factors, driven by complete/accurate Business Profile information — not by content volume.
**Applies when:** `local.md` workflow runs and NAP (name/address/phone) or LocalBusiness schema is present.
**Verify here:** `score.py`'s Local category (NAP consistency, LocalBusiness+address schema, contact route).
**Skill action:** Verify NAP consistency and complete Business Profile fields before proposing new local pages.
**Do not claim:** Any influence over "distance." Never recommend fabricating reviews.

## P13. AI answers (AEO): indexable, snippet-eligible pages with unique, detailed, well-evidenced content

**Documented evidence:** google-ai-search-guidance-2025, geo-arxiv-paper, ahrefs-ai-overviews-reduce-clicks
**Mechanism:** Google states AI features rely on the same foundational SEO practices, not a separate system. A lab benchmark (GEO, KDD 2024) found that adding citations/quotations/statistics improved a page's visibility *within that research benchmark*.
**Applies when:** Running the `aeo` workflow.
**Verify here:** `validate_aeo.py` static signals.
**Skill action:** Add direct answers, clear entity/author identity, and dated freshness — never FAQ/schema/citations purely to "game" an LLM.
**Do not claim:** That the GEO paper's benchmark result transfers to production Google/ChatGPT — it does not, and Ahrefs' own observational data shows AI Overviews correlate with *lower* CTR for the top organic result, which is worth setting as an honest expectation in `report.md`.

## P14. URL migrations: full mapping, redirects, before/after crawl comparison

**Documented evidence:** aleyda-solis-migrations-checklist
**Mechanism:** Map every old URL to its new target, add redirects, and run a crawl comparison before/after the migration.
**Applies when:** The `launch` workflow's URL-change path is triggered.
**Verify here:** `.claude/seo/changelog.md`, `seo_tools.py snapshot`/`compare` (the existing regression baseline mechanism already implements the "before/after crawl comparison" half of this pattern).
**Skill action:** Follow the existing SKILL.md URL-change contract (preserve old URL in changelog, confirm indexability, add redirect when approved, update internal links/sitemap/canonical, run regression).
**Do not claim:** A migration is risk-free because the checklist was followed — regression-check the result.

## P15. hreflang for localized page sets

**Documented evidence:** google-hreflang-docs
**Mechanism:** Reciprocal `hreflang` links across all localized variants, a self-reference on every page, and an `x-default` fallback.
**Applies when:** i18n is detected or `config.json` lists secondary markets (Phase 5 `hreflang` subcommand).
**Verify here:** `validate_hreflang.py` findings.
**Skill action:** Fix missing self-reference/reciprocal links/x-default before other localization work.
**Do not claim:** A ranking benefit in any specific market from correct hreflang — it's a correctness requirement, not a ranking lever.
