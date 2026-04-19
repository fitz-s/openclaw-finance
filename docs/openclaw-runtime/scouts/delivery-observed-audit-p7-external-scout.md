# Delivery Observed Audit P7 External Scout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

External anchors:

- Discord rate limits: https://docs.discord.com/developers/topics/rate-limits
- Discord webhook execution: https://docs.discord.com/developers/resources/webhook

Relevant findings:

- Discord can return HTTP 429 with `Retry-After` / `retry_after`; delivery systems need observed success/failure telemetry, not just scheduled-send intent.
- Discord webhook execution with `wait=true` can return created-message confirmation. Even when OpenClaw owns delivery, finance should distinguish scheduled report generation from observed delivery success in parent run logs.
