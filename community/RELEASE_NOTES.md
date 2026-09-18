# Louter 0.2.11 — no-bytecode packaging hardening

- Fixes the concrete ClawHub 0.2.10 scan finding: `scripts/__pycache__/common.cpython-314.pyc` could be recreated after package extraction when Python entry points imported `common.py`.
- The shell installer now exports `PYTHONDONTWRITEBYTECODE=1` and invokes Python with `-B`.
- Packaged Python entry points set `sys.dont_write_bytecode = True` before importing sibling modules.
- Adds a regression gate that builds the npm artifact, extracts it, runs packaged installer/setup/telemetry entry points, and fails if any `__pycache__`, `.pyc`, or `.pyo` appears afterward.
- Existing prepack cleanup and artifact inventory checks remain in place.
- Routing, opt-in telemetry consent, community dashboard, and pricing behavior are unchanged.

Validation includes the normal JavaScript, installer and telemetry suites plus the new post-extraction bytecode test.

[Live savings dashboard](https://liseman.github.io/openclaw-louter/) · [Opt-in instructions and privacy](https://github.com/liseman/openclaw-louter/blob/main/community/README.md)
