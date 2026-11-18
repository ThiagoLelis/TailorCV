# Duplicate Application

Never create a **Duplicate Application**: an Application for a Job Posting that already has one that is not
Closed (see `GLOSSARY.md`). When the tailor-cv skill is about to create one, it does not, and it tells the user
which Application already exists.

Applications are only created by the tailor-cv skill. The board only moves them, so the board UI does not change.

## Rules

- **Open Applications**: an Application in `awaiting/`, `applied/`, `in-process/` or `offer/` blocks a new one
  for the same Job Posting. One in `closed/` does not: pursuing the posting again creates a new Application.
- **Same Job Posting**: two links lead to the same Job Posting only when they share a **posting key** (below).
  If there is no shared key, they are distinct Job Postings, even at the same company with a similar role. There
  is no fuzzy matching on company or role.
- **Blocked, not warned**: a duplicate is never created. The skill skips that link, says so in its report, and
  goes on with the other links.
- **Regenerating is not creating**: when the user asks to regenerate or update an existing Application, the skill
  works in that folder as it does today, and the check does not apply.

## Posting key

`posting_keys(url) -> set[str]` in `board.py`. It is a pure function with no network access. It returns one key
for a link that identifies a posting, and an empty set for a link that does not.

| Source | Link shapes | Key |
| --- | --- | --- |
| Ashby | `jobs.ashbyhq.com/<org>/<uuid>[/application]`, any host with `?ashby_jid=<uuid>` | `ashby:<uuid>` |
| Lever | `jobs.lever.co/<company>/<id>[/apply]` | `lever:<id>` |
| Greenhouse | `boards.greenhouse.io/<board>/jobs/<id>`, `job-boards.greenhouse.io/...`, any host with `?gh_jid=<id>` | `greenhouse:<id>` |
| LinkedIn job | `[xx.]linkedin.com/jobs/view/<id>`, `/jobs/view/<slug>-<id>` | `linkedin-job:<id>` |
| LinkedIn post | `linkedin.com/posts/<slug>-<activity id>-<code>`, `/feed/update/urn:li:activity:<id>` | `linkedin-post:<id>` |
| Anything else | | `url:<normalized url>` |

IDs are lowercased. A normalized URL:

- uses a lowercase host without `www.`, keeps the path's case (Loxo IDs are case-sensitive base64) and ignores
  the scheme;
- drops the fragment and the tracking query parameters (`utm_*`, `hsa_*`, `gclid`, `fbclid`, `ref`, `source`,
  `t`, `trk`, `refId`, `trackingId`) and keeps the other parameters, sorted;
- drops a trailing `/` and a trailing `/apply` or `/application` segment.

**Listing pages** identify no posting and return an empty set. A listing page is a link whose path, after
normalization, is empty or a single segment from `jobs`, `careers`, `career`, `join`, `join-us`, `opportunities`,
`vagas`. Example: `https://www.bluecoding.com/jobs` and `https://talent.bluecoding.com/`. This keeps two different
Blue Coding postings from blocking each other through a shared generic link.

`lnkd.in` short links are not resolved here. The skill resolves them first (see `extraction.md`); an unresolved
`lnkd.in` link gets an ordinary `url:` key.

## Check

`Board.open_application_for(urls) -> dict | None`: the summary (`id`, `stage`, frontmatter) of the open
Application whose `job_url` or `apply_url` shares a posting key with any of `urls`, or `None`. If more than one
matches, return the most recent by `created`.

CLI, so the skill can call it without the server running:

```
python3 board.py --check <url> [<url> ...]
```

- No open Application: prints nothing and exits 0.
- Found: prints one line, `<stage>/<folder>  <company> — <role>`, and exits 1.

## Skill (`.claude/skills/tailor-cv/SKILL.md`)

1. **Before extraction**: run `--check` with the link the user pasted (after resolving `lnkd.in`). This catches a
   repeated paste before any fetching.
2. **After extraction**: run `--check` with every link learned for the posting (the pasted link, the resolved
   LinkedIn target, the ATS `jobUrl`, the apply URL). This catches the same posting reached through another
   source, e.g. a LinkedIn job whose apply link is the Ashby posting that already has an Application.
3. If either check finds an open Application, do not create anything for that link. Report it alongside the
   other results, in the user's language, with the existing Application's Stage, company, role and folder path,
   and say that they can ask to regenerate it if that is what they meant.
4. When writing `application.md`, `job_url` must be the posting itself, never a listing page. If the only link
   is a listing page, keep it, but know that the posting cannot be matched later.
5. **Folder name**: if `<date>_<Company>_<Role>` already exists in any Stage (a Closed Application pursued again
   on the same day), append `-2`, `-3`, … so a later move to that Stage does not hit the `already exists`
   conflict in `Board.move()`.

## Docs

- `GLOSSARY.md`: done (Job Posting, Application, Duplicate Application).
- No ADR: the rule is cheap to change and involved no architectural trade-off.
- `board.py` docstring: mention `--check`.

## Out of scope

- Matching across sources without a shared key (e.g. a LinkedIn job whose apply link is "DM me", against an Ashby
  posting). Per the glossary, those count as distinct Job Postings.
- Backfilling `job_url` on existing Applications that point to listing pages.
- Any duplicate check in the board UI.
