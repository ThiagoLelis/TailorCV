# TailorCV

A personal, self-hosted tool to generate tailored CVs for job postings and track each application through to its outcome.

## Language

**Job Posting** (PT: Vaga):
A position advertised by a company or recruiter. One Job Posting can be reached through several links (careers page, applicant tracking system, LinkedIn); links that cannot be shown to lead to the same position are distinct Job Postings, even at the same company with a similar role.
_Avoid_: Job, opening, role (when meaning the posting itself)

**Application Package** (PT: Pacote):
The documents generated for one Job Posting: tailored CV, optional cover letter, and the job info sheet with research and interview prep.
_Avoid_: CV folder, output, generated CV (when meaning the whole set)

**Application** (PT: Candidatura):
The candidate's pursuit of one Job Posting, from the moment its Application Package exists until it ends. A Job Posting has at most one Application that is not Closed; regenerating the Package does not create a new one, but pursuing a Job Posting again after its Application was Closed does.
_Avoid_: Card, ticket, job, task

**Duplicate Application** (PT: Candidatura duplicada):
An Application for a Job Posting that already has one that is not Closed. It is never created.
_Avoid_: Duplicate card, repeated job

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

**Fit** (PT: Fit / Aderência):
How well the candidate matches a Job Posting, from 1 (poor) to 5 (strong), judged when the Application Package is generated and shown as stars on the board.
_Avoid_: Score, match, rating

**Time in Stage** (PT: Tempo na etapa):
How long an Application has been, or was, in a Stage, measured from its last entry into that Stage. Offer and Closed are done Stages, so no running time is shown for them.
_Avoid_: Age, duration (when meaning time in one Stage)

**Board Order** (PT: Ordem no board):
The order of the Applications within one Stage's column: by Fit (highest first, newest first within a Fit), except for Applications the user placed by hand on the board, which stay where they were put across reloads.
_Avoid_: Priority, rank (the order carries no meaning beyond the user's own arrangement)
