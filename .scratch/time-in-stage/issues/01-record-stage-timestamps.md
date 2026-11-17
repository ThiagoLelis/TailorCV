# Record Stage entry timestamps on move

Status: resolved

See `../spec.md`, section "Data".

## Acceptance

- Moving an Application to Stage X writes `X_at` (local `YYYY-MM-DDTHH:MM`) to `application.md` frontmatter.
  Awaiting has no field (uses `created`).
- Timestamps of every Stage after X (awaiting → applied → in-process → offer → closed) are removed.
- Moving to the current Stage changes nothing.
- The user's notes and other frontmatter fields are preserved.
- Covered by tests in `tests/test_board.py` (inject the clock so tests are deterministic).
