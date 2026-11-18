---
name: tailor-cv
description: Generates tailored, ATS-optimized English CVs (Markdown + PDF) for the user from job posting links, plus a job_info.md with the apply link, company/culture research and interview prep, and an application.md that tracks the Application on the TailorCV board, saved in generated_cvs/awaiting/<date>_<Company>_<Role>/. On first use it builds the user's master profile with them. Use this whenever the user pastes one or more job links (LinkedIn, lnkd.in, Ashby, Greenhouse, Lever, Loxo, careers pages, even a WhatsApp-style list of links) or a job description and wants a CV/resume/currículo for it, asks to "gerar currículo", "adaptar CV", "abrir os links das vagas", wants to set up or update their profile, or wants to regenerate existing CVs after a change to their profile.
---

# Tailor CV

Turn job links into ready-to-send application packages for the user. All facts about the candidate come from
`references/master_profile.md`. In this file, `<Name>` is the short name the profile sets for file names
(section 1). One folder per Application:

```
generated_cvs/awaiting/<YYYY-MM-DD>_<CompanyNoSpaces>_<Role-With-Hyphens>/
├── <Name> - <Company>.md     # CV source
├── <Name> - <Company>.pdf    # CV to send
├── job_info.md               # apply link + company research + interview prep (Portuguese)
└── application.md            # the Application: frontmatter + the user's own notes
```

The date is today's date. If that folder name already exists in any Stage (a Closed Application being
pursued again on the same day), append `-2`, `-3`, … so the board can later move it without a name clash.

## 0. The profile (first run)

`references/master_profile.md` holds the user's real data, so it is gitignored and each clone starts without
one. If it is missing, or still has `<placeholders>`, build it before generating any CV:

1. Copy `references/master_profile.template.md` to `references/master_profile.md`.
2. Ask the user for their current CV, LinkedIn profile PDF, or any text about their career, and read it.
3. Fill every section from what they gave you. Ask about anything missing that a CV needs: contact details
   (LinkedIn included), dates, the short name for file names, and which tools they used where. Dig for the
   material the writing rules in step 3 of the workflow need, because CVs can't be stronger than the profile:
   - **Real metrics** for every job: before → after, volume, time or money saved, people or clients served.
     Ask about each job by name; estimates the user stands behind ("~40%", "10+ clients") are fine.
   - **Own initiatives:** which projects they proposed themselves, not just built.
   - **Soft skills and personal traits**, each with the job or project that proves it.
4. Never invent anything to fill a gap: leave the item out or ask. The profile is only as good as its facts.
5. Show a summary of the profile and ask for corrections before going on to the job links.

Never copy profile data into a tracked file (this skill, the examples, the README, tests).

## The board (Stages are folders)

`python3 board.py` serves a Kanban board over `generated_cvs/` (see `GLOSSARY.md` and `docs/adr/`). Each
Stage is a folder: `awaiting/`, `applied/`, `in-process/`, `offer/`, `closed/`. The board moves Application
folders between them, so:

- A **new** Application always goes in `generated_cvs/awaiting/`.
- To regenerate or update an existing one, find its folder in **any** Stage (`generated_cvs/*/<folder>/`) and
  work in place. Never move it back to `awaiting/`.
- Never create a **Duplicate Application**: a new one for a Job Posting that already has an Application not
  in `closed/` (see `GLOSSARY.md`). Check with `python3 board.py --check <url> [<url> ...]`, passing every
  link you know for the posting. Exit 0 means no open Application. Exit 1 prints the one that blocks it
  (`<stage>/<folder>  <company> — <role>`). A Closed Application does not block: pursuing the posting again
  creates a new one. Regenerating an existing Application on request is not creating, so it skips the check.
- Write `application.md` only when creating the Application. Its body is the user's notes: never overwrite or
  edit it afterwards (you may update frontmatter values like `apply_url` if they were wrong). Format:

```markdown
---
company: Awesome Motive
role: AI Engineer
job_url: https://www.linkedin.com/jobs/view/4488830591/
apply_url: https://awesomemotive.com/careers/
created: 2026-11-16
fit: 4
---
```

`company` is the real name with spaces (recruiter name for an undisclosed client; "<poster> (LinkedIn post)"
for an anonymous post). `job_url` is the posting itself, never a listing page like `company.com/jobs` (if a
listing page is the only link you have, keep it, but that posting can no longer be matched as a duplicate);
`apply_url` is the direct apply link, omitted if there is
none (e.g. DM-only). `created` is today's date (ISO). `fit` is the same 1-5 fit you report in the chat table (step 6), as a bare
integer: the board shows it as stars on the card, so the two must match. When regenerating changes your
assessment, update `fit` too. Quote a value with double quotes if it contains `: ` or
starts with a special character. The PDF name is what recruiters see, so it uses the company's real name with
spaces ("<Name> - Awesome Motive.pdf"). If the hiring company is unknown (e.g. an anonymous LinkedIn post),
use the role title instead ("<Name> - Senior Python Django Engineer.pdf"), never "LinkedIn Post". If a
recruiter posts for an undisclosed client, use the recruiter's name.

## Source of truth

Read `references/master_profile.md` before writing anything. It is the only allowed source of facts about
the candidate, contact details included. The reason this matters: these CVs go to real employers, and an
invented skill or metric that gets probed in an interview costs them the job. So:

