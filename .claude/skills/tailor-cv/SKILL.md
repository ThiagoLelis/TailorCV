---
name: tailor-cv
description: Generates tailored, ATS-optimized English CVs (Markdown + PDF) for Thiago Lelis from job posting links, plus a job_info.md with the apply link, company/culture research and interview prep, and an application.md that tracks the Application on the TailorCV board, saved in generated_cvs/awaiting/<date>_<Company>_<Role>/. Use this whenever the user pastes one or more job links (LinkedIn, lnkd.in, Ashby, Greenhouse, Lever, Loxo, careers pages, even a WhatsApp-style list of links) or a job description and wants a CV/resume/currículo for it, asks to "gerar currículo", "adaptar CV", "abrir os links das vagas", or wants to regenerate existing CVs after a change to his profile.
---

# Tailor CV

Turn job links into ready-to-send application packages for **Thiago Lelis dos Santos**. One folder per Job Posting:

```
generated_cvs/awaiting/<YYYY-MM-DD>_<CompanyNoSpaces>_<Role-With-Hyphens>/
├── Thiago Lelis - <Company>.md     # CV source
├── Thiago Lelis - <Company>.pdf    # CV to send
├── job_info.md                    # apply link + company research + interview prep (Portuguese)
└── application.md                  # the Application: frontmatter + Thiago's own notes
```

The date is today's date.

## The board (Stages are folders)

`python3 board.py` serves a Kanban board over `generated_cvs/` (see `GLOSSARY.md` and `docs/adr/`). Each
Stage is a folder: `awaiting/`, `applied/`, `in-process/`, `offer/`, `closed/`. The board moves Application
folders between them, so:

- A **new** Application always goes in `generated_cvs/awaiting/`.
- To regenerate or update an existing one, find its folder in **any** Stage (`generated_cvs/*/<folder>/`) and
  work in place. Never move it back to `awaiting/` and never create a duplicate for the same Job Posting.
- Write `application.md` only when creating the Application. Its body is Thiago's notes: never overwrite or
  edit it afterwards (you may update frontmatter values like `apply_url` if they were wrong). Format:

```markdown
---
company: Awesome Motive
role: AI Engineer
job_url: https://www.linkedin.com/jobs/view/4488830591/
apply_url: https://awesomemotive.com/careers/
created: 2026-11-16
---
```

`company` is the real name with spaces (recruiter name for an undisclosed client; "<poster> (LinkedIn post)"
for an anonymous post). `job_url` is the posting; `apply_url` is the direct apply link, omitted if there is
none (e.g. DM-only). `created` is today's date (ISO). Quote a value with double quotes if it contains `: ` or
starts with a special character. The PDF name is what recruiters see, so it uses the company's real name with spaces
("Thiago Lelis - Awesome Motive.pdf"). If the hiring company is unknown (e.g. an anonymous LinkedIn post),
use the role title instead ("Thiago Lelis - Senior Python Django Engineer.pdf"), never "LinkedIn Post". If a
recruiter posts for an undisclosed client, use the recruiter's name.

## Source of truth

Read `references/master_profile.md` before writing anything. It is the only allowed source of facts about
Thiago. The reason this matters: these CVs go to real employers, and an invented skill or metric that gets
probed in an interview costs him the job. So:

- Never invent experience, years, tools or metrics. If the JD asks for something not in the profile, leave it
  out of the CV and list it as a gap in `job_info.md` (section 6 of the profile lists known gaps).
- Keep the impact metrics: 2 s to 70 ms (96% latency reduction) at Glewee; over 1 billion BRL/day at Luizalabs.
- Castor EDC ended Nov 2026, so no role says "Present" and Castor is described in past tense.
- Postgres, Redis and Kubernetes go in the skills section only. Kubernetes is "developer usage", never DevOps.
- When the user corrects or adds a fact during the session, update `references/master_profile.md` right away
  (and the gaps list), so future runs get it, then regenerate the affected CVs.

## Workflow

