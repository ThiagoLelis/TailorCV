# Time in Stage

Show how long each Application spends in each Stage, in particular how long it takes from **Applied** to the
company's first response (**In Process**) and from **Applied** to **Offer**.

## Data

- `move()` in `board.py` records when an Application enters a Stage, as new `application.md` frontmatter fields:
  `applied_at`, `in_process_at`, `offer_at`, `closed_at`. Entering **Awaiting Application** uses the existing
  `created` field; no new field.
- Values are local time without a timezone, `YYYY-MM-DDTHH:MM`. A date alone (`YYYY-MM-DD`, read as midnight) is
  also accepted, so the user can fill older Applications by hand.
- A timestamp is written only when the Stage actually changes (moving to the current Stage is a no-op).
- Only the **last** entry into each Stage is kept. When an Application enters Stage X, set `X_at` and **delete the
  timestamps of every Stage after X** in the order awaiting → applied → in-process → offer → closed. Example:
  reopening from Closed to Applied removes `closed_at`. Going from Applied straight to Closed keeps `applied_at`.
- No backfill: existing Applications, and folders moved by hand in the file explorer, have no timestamps and show
  "—".

## Calculation (client side, `board_ui/app.js`)

The server only stores timestamps. `summary()` already returns all frontmatter, so the API does not change.

- **Time in Stage** S = from entry into S to the next later Stage entry on record, or to now if S is the current
  Stage. If either end is missing, show "—".
- **Offer** and **Closed** are done Stages: no running time is shown for them.
- Metrics per Application:
  - Applied → response: `in_process_at - applied_at`.
  - Applied → Offer: `offer_at - applied_at`.
  - Closed without response (Applied → Closed with no `in_process_at`): show "no response · closed after N d".
- Display: less than 24 h shows "today"; anything longer shows whole days ("5 d"). Both are in the board's i18n
  strings (EN/PT).

## UI

- **Card**: time in the current Stage (e.g. "Applied · 5 d"), except in Offer and Closed.
- **Detail panel**: time in each Stage and both metrics.

## Docs

- ADR `docs/adr/0003-*`: keep only the last entry per Stage, and clear the timestamps of later Stages on move.
- `GLOSSARY.md`: add **Time in Stage** (PT: Tempo na etapa).
- The tailor-cv skill does not change.

## Out of scope

- Aggregate view across Applications (average or median Applied → response): `issues/04`.
- Stale-Application alert (e.g. highlighting a card after 14 d in Applied): `issues/05`.
