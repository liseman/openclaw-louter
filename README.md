# Louter — Lite Router for OpenClaw

**Keep the easy stuff local. Ask your models when it matters.**

Louter adds a lightweight local path before the normal OpenClaw agent. Explicit routes let you choose a model; `ask around:` collects multiple answers and synthesizes them. Ordinary requests that need tools, current information or more context continue to your main agent.

**New in 0.2.9: [opt-in, GitHub-only community savings](community/README.md).**
[Public totals dashboard](https://github.com/liseman/openclaw-louter/tree/community-stats) · [Privacy and opt-in instructions](community/README.md) · [Release notes](community/RELEASE_NOTES.md)

This project targets the OpenClaw interfaces tested on 2026.9.4. Model names in examples are configurable routes from the tested installation, not a promise of public availability or access to those models.

## Install and setup

GitHub releases and ClawHub publication are separate. Check the registry for the version actually published there:

```bash
clawhub package inspect @liseman/openclaw-louter
```

For the default OpenClaw profile, install the latest registry version and run its setup:

```bash
openclaw plugins install 'clawhub:@liseman/openclaw-louter' --accept-capabilities && ~/.openclaw/extensions/louter/install.sh
```

If OpenClaw reports a different installation path, run `install.sh` from the path shown by `openclaw plugins inspect louter`. The installer targets Linux systemd-user hosts. Run as the OpenClaw user, not root. Do not assume a second profile is isolated from system services merely because it has another state directory.

The installer asks for conversation-hook and configured-model permissions, preserves ClawHub-managed provenance, checks the package, offers route/model discovery, and runs bounded smoke tests. It can reuse local Qwen or offer a model download through an **existing** Ollama runtime. It does not silently install operating-system runtimes, drivers or sudo packages. Cloud routes still require working authentication and correctly configured workers; catalog discovery is not a successful model invocation.

`install.sh --yes` approves ordinary setup, **not public telemetry**. `--skip-smoke` avoids live model tests; `--no-restart` skips restarting and live tests. Full diagnostics remain local.

For just route discovery, from the installed package:

```bash
python3 scripts/setup.py
```

## Use it

| Message | Behavior |
|---|---|
| `What is a hexagon?` | Try local; hand back to the main agent when needed. |
| `Research the latest ...` | Go directly to the main agent. |
| `local: explain this sentence` | Local text completion; no cloud fallback on error. |
| `astra: critique this idea` | Call the configured Astra worker. |
| `claude: give a second opinion` | Call the configured Claude worker. |
| `ask around: compare these approaches` | Query configured routes concurrently, then synthesize. |
| `ask around --details claude: ...` | Include that model's retained original response. |
| `details claude` / `details all` | Retrieve originals from this conversation without another model call. |
| `details claude RUN-ID --page 2` | Retrieve a later page from a retained panel. |
| `savings` / `savings today` / `savings week` / `savings month` | Local counters and labeled estimates. |
| `louter routes` / `louter status` / `louter help` | Show configuration and help without a model call. |

Explicit routes and panels are **current-message, text-only completions**. They have no browsing, account access, file tools or conversation history. Paste the evidence needed for the answer. Use an unprefixed request for the main agent's tools/history. A model panel is not independent verification, and agreement is not a confidence score.

Worker-backed cloud routes use `api.runtime.subagent.complete()` without a model override. Routes without `agentId` retain the `llm.complete()` compatibility path. The tested Claude worker pins the model-scoped `claude-cli` runtime; that requires Claude Code installed and authenticated on the gateway host. Worker model labels are configured attribution, not independently verified provider receipts.

## Configure routes

Settings live under `plugins.entries.louter.config`; see [the example](config.example.json) and [schema](openclaw.plugin.json). From the installed package:

```bash
python3 scripts/louterctl.py routes list
python3 scripts/louterctl.py routes add reviewer anthropic/claude-opus-5
python3 scripts/louterctl.py panel local astra reviewer
python3 scripts/louterctl.py synthesizer local --fallback astra
python3 scripts/louterctl.py timeout 5
python3 scripts/louterctl.py fallback --off
```

Aliases, models and panel membership are user-changeable. `routes add` can update an alias. Route configuration does not supply missing provider credentials. Model permission changes require approval. An unknown explicit alias produces an error instead of silently choosing a cloud model.

The default automatic local deadline is five seconds. Ask Around defaults to a 45-second overall budget, with per-model limits and local-first synthesis. Configure `fallbackSynthesizer: null` to prohibit cloud synthesis. Deadline cancellation limits how long Louter waits; it cannot prove that a remote provider stopped computing or billing.

For configured cloud execution failures, Louter can retry locally with a visible notice. The failed cloud result remains attributed as failed; a shared local panel answer is not counted as an additional independent model vote. Content refusals are not rewritten or intentionally bypassed. Failure codes and handling are explicit in the configuration and tests.

Original panel responses, including partial results, are kept separately from synthesis and scoped to the conversation. Default retention is seven days; long originals are paginated. Incomplete synthesis does not deliberately discard completed model answers.

## Local privacy boundary

Within an active Louter hook, `local:` uses a loopback-only HTTP inference endpoint. It does not use environment HTTP proxies or follow redirects, and it does not fall through to a cloud model after failure. `localhost` is normalized to literal loopback before the runtime request.

This is **not an end-to-end offline/privacy guarantee**: message channels may already transmit content, OpenClaw may retain transcripts, other plugins may observe turns, and the local inference server itself must be trusted not to proxy externally. Disabled or blocked hooks cannot enforce routing. Available attachment metadata is checked, but the host does not guarantee a complete media inventory on every channel. Verify activation with `louter ping`.

## Savings: local and community

`savings` shows local counters, main-agent handoffs, attempted/completed cloud calls and estimated avoided input/output tokens. Estimates are assumptions, not measured counterfactual model usage. A local turn might otherwise have used another local model. Dollar rates are unset by default; estimates are not net savings, changes to subscription bills, or independently measured compute reductions. Ask Around and failure-fallback costs must not be mistaken for savings.

**Optional public reporting is OFF by default.** It uses the participant's existing GitHub CLI login to update one public issue per installation/profile. Reports reveal the GitHub username and submission/edit timestamps. They are not anonymous. The payload contains only a random installation ID, version/date/sequence and allowlisted cumulative counters—no prompts, answers, sessions, model names, local paths or provider credentials.

```bash
python3 scripts/louterctl.py telemetry preview
python3 scripts/louterctl.py telemetry on
python3 scripts/louterctl.py telemetry send
python3 scripts/louterctl.py telemetry status
python3 scripts/louterctl.py telemetry off
python3 scripts/louterctl.py telemetry withdraw
```

`on` has separate explicit consent; `off` stops new uploads. `withdraw` excludes the report from current totals after the next rebuild but cannot erase public history or third-party copies. Automatic reporting uses an optional profile-specific systemd user timer; `on --manual` needs no timer. Preview/status perform no network requests. Ordinary installation approval never enables telemetry.

The GitHub collector rebuilds the public `community-stats` branch roughly hourly. The rendered README dashboard works without GitHub Pages; a static HTML dashboard and browser-only price calculator are also included for Pages. [Full reporting/privacy details](community/README.md).

## Tests and release checks

```bash
npm test
python3 -B test/installer_test.py
python3 -B test/telemetry_test.py
python3 scripts/smoke.py
```

The first three use offline/mocked transports. `smoke.py` makes actual configured-model calls and prints a compact summary; it can incur provider charges. CI also checks Python syntax, that the telemetry CLI has no pre-consent network side effects, and the actual packed artifact for generated bytecode/backups. The release workflow runs tests before creating a stable GitHub release.

New reporting logic has not been run against every user's credentials or systemd setup. The repository dashboard workflow is separate from participant opt-in and does not enroll users. Registry scanning/publication status is independent of GitHub CI; a successful CI run is not a third-party security certification.

## Primary references

- [OpenClaw plugin installation](https://docs.openclaw.ai/cli/plugins/install)
- [OpenClaw plugin runtime models](https://docs.openclaw.ai/plugins/sdk-runtime/models)
- [OpenClaw tool-free worker completion](https://docs.openclaw.ai/plugins/sdk-runtime/background-work)
- [GitHub CLI API requests](https://cli.github.com/manual/gh_api)
- [GitHub Issues REST API](https://docs.github.com/en/rest/issues/issues)
- [GitHub Actions workflow events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
