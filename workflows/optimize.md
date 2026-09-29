# General optimization

Use for search-sensitive development changes. Inspect before editing, identify intent/impact, make minimal reversible changes, validate affected assets, rescan, and update state/changelog. Apply Guardian classifications. A purely visual button-style change gets a short “no search-sensitive regression identified” response, not a broad audit.

For a change with a measurable hypothesis (a title/content rewrite, an internal-linking change, a schema addition), offer to `scripts/impact.py mark` it (see [workflows/measure.md](measure.md)) before it ships.
