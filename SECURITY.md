# Security and privacy

Louter is trusted code running inside OpenClaw. Review it and its permissions before installation. It is not a sandbox or a promise of model correctness.

Local endpoints are restricted to loopback HTTP addresses; redirects are rejected. Explicit local requests do not fall back to a cloud model. This does not disable channel transport, OpenClaw transcripts, unrelated plugins, or provider-independent telemetry. Automatic routing may send a request to the configured main agent; Ask Around deliberately sends the question to each enabled panel member and may use its configured synthesis fallback.

Cloud completions use OpenClaw's existing credential and permission systems. Louter does not embed API keys. Explicit model calls and panels are isolated, text-only, current-request completions rather than full tool-capable agents.

Stored panel replies are conversation-scoped, kept in private files, and subject to configured retention. Do not share diagnostic directories or local state publicly.

Report non-sensitive bugs through the repository issue tracker. For sensitive reports, contact the maintainer using a private channel rather than posting tokens, private conversations, or exploit details in a public issue.

No independent security audit or live-provider certification is claimed.
