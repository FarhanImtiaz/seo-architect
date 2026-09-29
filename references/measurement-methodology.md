# Measurement methodology

`scripts/impact.py` answers one question honestly: did a specific, pre-registered change measurably move a metric, relative to this site's own history? It is not a forecast, not proof of causation, and not a substitute for the 100-point hygiene score in `scripts/score.py` — the two are never mixed. A change record is registered *before* deployment (`mark`), real data is imported only after real time has passed (`import`), and only then is it evaluated (`evaluate`).

## The pipeline

1. **Gate checks** — refuse with `insufficient-data` unless: the imported treated series covers at least `preDays` before deployment and the full `settleDays`+`postDays` after it; the last 3 days before "now" are excluded as provisional (a partial week undercounts); the treated pre-window volume clears `minData.minPreClicks`; no attached measurement is `synthetic` (unless explicitly testing).
2. **Effect estimate** — with a control group: `(treated post/pre) ÷ (control post/pre)`, a difference-in-differences ratio. Without one: the plain treated post/pre ratio, but the verdict is then capped at `observed-sitewide-not-separable` regardless of size — a site-wide change with nothing to compare against can never honestly claim a direction.
3. **Placebo distribution** — the same pre/post window pair is slid across the site's own pre-change history to build a null distribution of the identical statistic. The observed effect is judged against *this site's own variance*, not an assumed one. Fewer than 12 placebo windows is noted as a resolution limitation, not hidden.
4. **Confounders** — automatically checked: other registered changes whose windows and URLs overlap, entries in `.claude/seo/external-events.json` (algorithm updates, migrations, outages, campaigns) that fall inside the evaluation window. Any hit forces `confounded`, full stop — an effect number is not also reported as meaningful.

## The fixed verdict vocabulary

Never paraphrase these into softer or stronger language. They are deliberately blunt:

- `insufficient-data` — not enough data yet; lists exactly what's missing.
- `confounded` — cannot be attributed to this change; another change or event overlaps the window.
- `no-detectable-change` — the observed effect sits inside this site's own normal variation (the reported `minimumDetectableChange` is the resolution floor below which nothing could have been seen anyway).
- `change-consistent-with-hypothesis` / `change-opposite-to-hypothesis` — observed, unusual relative to this site's own history; **consistent with, not proof of,** the change's effect.
- `observed-sitewide-not-separable` — the ceiling for any change with no control group.

## What this must never do

- Forecast a result before it's measured.
- Claim revenue or conversions without GA4 conversion data actually imported.
- Report on a query or page that wasn't in the imported rows.
- Change `preDays`/`settleDays`/`postDays` after the fact without recording it in `amendments[]` (always echoed back in every evaluation).
- Treat Search Console's average position as a rank.
- Split AI Overviews/AI Mode out from "Web" performance data — Google's own documentation counts them together; don't imply a separation the data doesn't support.
- Feed a verdict or effect size back into `scripts/score.py`. The hygiene score and this measurement answer different questions; conflating them would make the score read as a ranking predictor, which it explicitly is not.

## Why a control group changes what's claimable

Search traffic moves for reasons that have nothing to do with any one page: seasonality, algorithm updates, competitor changes, brand campaigns. A control group (pages you didn't touch) absorbs those site-wide swings, so the treated-vs-control ratio isolates something closer to the change's own effect. Without one, a real traffic swing and a real page change are indistinguishable — which is exactly why the no-control case is capped rather than allowed to claim a direction.
