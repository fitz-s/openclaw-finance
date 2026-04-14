# IBKR Web API integration

## Current source policy

- Daily unattended holdings baseline should use IBKR Flex Web Service.
- Client Portal Web API is now a manual/snapshot recovery path, not the primary scheduled holdings source.
- Downstream finance scripts should consume `state/portfolio-resolved.json` and `state/held-tickers-resolved.json`, not raw `portfolio.json`.
- Resolver priority:
  1. fresh Client Portal snapshot, when explicitly available
  2. fresh Flex baseline
  3. unavailable/fail-closed state

## Flex Web Service

- Token source: Keychain id `ibkr_flex_web_token` or env `IBKR_FLEX_TOKEN`.
- Query id source: `finance/state/ibkr-flex-config.json` field `activity_query_id` or env `IBKR_FLEX_ACTIVITY_QUERY_ID`.
- Example config template: `finance/ops/ibkr-flex-config.example.json`.
- Fetcher: `scripts/portfolio_flex_fetcher.py`.
- Resolver: `scripts/portfolio_resolver.py`.
- Scheduled path: system crontab runs Flex fetcher and then resolver at 08:00 and 16:00 on weekdays.
- If Flex token/query id is missing or stale, resolver writes unavailable state and downstream alerts fail closed.

## Client Portal Web API

- Source API: IBKR Web API / Client Portal Web API.
- Read-only use case: accounts, positions, trades, P&L, allocation.
- Auth/session flow:
  1. User logs into IBKR Client Portal / Gateway in browser.
  2. Validate SSO with `/sso/validate`.
  3. Initialize brokerage session with `/iserver/auth/ssodh/init`.
  4. Keep session alive with `/tickle`.
  5. Read data from `/portfolio/accounts`, `/portfolio/{accountId}/positions`, `/iserver/account/trades`, etc.
- In this workspace, `ibkr_tickle.py` should run every 5 minutes to avoid CPAPI session expiry. Scripts that need brokerage data should still call `ibkr_reader.ensure_session()` so they can recover when SSO is valid but `iserver/auth/status` has dropped.
- Local connector script: `ops/scripts/ibkr_reader.py`.
- Cookie/session cache file: `life/context/ibkr-cookie.json`.
