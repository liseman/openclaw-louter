# OpenClaw Plugin Issue Findings

Generated: deterministic
Status: PASS

## Triage Summary

| Metric                     | Value |
| -------------------------- | ----- |
| Issue findings             | 1     |
| Open issue findings        | 1     |
| Runtime-covered findings   | 0     |
| Runtime-partial findings   | 0     |
| P0                         | 0     |
| P1                         | 0     |
| Open P0                    | 0     |
| Open P1                    | 0     |
| Live issues                | 0     |
| Live P0 issues             | 0     |
| Compat gaps                | 0     |
| Deprecation warnings       | 0     |
| Inspector gaps             | 0     |
| Open inspector gaps        | 0     |
| Runtime coverage artifacts | 0     |
| Upstream metadata          | 1     |
| Contract probes            | 1     |

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

- P2 **louter** `upstream-metadata` `plugin-upstream-fix`
  - **package-manifest-version-drift**: louter: package and manifest versions drift
  - state: open · compat:none
  - evidence:
    - package:0.2.4
    - manifest:0.2.2
  - author remediation:
    - Align the plugin version declared in package.json and openclaw.plugin.json.
    - docs: https://docs.openclaw.ai/clawhub/plugin-validation-fixes#package-manifest-version-drift

## Issues

- P2 **louter** `upstream-metadata` `plugin-upstream-fix`
  - **package-manifest-version-drift**: louter: package and manifest versions drift
  - state: open · compat:none
  - evidence:
    - package:0.2.4
    - manifest:0.2.2
  - author remediation:
    - Align the plugin version declared in package.json and openclaw.plugin.json.
    - docs: https://docs.openclaw.ai/clawhub/plugin-validation-fixes#package-manifest-version-drift

## Contract Probe Backlog

- P2 **louter** `package-loader`
  - contract: Package and OpenClaw manifest versions stay aligned for release compatibility reporting.
  - id: `package.metadata.version-alignment:louter`
  - evidence:
    - package:0.2.4
    - manifest:0.2.2
