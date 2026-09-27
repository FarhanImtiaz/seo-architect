# Playbook ("what's working for others")

Run `full_audit.py . --snapshot`, then `scripts/pattern_match.py .` to get a deterministic, signal-based shortlist of applicable pattern IDs from [references/winning-patterns.md](../references/winning-patterns.md). Read the full card for each matched ID — do not act on the ID alone.

For each pattern presented to the user:

1. State it with the required citation form from `winning-patterns.md`'s opening rules: `Documented pattern (Source, tier X): mechanism. Applicability here: [observed/inference]. Expected effect on this site: unknown until measured.`
2. Show the "Verify here" evidence that made it match this project.
3. Follow the "Skill action" exactly — most propose a plan or a specific edit, not a blanket rewrite.
4. Never quote the "Do not claim" content as if it were an available claim.

Never present a pattern's source-site outcome as a forecast for this project. A pattern is context for a decision, not a shortcut around the Guardian classifications or the evidence-gate rules in SKILL.md. If the user wants to lean heavily on a `lastVerified:"pending"` source (see `references/sources.json`), say so explicitly and suggest they confirm it first.
