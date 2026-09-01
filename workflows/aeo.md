# AEO

Read [AEO and AI search](../references/aeo-and-ai-search.md) and [the assurance model](../references/assurance-model.md). First confirm the page is indexable and eligible for a normal search snippet; no answer-engine work bypasses technical SEO. Then inspect the visible page for a concise direct answer, definitions, conditions/limits, scannable steps or comparison where useful, clear organization/author identity, original evidence, dated freshness, useful images/video, and schema that exactly matches visible content.

Use `validate_aeo.py` for static signals and, when possible, `live_validate.py` against the rendered staging URL. Treat output as a review queue, never as an “AI visibility score.” Do not add FAQ blocks, schema, citations, AI disclosures, or special crawler directives merely to game an LLM. Add only answers and evidence that genuinely help a visitor.

When Search Console or another authorized source provides AI-feature data, record its date, property, and limitations in the evidence ledger. Otherwise report AI-feature measurement as unavailable. Never promise inclusion, citation, impressions, rankings, or traffic.