- Never invent experience, years, tools or metrics. If the JD asks for something not in the profile, leave it
  out of the CV and list it as a gap in `job_info.md` (the profile's "Known gaps" section lists known ones).
- Apply every rule in the profile's "Tailoring rules" section (metrics to keep, which experience to lead
  with, wording limits).
- When the user corrects or adds a fact during the session, update `references/master_profile.md` right away
  (and the gaps list), so future runs get it.
  - A **correction** (wrong date, wrong claim, a skill they don't have) makes existing CVs wrong: regenerate every
    CV that contains it (see "Updating existing CVs").
  - An **added fact** is new material in the profile, which is a pool each CV picks from by relevance. Put it
    in the CV you are working on only if it serves that job (it matches the JD's terms, which raises the ATS
    ranking), and leave earlier CVs alone. Don't offer to add it to them either; the user will ask if they
    want that.

## Workflow

### 1. Extract every job description
First resolve `lnkd.in` short links and run `python3 board.py --check` on each pasted link. A link that hits an
open Application gets nothing more: no fetching, no files. Then, after extraction, run `--check` again per
posting with every link you learned for it (the pasted link, the resolved LinkedIn target, the ATS `jobUrl`,
the apply URL). That catches the same posting reached through another source, e.g. a LinkedIn job whose apply
link is an Ashby posting that already has an Application. Stop there for that posting too.

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
Follow the exact structure of `references/examples/cv_example.md` (a fictional candidate: copy its shape,
never its content), because `scripts/md2pdf.py` relies on it: `# Name`, then a bold headline line, then a
contact line, then `##` sections, `###` jobs with a `*meta*` line, `- ` bullets.

Every CV must rank well in ATS checkers, whatever the job, fit or seniority. The rules below are what those
checkers reward, so apply all of them every time: none is optional for a "simple" or low-fit job. The only
choice is which profile facts to use, judged by the JD's own terms (that keyword match is itself what ATS
ranking scores).

Tailoring is surgical, not a rewrite of history:
- **Headline:** "<Seniority> <role-flavored title> | <3-4 JD keywords>".
- **Contact line:** location · phone · email · LinkedIn (`linkedin.com/in/...`) as plain text; the renderer
  makes them clickable. ATS checkers look for all four.
- **Professional Summary (3-5 sentences):** connect the job's main need to the most relevant experience
  (the profile's tailoring rules say which experience fits which kind of role). Mirror the JD's own terms.
  Implied first person, no "I"/"my" ("At Acme, built..."): resume convention, and ATS checkers flag pronouns.
  Close with one sentence of the profile's personal traits, each tied to its evidence ("proactive" next to an
  initiative they proposed), so the traits read as facts rather than a list of adjectives.
- **Section names:** keep the standard ones ATS parsers recognize: Professional Summary, Key Technical
  Skills, Professional Experience, Education, Languages. Don't merge them ("Education & Languages").
- **Key Technical Skills:** reorder so the JD's languages, tools and concepts come first in each line, and
  the most relevant line is on top.
- **Experience:** keep every job and its dates; reorder bullets so the most relevant come first; bold-label
  the leading phrase of each bullet; drop or shorten bullets that don't serve this job (older jobs can shrink
  to 1-2 bullets).
- **Measurable achievements:** at least 5 per CV, each a real number from the profile (before → after,
  volume, time saved). When the profile has fewer than 5, ask the user for real numbers before writing;
  ATS checkers and recruiters both count them.
- **Soft skills:** where a bullet is the evidence for one of the profile's soft skills, use the skill's name as
  the bullet label (**Stakeholder Communication:**, **Technical Leadership:**, **Cross-Functional
  Collaboration:**), so ATS checkers find the skill and recruiters see the proof beside it.
- **Own initiatives:** a project the profile marks as the candidate's own initiative opens with the verbs that
  show it ("Proposed to the logistics team, architected and built..."). It is the strongest proof of a
  proactive trait.
- Strong action verbs (Architected, Engineered, Owned, Eliminated, Spearheaded), direct and results-oriented.
- Single column, no tables or images, so ATS parsers read it cleanly. Aim for about 1.5-2 pages.

### 4. Render the PDF
```bash
python3 -I .claude/skills/tailor-cv/scripts/md2pdf.py "generated_cvs/awaiting/<folder>/<Name> - <Company>.md"
```
It writes the PDF next to the .md using headless Chrome/Edge (Windows browser via WSL, or Linux Chromium),
then reads it back like an ATS does: it fails if any text line was written in pieces (simple parsers read
those as spaces inside words) or if `pdftotext` can't find the email, phone, LinkedIn or every `##` heading.
Fix a FAIL before handing the CV over; don't loosen the CSS rules the script documents. Read one generated
PDF to check the layout the first time in a session.

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
- A table: job, fit (1-5 ⭐, the `fit` saved in `application.md`), main strengths, gaps not included in the CV.
- Links that failed and why.
- Links blocked as Duplicate Applications, each with the existing Application's Stage, company, role and folder
  path, and a note that the user can ask to regenerate it if that is what they meant.
- Anything the user must do before sending (unusual apply flows, unconfirmed postings).
- The folder path.
Keep the per-job interview advice inside each job_info.md rather than repeating it in chat.

## Updating existing CVs
If the user asks to change something across CVs (a new skill, a date, a wording rule): update
`master_profile.md`, edit every affected `generated_cvs/*/*/<Name> - *.md` (any Stage) (grep for the old text
first so nothing is missed), and re-run `md2pdf.py` on all of them.
