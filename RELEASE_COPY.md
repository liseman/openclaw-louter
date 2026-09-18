# Louter: keep the easy stuff local

Louter is a lightweight OpenClaw plugin with a different answer to model routing:
sometimes the cheapest cloud-agent turn is the one you don't start.

Simple, self-contained messages can be answered through your local model endpoint.
Requests that need the full agent continue to your normal model and its tools.
Explicit aliases let you choose a model, while **Ask Around** gathers independent
answers from your configured panel and preserves both a synthesis and the originals.

- Local-only explicit requests do not silently become cloud requests.
- Your models and credentials stay configured in OpenClaw.
- Panel members have independent deadlines; partial outcomes remain visible.
- Details come from stored originals, not another summarization call.
- Savings are estimates with disclosed assumptions, not imaginary subscription discounts.

Preview release for OpenClaw 2026.9.x. Text-only isolated prefixes and panels;
normal unprefixed main-agent requests retain their usual tools/history. Installation
requires review and capability consent. No universal performance or correctness claims.
