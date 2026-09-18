# Louter 0.2.9 — opt-in GitHub-only community savings

- Optional public aggregate reporting, OFF by default. Existing users are not opted in by an upgrade or install.sh --yes.
- Public reports are tied to the sender's GitHub username; the consent prompt explicitly says this is not anonymous.
- Preview, on, off, status, send and withdraw commands; daily profile-specific user timer or manual reporting.
- Strict numeric allowlist: no prompts, answers, sessions, model names, local paths or provider credentials.
- Durable cumulative checkpoints, retry deduplication, stats-reset handling and account-change checks.
- GitHub Actions aggregates current reports roughly hourly onto a public community-stats branch, with a rendered README dashboard, JSON and an optional GitHub Pages-ready HTML dashboard.
- No Cloudflare, external collector, shared publisher token or third-party analytics.
- No assumed dollar prices: token totals and any gross API-equivalent estimate are explicitly counterfactual and self-reported, not verified net savings.
- Routing implementation is unchanged.

Validation: 34 existing JavaScript tests, 37 telemetry/client/collector tests, installer regressions, CLI no-consent checks, and the packaged-artifact audit are included in CI. Real client reporting still requires each participant's explicit opt-in and working gh login.

[Public totals](https://github.com/liseman/openclaw-louter/tree/community-stats) · [Opt-in instructions and privacy](https://github.com/liseman/openclaw-louter/blob/main/community/README.md)

This is a GitHub release. ClawHub publication is a separate registry operation.
