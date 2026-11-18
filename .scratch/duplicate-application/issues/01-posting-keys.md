# Derive posting keys from Job Posting links

Status: resolved

See `../spec.md`, section "Posting key".

## Acceptance

- `posting_keys(url)` in `board.py` returns the key for every row of the spec's table, including variants:
  `/apply` and `/application` suffixes, `?ashby_jid=` and `?gh_jid=` on a company host, LinkedIn subdomains
  (`br.linkedin.com`) and `/jobs/view/<slug>-<id>`.
- Unrecognized hosts get `url:<normalized url>`: tracking parameters, fragment, scheme, `www.` and a trailing
  `/` do not change the key; other query parameters do.
- Listing pages return an empty set (`https://www.bluecoding.com/jobs`, `https://talent.bluecoding.com/`).
- Pure function, no network. Covered by unit tests in `tests/test_board.py` built from the real `job_url` and
  `apply_url` shapes in `generated_cvs/` (Ashby, Lever, hireez, Loxo with `?t=`, LinkedIn job and post).
