# Louter 0.2.0 — Lite Router for OpenClaw

**Keep the easy stuff local. Ask your models when it matters.**

A lightweight local reply path can finish simple turns before the normal OpenClaw agent is invoked. Harder requests continue to the existing main agent. No proxy subscription and no new cloud-provider credentials are required by Louter.

## Included

- Automatic local-first replies with a five-second default local budget.
- Configurable explicit routes, including local-only handling without cloud fallback.
- Ask Around: concurrent model answers, local-first synthesis, partial-result reporting, and retained original responses.
- Conversation-scoped `details` retrieval without new model calls.
- Persistent usage counters and opt-in API-equivalent pricing estimates.
- Setup helpers, a permission-aware installer, and quiet smoke-test summaries.

## Release status

Preview release targeting OpenClaw 2026.9.4. The 28 offline code/transport/storage tests and two simulated installer tests passed in the packaging environment. This release has not been run against live model accounts in that environment. Run the supplied live smoke test on the target host.

Explicit prefixes and panels are text-only, current-request completions without normal agent tools/history. `local:` is a model-routing boundary, not an assurance that messaging channels or other plugins are offline. Savings figures are estimates, not reductions in a ChatGPT subscription bill.

Package: `@liseman/openclaw-louter` · Runtime plugin ID: `louter` · License: MIT
