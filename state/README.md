# State (v2)

Purpose: local, auditable state for 24/7 finance scanning, duplicate suppression, and report routing.

## State responsibilities
The finance state should help the system:
- remember what was already seen
- remember what was already sent
- accumulate useful observations
- avoid duplicate alerts
- decide when enough information exists for a short report or core report

## Suggested tracked items
- last scan time by mode/window
- last short-report send time
- last core-report send time
- seen news ids / hashes
- seen filing ids
- active themes
- accumulated observations
- last major-event signature
- last report paths
- gate thresholds / policy config
- fallback events and failure notes
- last delivered conclusion signature

## Windows (America/Chicago)
- overnight: 19:00–03:30
- pre: 03:30–08:30
- open: 08:30–11:30
- mid: 11:30–14:00
- late: 14:00–15:00
- post: 15:00–19:00

## Dedup Rules
- Same event should not trigger repeated alerts unless the situation materially changes.
- Repeated headlines with no new conclusion should be suppressed.
- During market hours, short reports should be spaced by accumulated signal, not by every tiny change.

## Routing Rules
- Urgent + important events may break accumulation and alert immediately.
- Non-urgent items should accumulate toward the next short report or core report.
- Core reports should synthesize rather than replay every headline.
