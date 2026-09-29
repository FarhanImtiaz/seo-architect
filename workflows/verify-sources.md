# Verifying pending sources

`references/sources.json` entries with `lastVerified:"pending"` have not been confirmed by directly reading the source (a prior fetch attempt 403'd, or the fetch was never attempted). `scripts/validate_sources.py` surfaces the current pending count as a warning; treat a rising count as a regression, not noise.

To verify one:

1. Fetch the entry's `url`. If it fails (403, moved, paywalled), leave `lastVerified:"pending"` and add or update `caveats` with exactly what couldn't be confirmed and why — never silently leave it unexplained.
2. If it succeeds, confirm the fetched content actually supports the specific mechanism/finding `references/winning-patterns.md` attributes to it — not just that the URL resolves. A page that loads but doesn't say what a pattern card claims it says is not verified.
3. Set `lastVerified` to today's real date (not guessed), and correct the entry's `tier`/`numbersQuotable` if the content turns out to license less than the card currently assumes (e.g. a number you thought was Tier A turns out to be a third party's estimate).
4. If a card's evidence turns out weaker than presented, fix the card itself — don't quietly leave `winning-patterns.md` overstating what a downgraded source supports.
5. Re-run `python3 scripts/validate_sources.py .` — it must still PASS, and the pending count should have dropped by one.

A source older than 12 months also warrants a re-check even if previously verified (`validate_sources.py` warns on this) — pages get edited, numbers get updated, and a stale "verified" stamp is worse than an honest "pending" one.
