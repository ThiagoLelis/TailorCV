# TailorCV

A personal, self-hosted tool to generate tailored CVs for job postings and track each application through to its outcome.

## Language

**Job Posting** (PT: Vaga):
A position advertised by a company or recruiter, identified by its link.
_Avoid_: Job, opening, role (when meaning the posting itself)

**Application Package** (PT: Pacote):
The documents generated for one Job Posting: tailored CV, optional cover letter, and the job info sheet with research and interview prep.
_Avoid_: CV folder, output, generated CV (when meaning the whole set)

**Application** (PT: Candidatura):
The candidate's pursuit of one Job Posting, from the moment its Application Package exists until it ends. A Job Posting has at most one Application; regenerating the Package does not create a new one.
_Avoid_: Card, ticket, job, task

**Stage** (PT: Etapa):
Where an Application currently stands. Exactly one of: Awaiting Application, Applied, In Process, Offer, Closed.
_Avoid_: Status, column, phase

**Awaiting Application** (PT: Esperando aplicação):
The Stage of an Application whose Package exists but has not been sent.

**Applied** (PT: Aplicado):
The Stage of an Application that was sent and has had no response.

**In Process** (PT: Em processo):
The Stage of an Application with any contact from the company: recruiter screen, interviews, technical test.

**Offer** (PT: Oferta):
The Stage of an Application that received an offer.

**Closed** (PT: Encerrado):
The final Stage of an Application that ended without proceeding, always with a reason: rejected, withdrawn, or posting closed.
_Avoid_: Rejected (it is only one of the reasons)

**Time in Stage** (PT: Tempo na etapa):
How long an Application has been, or was, in a Stage, measured from its last entry into that Stage. Offer and Closed are done Stages, so no running time is shown for them.
_Avoid_: Age, duration (when meaning time in one Stage)
