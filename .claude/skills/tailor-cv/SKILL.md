---
name: tailor-cv
description: Generates tailored, ATS-optimized English CVs (Markdown + PDF) for Thiago Lelis from job posting links, plus a vaga_info.txt with the apply link, company/culture research and interview prep, saved in generated_cvs/<date>_<Company>_<Role>/. Use this whenever the user pastes one or more job links (LinkedIn, lnkd.in, Ashby, Greenhouse, Lever, Loxo, careers pages, even a WhatsApp-style list of links) or a job description and wants a CV/resume/currículo for it, asks to "gerar currículo", "adaptar CV", "abrir os links das vagas", or wants to regenerate existing CVs after a change to his profile.
---

# Tailor CV

Turn job links into ready-to-send application packages for **Thiago Lelis dos Santos**. One folder per job:

```
generated_cvs/<YYYY-MM-DD>_<CompanyNoSpaces>_<Role-With-Hyphens>/
├── Thiago Lelis - <Company>.md     # CV source
├── Thiago Lelis - <Company>.pdf    # CV to send
└── vaga_info.txt                   # apply link + company research + interview prep (Portuguese)
```

The date is today's date. The PDF name is what recruiters see, so it uses the company's real name with spaces
("Thiago Lelis - Awesome Motive.pdf"). If the hiring company is unknown (e.g. an anonymous LinkedIn post),
use the role title instead ("Thiago Lelis - Senior Python Django Engineer.pdf"), never "LinkedIn Post". If a
recruiter posts for an undisclosed client, use the recruiter's name.

## Source of truth

Read `references/master_profile.md` before writing anything. It is the only allowed source of facts about
Thiago. The reason this matters: these CVs go to real employers, and an invented skill or metric that gets
probed in an interview costs him the job. So:

- Never invent experience, years, tools or metrics. If the JD asks for something not in the profile, leave it
  out of the CV and list it as a gap in `vaga_info.txt` (section 6 of the profile lists known gaps).
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
python3 -I .claude/skills/tailor-cv/scripts/md2pdf.py "generated_cvs/<folder>/Thiago Lelis - <Company>.md"
```
It writes the PDF next to the .md using headless Chrome/Edge (Windows browser via WSL, or Linux Chromium).
Read one generated PDF to check the layout the first time in a session.

### 5. Write vaga_info.txt (Portuguese, plain text)
Follow `references/examples/vaga_info_example.txt`. Sections, in this order:
- Header: VAGA, EMPRESA (or recruiter), LOCAL/timezone, contract model, EXTRAÍDO EM (date)
- LINKS PARA APLICAR: direct apply URL first, then the original link and contacts; explain unusual apply flows
  (DM the poster, Workable "How to Apply" steps, email). For DM-only jobs, add a short ready-to-send message
  in English.
- SOBRE A EMPRESA, then O QUE O TIME FAZ / SOBRE A VAGA, RESPONSABILIDADES, REQUISITOS, DESEJÁVEL, STACK
- CULTURA / VALORES, BENEFÍCIOS, PROCESSO SELETIVO (when known)
- PONTOS FORTES PARA DESTACAR: concrete stories from the profile mapped to the JD
- LACUNAS / PREPARAÇÃO: each gap with a concrete way to prepare, without claiming the skill
- PERGUNTAS PARA FAZER: 3-4 smart questions (always ask salary/contract model and company name if unknown)
- Warnings at the top when relevant: posting closed, job not confirmed, low fit.

### 6. Report back (Portuguese)
Reply with:
- A table: job, fit (1-5 ⭐), main strengths, gaps not included in the CV.
- Links that failed and why.
- Anything the user must do before sending (unusual apply flows, unconfirmed postings).
- The folder path.
Keep the per-job interview advice inside each vaga_info.txt rather than repeating it in chat.

## Updating existing CVs
If the user asks to change something across CVs (a new skill, a date, a wording rule): update
`master_profile.md`, edit every affected `Thiago Lelis - *.md` under `generated_cvs/` (grep for the old text
first so nothing is missed), and re-run `md2pdf.py` on all of them.
