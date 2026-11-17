# Show Time in Stage on cards and in the detail panel

Status: resolved
Blocked by: 01

See `../spec.md`, sections "Calculation" and "UI".

## Acceptance

- Cards in Awaiting, Applied and In Process show the time in the current Stage ("today" / "N d").
- The detail panel shows the time in each Stage and the metrics Applied → response and Applied → Offer, plus
  "no response · closed after N d" when the Application was closed from Applied.
- Missing timestamps show "—". Date-only values (`YYYY-MM-DD`) parse as midnight local time.
- Strings exist in both EN and PT.
