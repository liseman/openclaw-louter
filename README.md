# Louter — Lite Router for OpenClaw

**Keep the easy stuff local. Ask your models when it matters.**

Louter adds a small, text-only local reply path ahead of the normal OpenClaw agent. A local answer can finish the turn without sending the full agent prompt to a model. Harder automatic requests continue to your existing main agent. Explicit prefixes and an optional model panel give you direct control.

**Version 0.2.0 is a complete runnable preview, not a claim of production certification.** It ships ordinary JavaScript, not a missing TypeScript build. It targets the interfaces verified in this conversation on OpenClaw 2026.9.4. Model names below are the user's configured routes, not assertions about current public model availability.

## Install on luketinybox

Run the supplied self-contained `install-louter.sh` on the Linux OpenClaw host, as `luke`, without sudo. Or unpack the source archive and run `bash install.sh`.

The installer:

* runs offline tests before changing registration;
* backs up existing Louter source and the config fields it changes;
* links `~/openclaw-louter`, enables its conversation hook, and authorizes only its configured cloud targets;
* disables `fastpath-test` and `mode-switcher` only after Louter is registered;
* preserves main-model selection, provider credentials, Qwen's systemd service and previous source;
* restarts with a bounded wait, never force-kills running work, then runs quiet live smoke tests.

OpenClaw capability prompts remain visible. Routine logs go into a private diagnostic directory. Failed tests are not declared successful just because a routing log appeared. The live tests verify turn completion, expected text and route/model receipts where available.

`bash install-louter.sh --skip-smoke` skips paid/live model calls. `--no-restart` also skips live tests. `--yes` explicitly approves the permissions described by the installer; it is not needed for ordinary use.

## Messages

| Message | Result |
| --- | --- |
| `What is a hexagon?` | Automatic local attempt, then main-agent fallback when needed. |
| `Research the latest …` | Bypasses local inference and continues to the normal main agent. |
| `local: Explain this sentence: …` | Local text completion only. Error/timeout does **not** ask a cloud model. |
| `astra: Compare these two arguments: …` | One isolated completion from the configured `astra` model. |
| `claude: Review this paragraph: …` | One isolated completion from the configured `claude` model. |
| `ask around: Which approach is better, and why?` | Configured panel in parallel, local-first synthesis, optional configured synthesis fallback. |
| `ask around --details claude: …` | Synthesis plus Claude's stored original response. |
| `details claude` / `details all` | Full saved responses from the latest panel **in this conversation**, without a new model call. |
| `details claude RUN-ID --page 2` | A later page of a particular retained response. |
| `savings` / `savings today` / `savings week` / `savings month` | Persistent counters and explicitly labeled estimates. |
| `louter routes` / `louter status` / `louter help` | Local diagnostics, configuration view or help. |

### Explicit cloud routes are not full tool-capable agents

`astra:` and `claude:` deliberately use `api.runtime.llm.complete` with `isolated-agent-runtime`. Each receives the prefix-stripped **current text only** and no conversation history or model-callable tools. That avoids recursive routing and accidental agent actions. For browsing, files, account access, or continuing your normal conversation, use an **unprefixed** message; your normal main agent retains its configured capabilities.

The same limitation applies to Ask Around: it is a text model panel, not three agents browsing or executing commands. Paste necessary evidence into the question. Independent answers are not independent verification. Model agreement is not a confidence score.

## Configurable routes

All settings live at `plugins.entries.louter.config`. The configuration schema is in `openclaw.plugin.json`; `config.example.json` contains the complete initial configuration.

Initial routes reproduce the confirmed setup:

* `local` → loopback Qwen at `http://127.0.0.1:18080/v1/chat/completions`;
* `astra` → `openai/gpt-6-astra`;
* `claude` → `anthropic/claude-opus-5`.

Only the named agents in `agentIds` are intercepted; initially that is `main`.

Terminal administration does not require editing JavaScript:

```bash
python3 ~/openclaw-louter/scripts/louterctl.py routes list
python3 ~/openclaw-louter/scripts/louterctl.py routes add reviewer anthropic/claude-opus-5
python3 ~/openclaw-louter/scripts/louterctl.py panel local astra reviewer
python3 ~/openclaw-louter/scripts/louterctl.py synthesizer local --fallback astra
python3 ~/openclaw-louter/scripts/louterctl.py timeout 5
```

`routes add` also changes an existing alias. It updates Louter's **exact** host model-permission list after confirmation, not the user's global model policy. A route still needs working provider authentication and permission in the selected agent's policy. A disabled route remains visible but is never invoked. Up to eight explicitly selected panel aliases may participate; the entire OpenClaw catalog is never fanned out automatically.

For a local Ollama route, use its native API so thinking and residency settings are explicit:

```bash
python3 ~/openclaw-louter/scripts/louterctl.py routes add small qwen3.5:2b \
  --local-endpoint http://127.0.0.1:11434/api/chat --protocol ollama --context 4096
```

### Cloud worker runtimes

Louter uses `api.runtime.subagent.complete()` for configured cloud workers. The dedicated Claude worker keeps the canonical model ref `anthropic/claude-opus-5` and pins the model-scoped runtime to `claude-cli`; this lets the worker use Claude Code's own authenticated CLI backend rather than the direct Anthropic Messages transport. The gateway host must have the `claude` CLI installed, logged in, and visible on the gateway service PATH. Astra uses its configured OpenAI/Codex runtime.

## Ask Around: deadlines, failures and details

Panel calls start concurrently, each with a deadline and an abort signal. There is also a total synthesis/panel deadline. The defaults are 20 seconds per cloud panel member, 12 seconds for local, and **45 seconds for the overall panel/synthesis operation**, plus small host/storage overhead. The hook's host timeout is deliberately longer than the plugin's internal budgets.