### 1. Extract every job description
Fetch all links in parallel. Read `references/extraction.md` for how each source behaves (LinkedIn redirects,
lnkd.in short links, Ashby API behind `?ashby_jid=`, Loxo recruiter pages, ads that point to service pages).
For each job capture: title, company (or recruiter + "client undisclosed"), location/remote/timezone rules,
responsibilities, requirements, nice-to-haves, stack, compensation, how to apply, the direct apply URL, and
whether it is still open.

Some links won't work. Don't stall: finish the rest and report each failure with what the user can do (e.g.
"group post needs login, paste the text"). For a closed posting or one that is clearly not a job, say so and
ask before spending effort on it.

### 2. Research the company (in parallel)
Careers page (values, benefits, hiring steps), about page, values/engineering blog linked from the JD. Only
write facts you read, and label inferences.

### 3. Write the CV (English, Markdown)
Follow the exact structure of `references/examples/cv_example.md`, because `scripts/md2pdf.py` relies on it:
`# Name`, then a bold headline line, then a contact line, then `##` sections, `###` jobs with a `*meta*` line,
`- ` bullets.

Tailoring is surgical, not a rewrite of history:
- **Headline:** "Senior <role-flavored title> | <3-4 JD keywords>".
- **Professional Summary (3-4 sentences):** connect the job's main need to the most relevant experience. AI /
  HealthTech roles → Castor + Areti. High-scale backend / fintech / marketplace → Glewee + Luizalabs.
  Customer-facing / forward-deployed → Areti (scoping, UAT, go-live). Mirror the JD's own terms.
- **Key Technical Skills:** reorder so the JD's languages, tools and concepts come first in each line, and
  the most relevant line is on top.
- **Experience:** keep every job and its dates; reorder bullets so the most relevant come first; bold-label
  the leading phrase of each bullet; drop or shorten bullets that don't serve this job (older jobs can shrink
  to 1-2 bullets).
- Strong action verbs (Architected, Engineered, Owned, Eliminated, Spearheaded), direct and results-oriented.
- Single column, no tables or images, so ATS parsers read it cleanly. Aim for about 1.5-2 pages.

### 4. Render the PDF
```bash
python3 -I .claude/skills/tailor-cv/scripts/md2pdf.py "generated_cvs/awaiting/<folder>/Thiago Lelis - <Company>.md"
```
It writes the PDF next to the .md using headless Chrome/Edge (Windows browser via WSL, or Linux Chromium).
Read one generated PDF to check the layout the first time in a session.

### 5. Write job_info.md and application.md (Portuguese, Markdown)
`job_info.md` follows `references/examples/job_info_example.md`: `# <job title>`, then a bullet list of
`**Key:** value` facts, then `##` sections with `- ` bullets. The board renders it, so keep it valid Markdown.
Sections, in this order:
- Header bullets: Empresa (or recruiter), Local/timezone, contract model, Extraído em (date)
- Links para aplicar: direct apply URL first, then the original link and contacts; explain unusual apply flows
  (DM the poster, Workable "How to Apply" steps, email). For DM-only jobs, add a short ready-to-send message
  in English.
- Sobre a empresa, then O que o time faz / Sobre a vaga, Responsabilidades, Requisitos, Desejável, Stack
- Cultura / valores, Benefícios, Processo seletivo (when known)
- Pontos fortes para destacar: concrete stories from the profile mapped to the JD
- Lacunas / preparação: each gap with a concrete way to prepare, without claiming the skill
- Perguntas para fazer: 3-4 smart questions (always ask salary/contract model and company name if unknown)
- Warnings at the top when relevant: posting closed, job not confirmed, low fit.

Then create `application.md` as described in "The board" above (skip it if the Application already exists).

### 6. Report back (Portuguese)
Reply with:
- A table: job, fit (1-5 ⭐), main strengths, gaps not included in the CV.
- Links that failed and why.
- Anything the user must do before sending (unusual apply flows, unconfirmed postings).
- The folder path.
Keep the per-job interview advice inside each job_info.md rather than repeating it in chat.

## Updating existing CVs
If the user asks to change something across CVs (a new skill, a date, a wording rule): update
`master_profile.md`, edit every affected `generated_cvs/*/*/Thiago Lelis - *.md` (any Stage) (grep for the old text
first so nothing is missed), and re-run `md2pdf.py` on all of them.
