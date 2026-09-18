# OpenClaw Plugin Compatibility Report

Generated: deterministic
Status: PASS

## Summary

| Metric                     | Value |
| -------------------------- | ----- |
| Fixtures                   | 1     |
| High-priority fixtures     | 1     |
| Hard breakages             | 0     |
| Warnings                   | 1     |
| Compatibility suggestions  | 0     |
| Issue findings             | 1     |
| Open issue findings        | 1     |
| Runtime-covered findings   | 0     |
| Runtime-partial findings   | 0     |
| P0 issues                  | 0     |
| P1 issues                  | 0     |
| Open P0 issues             | 0     |
| Open P1 issues             | 0     |
| Live issues                | 0     |
| Live P0 issues             | 0     |
| Compat gaps                | 0     |
| Deprecation warnings       | 0     |
| Inspector gaps             | 0     |
| Open inspector gaps        | 0     |
| Runtime coverage artifacts | 0     |
| Upstream metadata          | 1     |
| Contract probes            | 1     |
| Decision rows              | 0     |

## Triage Overview

| Class               | Count | P0 | Meaning                                                                                                                                                  |
| ------------------- | ----- | -- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| live-issue          | 0     | 0  | Potential runtime breakage in the target OpenClaw/plugin pair. P0 only when it is not a deprecated compat seam.                                          |
| compat-gap          | 0     | -  | Compatibility behavior is needed but missing from the target OpenClaw compat registry.                                                                   |
| deprecation-warning | 0     | -  | Plugin uses a supported but deprecated compatibility seam; keep it wired while migration exists.                                                         |
| inspector-gap       | 0     | -  | Plugin Inspector needs stronger capture/probe evidence before making contract judgments. Runtime-covered rows are proof-backed and not open report work. |
| upstream-metadata   | 1     | -  | Plugin package or manifest metadata should improve upstream; not a target OpenClaw live break by itself.                                                 |
| fixture-regression  | 0     | -  | Fixture no longer exposes an expected seam; investigate fixture pin or scanner drift.                                                                    |

## P0 Live Issues

_none_

## Other Live Issues

_none_

## Compat Gaps

_none_

## Deprecation Warnings

_none_

## Inspector Proof Gaps

_none_

## Runtime-Covered Inspector Gaps

_none_

## Upstream Metadata Issues

- P2 **openclaw-louter** `upstream-metadata` `plugin-upstream-fix`
  - **package-manifest-version-drift**: openclaw-louter: package and manifest versions drift
  - state: open · compat:none
  - evidence:
    - package:0.2.5
    - manifest:0.2.2
  - author remediation:
    - Align the plugin version declared in package.json and openclaw.plugin.json.
    - docs: https://docs.openclaw.ai/clawhub/plugin-validation-fixes#package-manifest-version-drift

## Hard Breakages

_none_

## Target OpenClaw Compat Records

| Metric                    | Value                                          |
| ------------------------- | ---------------------------------------------- |
| Configured path           | npm:openclaw@2026.9.4                          |
| Status                    | ok                                             |
| Requested version         | latest                                         |
| Resolved version          | 2026.9.4                                       |
| Range eligibility version | 2026.9.4                                       |
| Source                    | npm:openclaw                                   |
| NPM dist-tag              | latest                                         |
| Prepared cache            | hit                                            |
| Compat registry           | -                                              |
| Compat records            | 0                                              |
| Compat status counts      | -                                              |
| Record ids                | -                                              |
| Hook registry             | dist/agent-harness-runtime-BvaKEkqR.d.ts       |
| Hook names                | 42                                             |
| API builder               | dist/agent-harness-runtime-BvaKEkqR.d.ts       |
| API registrars            | 57                                             |
| Captured registration     | dist/agent-harness-runtime-BvaKEkqR.d.ts       |
| Captured registrars       | 57                                             |
| Package metadata          | package.json                                   |
| Plugin SDK exports        | 338                                            |
| Manifest types            | dist/install-security-scan.types-DTKUtHF_.d.ts |
| Manifest fields           | 0                                              |
| Manifest contract fields  | 22                                             |

## Warnings

| Fixture         | Code                           | Level   | Message                                                          | Evidence                      | Compat record |
| --------------- | ------------------------------ | ------- | ---------------------------------------------------------------- | ----------------------------- | ------------- |
| openclaw-louter | package-manifest-version-drift | warning | package.json and openclaw.plugin.json publish different versions | package:0.2.5, manifest:0.2.2 | -             |

## Suggestions To OpenClaw Compat Layer

_none_

## Issue Findings

- P2 **openclaw-louter** `upstream-metadata` `plugin-upstream-fix`
  - **package-manifest-version-drift**: openclaw-louter: package and manifest versions drift
  - state: open · compat:none
  - evidence:
    - package:0.2.5
    - manifest:0.2.2
  - author remediation:
    - Align the plugin version declared in package.json and openclaw.plugin.json.
    - docs: https://docs.openclaw.ai/clawhub/plugin-validation-fixes#package-manifest-version-drift

## Contract Probe Backlog

- P2 **openclaw-louter** `package-loader`
  - contract: Package and OpenClaw manifest versions stay aligned for release compatibility reporting.
  - id: `package.metadata.version-alignment:openclaw-louter`
  - evidence:
    - package:0.2.5
    - manifest:0.2.2

## Fixture Seam Inventory

| Fixture         | Priority | Seams          | Hooks                                           | Registrations     | Manifest contracts |
| --------------- | -------- | -------------- | ----------------------------------------------- | ----------------- | ------------------ |
| openclaw-louter | high     | plugin-runtime | before_agent_reply, gateway_start, gateway_stop | definePluginEntry | -                  |

## Decision Matrix

_none_

## Raw Logs

| Fixture         | Code                   | Level | Message                                                                          | Evidence                                                                                       | Compat record |
| --------------- | ---------------------- | ----- | -------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ------------- |
| openclaw-louter | seam-inventory         | log   | observed 3 hooks, 1 registrations, and 0 manifest contracts                      | hook:before_agent_reply, hook:gateway_start, hook:gateway_stop, registration:definePluginEntry | -             |
| openclaw-louter | hook-names-present     | log   | all observed hooks exist in the target OpenClaw hook registry                    | before_agent_reply, gateway_start, gateway_stop                                                | -             |
| openclaw-louter | api-registrars-present | log   | all observed api.register* calls exist in the target OpenClaw plugin API builder | -                                                                                              | -             |
| openclaw-louter | sdk-exports-present    | log   | all observed plugin SDK imports exist in target OpenClaw package exports         | openclaw/plugin-sdk/plugin-entry                                                               | -             |
| openclaw-louter | package-metadata       | log   | selected package metadata for plugin contract checks                             | package.json, @liseman/openclaw-louter, version:0.2.5                                          | -             |
