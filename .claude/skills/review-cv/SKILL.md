---
name: review-cv
description: Reviews a generated CV as a skeptical recruiter screening it for its job: finds the red flags that would get it rejected (tenure and gaps, title progression, implausible metrics, missing job requirements, vague or buzzword claims), asks the user for the facts behind each, then fixes the CV through the tailor-cv rules. Use when the user asks to review or critique a CV ("analisar o CV", "revisar"), asks why a recruiter wouldn't hire them, or wants a re-review after changes; tailor-cv also runs it on every CV it generates.
---

# Review CV

Read a CV as the recruiter screening it for one job would: skeptical, short on time, looking for a reason to
reject. Find every **red flag**, and turn each one into a fix grounded in real facts. The CV is a tailor-cv
output: `generated_cvs/<stage>/<folder>/<Name> - <Company>.md` + `.pdf`, with the job in `job_info.md` next to
it and the candidate's facts in `.claude/skills/tailor-cv/references/master_profile.md`.

Two modes:
- **Standalone:** the user asked for a review. Run steps 1-3, then 4-6 as the user answers.
- **After generation:** tailor-cv called it for a CV it just wrote. Run steps 1-2, apply every **wording**
  fix yourself (step 4), and hand back the **questions**, **gaps** and systemic flags (step 5) for
  tailor-cv's report instead of writing step 3's report.

## Steps

1. **Load what the recruiter sees.** Read the PDF's text (`pdftotext -layout "<pdf>" -`), not the .md: line
   wraps, page count and odd characters only show up there. Then read `job_info.md` and the profile.
   Done when: you know every must-have of the job and the profile fact behind each claim in the CV.

2. **Hunt red flags.** Apply every category in [references/red_flags.md](references/red_flags.md). Each flag
   gets: the CV line it comes from, how a recruiter reads it, and one fix type:
   - **wording:** the profile already has what fixes it (rephrase, cut, move, add a profile fact);
   - **question:** only the user knows the fact that fixes it (the story behind a gap, a real title, a number);
   - **gap:** the candidate really lacks it; it becomes interview prep in `job_info.md`, never a CV claim.
   Done when: every category has a verdict (flag or clean) and every flag has a fix type.

3. **Report** in the user's language. Open with the verdict (would you advance this candidate, and why).
   Then the flags, the most likely to cause rejection first. End with the questions, numbered so the user
   can answer by number. On a re-review, start with what was resolved since the last one.

4. **Fix.** Wording fixes follow tailor-cv's "Write the CV" rules; re-render with its `md2pdf.py` and check
   the page count didn't grow. Answers from the user are facts: they go into the profile first, following
   tailor-cv's "Source of truth" (a correction vs an added fact). When a correction also affects other CVs,
   ask which Stages to update: CVs in `applied/` and `closed/` are the record of what was sent.
   Done when: every flag is fixed, answered, or listed as a gap.

5. **Feed back systemic flags.** A flag that comes from the profile or from tailor-cv's rules (a wrong fact,
   a rule that produces self-praise, a title missing its seniority) will come back in the next CV. Propose
   the change to the profile's "Tailoring rules" (or to tailor-cv) and make it once the user agrees.

6. **Re-review** when asked: start again at step 1, reading the new PDF as if for the first time.
