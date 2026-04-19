# Exchange Calendar Provider P6 External Scout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

External anchors:

- NYSE official hours and calendars: https://www.nyse.com/markets/hours-calendars
- NYSE Group 2025/2026/2027 holiday and early closings calendar: https://www.businesswire.com/news/home/20241108580933/en/NYSE-Group-Announces-2025-2026-and-2027-Holiday-and-Early-Closings-Calendar
- NYSE Group 2026/2027/2028 holiday and early closings calendar mirror: https://www.morningstar.com/news/business-wire/20251223981478/nyse-group-announces-2026-2027-and-2028-holiday-and-early-closings-calendar

P6 uses committed deterministic calendar tables for 2026-2028 rather than runtime network lookup or a new dependency. This keeps report/scanner guards reproducible and reviewer-visible.
