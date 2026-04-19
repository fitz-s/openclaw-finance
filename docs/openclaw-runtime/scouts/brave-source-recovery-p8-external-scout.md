# Brave Source Recovery P8 External Scout

Source review: `/Users/leofitz/Downloads/review 2026-04-18.md`.

External anchors:

- Brave Search API docs: https://api-dashboard.search.brave.com/documentation
- Brave Web Search: https://api-dashboard.search.brave.com/documentation/services/web-search
- Brave News Search: https://api-dashboard.search.brave.com/documentation/services/news-search
- Brave pricing/rate limits: https://api-dashboard.search.brave.com/documentation/pricing

P8 uses a conservative breaker/defer policy. When recent Brave Web/News records indicate quota or rate-limit failures, finance should avoid spending aperture budget on additional live Brave calls until the cooldown expires. Recovery here means preserving future source capacity and producing explicit degradation, not bypassing quota with more calls.