The local synthesizer is attempted when the complete input fits its conservative context budget. Otherwise, or on failure, the configured cloud synthesizer may run within the remaining time. Set `fallbackSynthesizer` to `null` to forbid cloud synthesis. Identical answers are displayed directly without an unnecessary synthesis call. A single surviving answer is labeled as such.

Each original response, including an explicitly labeled partial response, is stored before synthesis. A failed or over-budget synthesis never discards the panel. Long originals are paginated instead of silently truncated. The panel is scoped by a hash of `agentId + sessionKey`; one conversation cannot read another's saved answers through `details`.

The code races deadlines itself and supplies abort signals. The host/provider must honor cancellation to stop underlying work; a deadline cannot prove that all remote billing or remote computation stopped. Logs distinguish requested models, actual returned model attribution, failures and completed responses. A timeout is not a completed answer.

## What `local:` guarantees—and what it does not

Within an active Louter hook, `local:` calls only a literal-loopback HTTP inference endpoint and never falls through to another model on error. It does not use environment HTTP proxies, follow redirects or allow remote URLs for a local route. It does not execute code, fetch files or run tools. Louter catches explicit-route errors and returns them to the user.

This is **not an end-to-end offline or platform privacy guarantee**. WhatsApp and other message channels may already transport the message. OpenClaw can retain transcripts and other enabled plugins may observe turns. A locally configured inference server must itself be trusted not to proxy to a cloud service. If the plugin is disabled, blocked, or the host stops executing its hook, it cannot enforce anything. Use the live `louter ping` test to verify activation.

The current reply-hook event guarantees cleaned text, not a complete attachment list. Louter declines when available context reports media and sends obvious attachment/file requests to main. It cannot guarantee detection of hidden/omitted media metadata on every channel. Explicit routes and panel requests remain text-only. Unknown explicit aliases return an error instead of guessing a cloud destination.

## Savings without imaginary prices

`savings` reports locally completed requests, avoided **main-agent turns**, main-agent handoffs, attempted/completed isolated calls, council calls, and reported token usage. It does not claim each avoided turn would have made exactly one cloud call.

Gross avoided API-equivalent cost uses configurable assumptions. Token assumptions default to the prototype's 15,000 input / 150 output tokens per avoided turn; these are not measured counterfactual cloud usage. Dollar prices default to **unset**, not a fabricated Astra price.

Supply your own verified prices, for example by running `louterctl.py prices INPUT_PRICE OUTPUT_PRICE` with USD per million token values. This is not net savings: panel/synthesis calls, caching, varying cloud answers, local electricity and subscription billing are not counterfactually measured. Legacy counter files are preserved separately and not silently recast as validated savings.

## Local model setup

```bash
python3 ~/openclaw-louter/scripts/setup_local.py
```

Setup first reuses the existing Qwen service. Otherwise, with an existing reachable Ollama installation, it offers a Qwen 3.5 model download after consent, using RAM only as a starting heuristic, then runs two tiny answer/latency tests. It applies a candidate only with `--apply`. It does not silently change the model or automatically increase your timeout. A failed candidate leaves current configuration unchanged.

This preview provisions **models through an existing runtime**; it does not install Ollama, graphics drivers, OS services or binaries unattended. New machines without a runtime need one installed first or a supplied local endpoint. Your luketinybox already has the service and needs no new model download. A two-question smoke test does not certify general model quality or safety.

## Tests and operations

```bash
cd ~/openclaw-louter
node --test test/*.test.js                 # offline / mocked transport tests
python3 scripts/smoke.py                   # live integration tests; compact final summary
python3 scripts/smoke.py --quick           # excludes panel and main-handoff checks
```

Smoke tests intentionally ask for short fixed answers, not open-ended research jobs. They check actual completion and evidence from the same session, rather than treating a timeout with a correct routing label as a pass. Logs and full JSON results stay in a private diagnostics directory.

Each local/remote model request, route decision and panel completion gets a metadata event with its run/session correlation. Raw questions and answers are **not** included in those routing logs. Raw panels are private JSON files under `~/.openclaw/louter/sessions/`, normally mode 0600 and directory mode 0700. Expired details are refused on access; cleanup runs on Gateway start and hourly. Shutdown aborts plugin-owned requests. Existing OpenClaw transcript behavior is unchanged.

The installer writes a targeted `rollback.py` path in its final summary. It does not delete original experimental plugins or reset global account/model configuration.

## Verification status

The delivered build is tested with mocked local/cloud transports, filesystem storage tests, and a real loopback HTTP redirect test. Its installer flow is exercised with simulated OpenClaw commands. It has **not** been executed against Luke's live OpenClaw 2026.9.4 runtime by this assistant. The installer/live smoke test is the remaining integration check; neither an earlier prototype's routing-only test nor a synthetic reply's base model label proves a new cloud route is working.

## References

Verified primary sources used for the implementation:

* https://docs.openclaw.ai/plugins/hooks/reference — claim hooks and timeout/cancellation semantics.
* https://docs.openclaw.ai/plugins/sdk-runtime/models — isolated completion and per-plugin model permissions.
* https://docs.openclaw.ai/tools/llm-task — one-message, zero-tool isolated execution.
* https://docs.openclaw.ai/cli/plugins/install — linked installs, approval and enable behavior.
* https://ollama.com/library/qwen3.5:0.8b
* https://ollama.com/library/qwen3.5:2b
* https://ollama.com/library/qwen3.5:4b
* https://docs.ollama.com/api/chat

The earlier installed-source snippets supplied by Luke also establish `before_agent_reply`, `eligibleTriggers`, and `api.runtime.llm.complete` on the exact target installation. Public SDKs evolve; keep host-version smoke tests in the release process.
