# ADR 0003 and glossary entry for Time in Stage

Status: resolved

See `../spec.md`, section "Docs".

## Acceptance

- `docs/adr/0003-*.md`: explains keeping only the last entry per Stage (fits the flat frontmatter, and moving
  back is rare) and clearing later Stages' timestamps on move (otherwise moving back leaves stale or negative
  durations).
- `GLOSSARY.md`: **Time in Stage** (PT: Tempo na etapa), defined as how long an Application has been, or was, in
  a Stage, measured from its last entry into it.
