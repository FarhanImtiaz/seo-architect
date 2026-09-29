# Schema

Inspect visible content first, select only fitting types, implement minimal non-conflicting JSON-LD, parse it with the validator, and confirm it remains aligned after edits. Treat reviews/ratings, prices, availability, authors, and local data as evidence-gated.

Run `seo_tools.py jsonld` — it checks required/recommended properties per type and flags values (rating, price, address) that aren't visible on the same page. A HIGH finding (missing required property, e.g. Product with none of offers/review/aggregateRating) blocks; a MEDIUM visible-alignment finding means the schema asserts something the page doesn't show — fix the content or drop the assertion, never the reverse. FAQ/HowTo eligibility has changed before (see [references/structured-data.md](../references/structured-data.md)); do not promise a rich result for either.

[references/winning-patterns.md](../references/winning-patterns.md) P04 covers when structured data is worth adding and its Eventbrite/Jobrapido evidence.
