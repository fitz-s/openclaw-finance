# SEC Fallback Activation P9 External Scout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

External anchors:

- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC current filings Atom endpoint: https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&output=atom
- SEC data submissions endpoint pattern: https://data.sec.gov/submissions/CIK##########.json

Scout note:

- Local unauthenticated `curl -I` to SEC endpoints returned `403` in this environment. P9 must treat SEC as a zero-credential fallback lane that can explicitly degrade, not as guaranteed source yield.
- SEC records should be metadata-only and should not create wake/judgment authority by themselves.
