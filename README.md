# Louter community savings

**Opt-in, public, self-reported statistics. Not verified reductions in cloud bills.**

Updated: 2026-09-21T06:55:49+00:00

| Metric | Total |
|---|---:|
| Participating installations | 2 |
| Reports updated within 30 days | 2 |
| Locally completed direct turns | 11 |
| Estimated input tokens avoided | 165,000 |
| Estimated output tokens avoided | 1,650 |
| Main-agent handoffs | 36 |
| Cloud calls attempted / completed | 34 / 17 |
| Ask Around runs | 7 |
| Local answers after cloud failures | 0 |

## What these numbers mean

Local answers are direct local completions, not a count of proven avoided cloud API requests. Token totals use each client's configured counterfactual assumptions. The main agent might itself be local. Ask Around and failure fallbacks are separate counters and do not inflate avoided-turn estimates.

**No default dollar claim.** For assumed prices I and O in USD per million tokens: `gross API-equivalent estimate = input_tokens / 1,000,000 * I + output_tokens / 1,000,000 * O`. This excludes cloud/panel costs, caching, electricity and subscriptions; it is not net savings.

Retries replace one cumulative installation snapshot. Stats resets are handled by the client's durable checkpoint. Reports are linked to public GitHub accounts and may be inaccurate or fabricated; this is not independently verified adoption or cost data.

## Data and controls

[Machine-readable totals](totals.json) · [Latest accepted reports](reports.json) · [Setup and privacy](https://github.com/liseman/openclaw-louter/blob/main/community/README.md)

Telemetry is disabled by default. Turning it off stops new uploads but leaves previously shared data. Withdraw or close a report to remove it from current totals on the next rebuild. Git history, issue edit history and third-party copies may remain.

Excluded installations: 0. Rejected malformed reports: 0.
