# Contributing

Keep the skill agent-neutral and focused on authorized GTM configuration. Never commit client
containers, plans, domains, credentials, personal data, screenshots, traces or generated run reports.
Use synthetic fixtures and local fake transports.

Use Python 3.11+, Node.js 22 and PowerShell 7. Install development dependencies with
`python -m pip install -e ".[dev]"`, then run the checks listed in [README.md](README.md#development-and-release).
Set `REQUIRE_RELAY_TESTS=1` to require local relay execution, as CI does. SDK tests use the optional
official MCP package against local stdio, HTTP and SSE servers, without account credentials.

Use only contract 8.0/run 6.0. Update fixtures to current semantics; do not add legacy parsers,
aliases, migrations or compatibility layers. Read [maintenance](references/maintenance.md) for
ownership. Shared domain rules serve preparation and execution; adapters handle transport rather
than owning a competing validator. Keep repository release tooling in `tools/`.

Behavior changes need focused positive and negative scenarios. Preserve approval binding, consent,
native field/shape proof, uncertainty after interrupted writes, dependency containment and repeat-run
no-op convergence. Test assertions separately from native saved payloads. Static and fake-transport
tests must never claim browser or vendor runtime certification.

Update VERSION, pyproject.toml, README and the current changelog section together. CI derives its tag
from VERSION. Release notes must explain the problem, change, required user action, validation and
known limits. Preserve past changelog entries as historical records. The package builder uses fixed
ZIP metadata and an explicit runtime boundary; verify extracted contents before tagging.
