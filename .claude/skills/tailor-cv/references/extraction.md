# Extracting job descriptions — what worked per source

Try WebFetch first; fall back to curl/APIs below. Never give up on the first 404 or empty page: most career pages
are JS shells around an ATS that has a public API.

## LinkedIn
- `linkedin.com/jobs/view/<id>/` returns a 301 to `br.linkedin.com/jobs/view/<slug>-<id>`. WebFetch the redirect
  target — the guest page includes the full JD, seniority, applicant count and whether it is still accepting
  applications ("Não aceita mais candidaturas" = closed → tell the user, ask before generating).
- `lnkd.in/p/<code>` short links: resolve with `curl -sIL -m 20 <url> | grep -i '^location'`.
  - To `linkedin.com/posts/...` (a member post): WebFetch works; JD is in the post text; the "how to apply" is often
    "DM me" — record that in job_info.md.
  - To `linkedin.com/feed/update/urn:li:groupPost:...` (group post): requires login, cannot be extracted. Ask the
    user to paste the text.

## Ashby (`jobs.ashbyhq.com`, or company pages with `?ashby_jid=<uuid>`)
- Company career pages often embed Ashby via JS. Find the org name by grepping the page's JS bundles:
  `curl -s -A 'Mozilla/5.0' <page> | grep -oE 'src="[^"]*\.js"'` then grep each bundle for `ashbyhq`.
  (Superhuman's org is `Superhuman Platform Inc`, URL-encoded.)
- Public API (full JD, location, remote flag, comp):
  `curl -s "https://api.ashbyhq.com/posting-api/job-board/<URL-encoded org>?includeCompensation=true"` → find the
  job whose `id` equals the `ashby_jid`; use `descriptionPlain` and `jobUrl` (the direct apply link).

## Greenhouse / Lever
- Greenhouse: `https://boards-api.greenhouse.io/v1/boards/<board>/jobs/<id>?content=true`
- Lever: `https://api.lever.co/v0/postings/<company>/<id>`
- The project's `parsers.py` also extracts JSON-LD `JobPosting` from these boards.

## Loxo (`*.app.loxo.co/job/...`) and other recruiter boards
- WebFetch works directly. Often posted by a recruiter for an unnamed client — record the recruiter, the contact
  listed on the page, and the fact that the employer is undisclosed.

## Generic careers pages / ads
- A link from a paid ad (utm_campaign=..., hsa_*) may point to a *service* page, not a job (e.g. HatchWorks
  "Forward Deployed Engineers" is a consulting offering). Check the company's job board (look for hireez, Workable,
  Ashby, Greenhouse links on the careers page) and WebSearch "<company> <role> job". If no posting exists, tell the
  user; if they still want a CV, base it on the service/role description and mark the vaga as NOT CONFIRMED.
- Pages listing several roles (e.g. Blue Coding talent page): pick the one that best matches the profile and
  mention the alternatives.

## Company research for job_info.md
Fetch in parallel: the company's careers page (values, benefits, hiring steps), an "about" page, and values/blog
pages linked from the JD. Only write facts you actually read; mark inferences as such.
