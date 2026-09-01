# SEO Architect

`seo-architect` is a reusable Claude Code skill for technical SEO, useful on-page work, information architecture, structured data, internal links, and answer-engine readiness. It is an engineering guardrail: it records evidence, makes only safe fixes automatically, and does not generate spam or invented proof.

## Install

See [INSTALL.md](INSTALL.md). Claude Code discovers global skills at `~/.claude/skills/seo-architect/` and project skills at `.claude/skills/seo-architect/`.

## Start

Run `/seo-architect setup`, then `/seo-architect audit`. State is created in the target project at `.claude/seo/`; it contains no credentials. The deterministic one-command baseline is `python3 /path/to/seo-architect/scripts/full_audit.py . --initialize --snapshot`. Common commands are `status`, `technical`, `page "topic"`, `optimize <path>`, `keywords`, `content`, `schema`, `links`, `aeo`, `local`, `ecommerce`, `launch`, `report`, and `fix`.

## Automation boundaries

It can safely fill deterministic omissions and validate them. After the skill fires, its in-session Claude Code hook flags sensitive file changes and asks for review before likely indexation, redirect, canonical, or schema-claim changes. It never silently creates doorway pages, fake proof, crawler-only content, deceptive redirects, keyword stuffing, or misleading schema.

## Optional data and agency use

The skill works from source code alone. Search Console, analytics, Bing, and SEO providers can add observed data when available; record only facts and do not put credentials in state. For Flowmend, start with `/seo-architect setup` and enter confirmed business facts in `.claude/seo/config.json`; [examples/flowmend-state](examples/flowmend-state) is a minimal onboarding example, not an authoritative profile. Derive services from the site. For a client, use the same flow and record their confirmed market, services, and evidence.

## Test

`python3 tests/run_tests.py` executes deterministic validator, Guardian, evidence, page-contract, and regression scenarios. Scripts are dependency-free Python 3.10+ and intentionally report static-analysis limits. `scripts/live_validate.py https://staging.example.com/page` optionally verifies one rendered HTTP response.

## Customization and V2

Edit project state rather than the global skill. Keep client facts out of the package. Potential V2 work: authenticated GSC/Bing integrations, SERP snapshots, citation monitoring, freshness alerts, tickets, and client reports.
