# Louter 0.2.10 — community dashboard release

- Includes the opt-in, GitHub-only community savings reporting introduced in 0.2.9.
- Deploys the richer community savings dashboard through GitHub Pages using the official Pages Actions flow.
- Dashboard starts with an editable API-equivalent reference price of $4/M input tokens and $20/M output tokens; values stay in the visitor's browser and can be changed.
- Public reporting remains OFF by default and requires explicit consent plus the participant's own GitHub login.
- Reports contain aggregate allowlisted counters only—no prompts, answers, sessions, model names, local paths or provider credentials.
- Estimates remain explicitly counterfactual/self-reported rather than verified or net cloud-bill savings.
- Routing behavior is unchanged.

Validation: JavaScript tests, telemetry/client/collector tests, installer regressions, CLI no-consent checks and packaged-artifact audit run before release.

[Live savings dashboard](https://liseman.github.io/openclaw-louter/) · [Public source data](https://github.com/liseman/openclaw-louter/tree/community-stats) · [Opt-in instructions and privacy](https://github.com/liseman/openclaw-louter/blob/main/community/README.md)

GitHub and ClawHub publication are separate registry operations.
