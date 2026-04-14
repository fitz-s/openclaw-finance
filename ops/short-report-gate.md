# Finance Short-Report Gate (v1)

## Rule
If the scan decision is "continue observing / do not send a standalone brief", the system must:
1. write into local state / buffer
2. not send a message
3. wait for the next round and continue accumulating

## Only send when one of these is true
- major sudden event / regime shift
- accumulated observations cross threshold
- scheduled rollup window is reached
- there is enough new conclusion versus the last delivered report

## Architecture
### Scan jobs
- read sources
- score observations
- update buffer/state
- record model fallback when it occurs
- do **not** announce externally by default

### Delivery jobs
- read accumulated state
- read `finance/state/intraday-gate-config.json`
- decide whether send conditions are satisfied
- send only when the gate is passed

## Delivery suppression rule
Text such as:
- continue scanning
- continue observing
- not enough to send
- hold for short report
- accumulate-no-send
must remain internal state and must never be delivered as user-facing output.

## Model routing
- primary: `google-gemini-cli/gemini-3-flash-preview`
- fallback: `minimax/MiniMax-M2.7`
- if fallback occurs, log it into state / maintenance notes
