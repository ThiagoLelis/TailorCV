# tailor-cv skill blocks Duplicate Applications

Status: resolved
Blocked by: 02

See `../spec.md`, section "Skill".

## Acceptance

- `SKILL.md` workflow runs `python3 board.py --check` before extraction (pasted link, `lnkd.in` resolved) and
  after extraction (every link learned for the posting).
- On a match the skill creates nothing for that link, finishes the other links, and reports the existing
  Application (Stage, company, role, folder path) in the user's language, offering to regenerate it instead.
- The regenerate/update path is unchanged and skips the check.
- `application.md` guidance: `job_url` is the posting itself, never a listing page.
- New folder names get a `-2`, `-3`, … suffix when `<date>_<Company>_<Role>` already exists in any Stage.
- `board.py` module docstring mentions `--check`.
