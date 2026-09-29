# Launch

Run a release gate for canonical host, indexability, robots, sitemap, titles/descriptions/H1, canonical/OG, JSON-LD, internal links, redirects/404, mobile/performance basics, images, breadcrumbs, direct answers, commercial pages, hreflang (when the project serves more than one locale — see [references/international-seo.md](../references/international-seo.md)), and configured tracking. Return READY, READY WITH WARNINGS, or BLOCKED; block only severe indexation, URL, content, or deployment risk.

For a rendering-mode change, apply [references/winning-patterns.md](../references/winning-patterns.md) P02 (treat as review-first; evidence on SSR/CSR impact is mixed, not a guarantee either direction). For a URL migration, apply P14 (full URL mapping, redirects, before/after crawl comparison via the existing snapshot/compare baseline).

Before shipping a launch-gated change, offer to `scripts/impact.py mark` it (see [workflows/measure.md](measure.md)) so its real-world effect can be honestly checked once enough time has passed — never as a requirement, but a launch with no measurement plan can't later answer "did it work."
