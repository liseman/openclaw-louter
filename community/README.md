# Opt-in community savings — GitHub only

The [public totals dashboard](https://github.com/liseman/openclaw-louter/tree/community-stats) lives in this repository's `community-stats` branch. GitHub Issues receive the reports; GitHub Actions rebuilds the totals roughly hourly. No Cloudflare, external server, database, publisher PAT or embedded shared credential is required.

**Reporting is OFF until the user explicitly opts in. Reports are PUBLIC and linked to the sender's GitHub username. They are not anonymous.** GitHub can retain connection metadata and issue/edit history even though the Louter payload contains no IP address.

## Participate (Louter 0.2.9 or newer)

From your installed Louter package or checkout, with GitHub CLI authenticated for github.com:

```bash
python3 scripts/louterctl.py telemetry preview
python3 scripts/louterctl.py telemetry on
python3 scripts/louterctl.py telemetry send
```

`on` shows the complete disclosure and your public GitHub identity before asking for consent. It installs a **profile-specific systemd user timer**, not a gateway service. No statistics are sent during `on`; the first scheduled attempt happens at the next daily timer, or use `send`. Both manual and automatic sends enforce a 24-hour interval between attempts, including failed attempts. The timer needs the user's systemd session to be running.

For manual-only participation, including macOS:

```bash
python3 scripts/louterctl.py telemetry on --manual
```

For a named profile or to avoid inherited state confusion, use the standalone client with an explicit state root:

```bash
python3 scripts/telemetry.py --state-dir "$HOME/.openclaw-louter-clean" preview
python3 scripts/telemetry.py --state-dir "$HOME/.openclaw-louter-clean" on
```

Otherwise the client respects `OPENCLAW_STATE_DIR`, `OPENCLAW_PROFILE` and `OPENCLAW_HOME`. It reads **only** `louter/stats.json` plus its own consent/checkpoint file, not sessions, transcripts, credentials or route configuration. It cannot grant itself access to private repositories. An existing `gh` login needs permission to create/edit the user's own public issues in this repository; a restricted fine-grained token may not permit that. A failed authorization remains a visible reporting error and never changes model routing.

## Controls

```bash
python3 scripts/louterctl.py telemetry status
python3 scripts/louterctl.py telemetry preview
python3 scripts/louterctl.py telemetry off
python3 scripts/louterctl.py telemetry withdraw
```

`preview` and `status` make **no network requests** and do not create an installation ID. `off` disables future uploads but leaves previously submitted data public. `withdraw` disables reporting, replaces the current report with a withdrawal marker and closes the issue; the next rebuild excludes that installation. Closing the report on GitHub also excludes it and causes the client to stop instead of reopening it. These actions **do not erase issue edit history, prior repository commits, or copies held by others**.

The ordinary installer's `--yes` is **not telemetry consent**. Only the dedicated `telemetry on --yes` explicitly preauthorizes the displayed public-reporting terms. Upgrades do not opt in existing users. Disabling telemetry does not disable Louter or local routing.

## Payload and estimates

Reports contain exactly: schema version, random installation UUID, sequence number, Louter version, reporting date, withdrawal flag and eight cumulative numeric counters:

- Locally completed direct turns; estimated input/output tokens avoided.
- Main-agent handoffs; cloud attempts/completions; Ask Around runs; local fallback answers.

No prompts, answers, session IDs, model names, machine identifiers, local paths or provider credentials are sent. GitHub necessarily identifies the issue author and submission/edit times. **Previously accumulated lifetime aggregate counts are included on opt-in.** Counts accumulated while disabled can therefore appear after re-enabling. Clearing local telemetry files loses retry/reset history; do not clone one telemetry state across machines.

The client maintains a durable counter checkpoint across ordinary `reset-stats` epoch changes. Re-reading/retrying a snapshot never adds it twice. Activity lost before a stats reset cannot be recovered. Decreasing counters within an unchanged epoch fail closed rather than inventing a correction.

The collector validates an exact allowlist, bounds numeric fields, rejects duplicate JSON keys/oversized bodies, binds reports to GitHub's author ID, and takes one latest sequence per author/installation. Any closed/withdrawn/excluded duplicate suppresses that installation. Maintainers can add `louter-stats-exclude` to remove an abusive report. This prevents accidental duplication, **not deliberate fabrication or Sybil attacks**.

These are self-reported statistics, not verified dollars or compute savings. A local answer is not proof of an avoided cloud request; the user's main agent might itself be local. Token estimates use client-configured assumptions. Cloud fallback/panel answers do not increase avoided-turn estimates. The HTML dashboard has an optional browser-only price calculator, with prices **unset** by default:

`gross API-equivalent estimate = estimated_input_tokens / 1e6 * input_price + estimated_output_tokens / 1e6 * output_price`

This excludes cloud/panel spending, caches, electricity and subscription billing. It is not net savings.

## Dashboard operation

The collector uses GitHub Actions' built-in `GITHUB_TOKEN` with `issues: read` and `contents: write`. Clients use their own existing `gh` credentials; no maintainer credential ships in Louter. The runtime reply hook has no new networking, timers or subprocesses.

The workflow runs on a schedule, manual dispatch and relevant trusted `main` changes—not on arbitrary issue events. Issue text is parsed as bounded JSON, never interpolated into shell code or executed. Aggregation is a full recomputation; a pagination/network failure fails the run instead of publishing partial totals. It publishes `README.md`, `totals.json`, `reports.json` and a static HTML page on `community-stats`, leaving `main` unchanged. GitHub schedules can be delayed or disabled; the last published timestamp remains visible.

The **rendered README dashboard works immediately on GitHub**. To serve the HTML version with GitHub Pages, the repository owner can choose **Settings → Pages → Deploy from a branch → community-stats → /(root)**. Pages is optional; no dashboard URL is claimed before it is enabled. The page uses no third-party scripts, fonts, cookies or analytics.

## Verification

```bash
python3 -B test/telemetry_test.py
```

Tests cover opt-out/no networking, schema/privacy controls, retries, rate limits, account switching, durable counter resets, withdrawals, malformed input, duplicate reports and aggregation. No real usage report is generated by the test suite.
