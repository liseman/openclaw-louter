# Publishing Louter

The accompanying self-contained `publish-louter.sh` stages only this release's source files. It does not read OpenClaw account files, transcripts, or local panel data. Run it as your normal user. It requires git, Python 3, Node.js 22 or later, npm, and GitHub CLI (`gh`).

It authenticates GitHub as `liseman`, uses the ClawHub CLI login for publisher `liseman`, validates and dry-runs the package, creates the public `liseman/openclaw-louter` repository when absent, and creates a GitHub prerelease tagged `v0.2.0`. It submits the exact npm-pack artifact to ClawHub with source commit metadata. Browser/device approval remains interactive. No tokens are printed or passed back to chat.

Preparing this source package does not publish it. The script performs the network writes from the publisher's authenticated machine.

ClawHub validation and publication are separate. A successful upload may still be pending security review. The script waits up to three minutes for definitive publication and reports an unconfirmed outcome rather than claiming success on timeout. If publication is pending, inspect the saved result and registry state rather than resubmitting blindly.

The script does not force-push, overwrite another repository, change your running OpenClaw setup, or publish to npm. It keeps logs and artifacts in `.publish/`, excluded from Git and npm artifacts. Future releases should increment the version and rerun all tests, including a live host smoke test.

Official references:

- https://docs.openclaw.ai/clawhub/publishing
- https://docs.openclaw.ai/clawhub/cli
- https://cli.github.com/manual/gh_repo_create
- https://cli.github.com/manual/gh_release_create
