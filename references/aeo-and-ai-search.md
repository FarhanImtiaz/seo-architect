# AEO and AI search

## What is supported

Treat answer-engine optimization as excellent search and information design, not a separate ranking system. Google states that AI features use the same foundational SEO practices and have no additional special optimization requirements. Eligibility still requires an indexed page eligible to appear with a search snippet; eligibility does not guarantee crawling, serving, an AI Overview link, a citation, or traffic. See [Google’s AI features guidance](https://developers.google.com/search/docs/appearance/ai-features) and its [generative AI optimization guide](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide).

Make the answer available before elaboration: define the service/problem, state conditions and limits, use scannable steps or comparisons when they genuinely clarify, and keep company identity consistent. Add FAQs only when the page truly answers them. Support claims with attributable first-party evidence, transparent methodology, author/company information, and freshness where it matters.

## Implementation checks

1. The important information is visible in the rendered page, returns a successful response, and is not blocked from indexing/snippets.
2. Headings describe sections; the opening content answers the page’s primary question or states the offering plainly.
3. Facts that could change include scope, constraints, date, and source where appropriate.
4. Structured data describes the same visible content and is parsed/validated; it is not a citation or AI-feature guarantee.
5. Relevant high-quality image/video media have useful context and accessible alternatives.
6. Track business outcomes and observed source data, not invented “AI visibility” scores.

## Do not do

Do not create an `llms.txt` file, crawler block/allow rule, FAQ, schema type, hidden prompt, keyword variant page, or AI-generated content disclosure as a magic ranking tactic. Use preview controls only when the site owner intentionally wants to limit snippets; restrictive controls can also limit appearance in AI search experiences. Automated content must remain accurate, original, valuable, and people-first; scaled low-value generation violates Google’s policies. [Google’s guidance on generated content](https://developers.google.com/search/docs/fundamentals/using-gen-ai-content) explains this boundary.
