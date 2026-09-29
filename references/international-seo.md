# International SEO (hreflang)

Only relevant once a project actually serves more than one locale/market. Use `scripts/validate_hreflang.py` (or `seo_tools.py hreflang`) — it self-gates to `applicable:false` when no `locale`/`secondaryMarkets` is set in `.claude/seo/config.json` and no i18n route/config signal is detected, rather than reporting false findings on a single-locale site.

Requirements, per [Google's own documentation](https://developers.google.com/search/docs/specialty/international/localized-versions) (see `references/sources.json` `google-hreflang-docs`):

- Every localized page should declare a self-referencing hreflang entry (pointing at itself).
- Alternates must be reciprocal: if page A declares an alternate to page B, page B must declare one back to A.
- Codes are ISO 639-1, optionally with an ISO 3166-1 region (`en`, `en-GB`) — not a made-up or malformed variant (`en-UK` is a common mistake for `en-GB`).
- An `x-default` fallback is recommended when there's a locale-selection or no-match page.

hreflang is a correctness requirement, not a ranking lever — see [references/winning-patterns.md](winning-patterns.md) P15. Fix missing self-reference, missing reciprocity, and invalid codes before any other localization work.
