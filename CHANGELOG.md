# Changelog

## 0.2.0 — 2026-09-17

Complete JavaScript package replacing interrupted experimental installer blocks.

- Configurable aliases with local-only explicit failure behavior.
- Parallel Ask Around with individual and total deadlines, local-first synthesis and partial results.
- Private, conversation-scoped originals with paging and retention.
- Host-authorized isolated cloud completions; no guessed model-resolution return fields.
- Five-second automatic local budget and normal main-agent fall-through.
- Per-call outcome accounting and user-configured API-equivalent prices.
- Linked Linux installer with backups, visible consent, bounded restart wait and targeted rollback.
- Quiet live tests that check completed results, not only intended routing labels.
- Optional local-model provisioning through existing Ollama, with consent and smoke benchmarks.

This is a preview pending live OpenClaw integration testing, not a ClawHub publication.

## 0.2.2

- Configure the dedicated Claude worker with model-scoped `agentRuntime.id: "claude-cli"`.
- Keep Claude and Astra structurally identical inside Louter: both use `api.runtime.subagent.complete()` against dedicated configured worker agents.
- Add upgrade-time Claude CLI presence check and live route verification.
- Fix upgrader PATH discovery for non-interactive SSH shells.
