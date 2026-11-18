# Find the open Application for a set of links, with a CLI

Status: resolved
Blocked by: 01

See `../spec.md`, section "Check".

## Acceptance

- `Board.open_application_for(urls)` returns the summary of the open Application whose `job_url` or
  `apply_url` shares a posting key with any of `urls`, or `None`.
- Applications in `closed/` never match. Applications in `awaiting/`, `applied/`, `in-process/` and `offer/` do.
- Links with no key (listing pages) never match anything.
- With several matches, the most recent by `created` wins.
- `python3 board.py --check <url> [<url> ...]` exits 0 with no output when there is no match, and exits 1
  printing `<stage>/<folder>  <company> — <role>` when there is one. It does not start the server. `--root` still
  applies. Running without `--check` starts the server as before.
- Covered by tests in `tests/test_board.py` against a temporary `generated_cvs/` tree (Closed vs open, `job_url`
  vs `apply_url` match, cross-source match via apply link, listing page, CLI exit codes).
