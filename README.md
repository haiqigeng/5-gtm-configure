# Configure GTM

Configure approved analytics, media, consent and scoped organization changes in authorized Google
Tag Manager web/server workspaces or connected pipelines. The skill saves and verifies the intended
object graph, preserves approved measurement semantics and consent, and never publishes GTM versions.

## Current release

**[v11.0.0](https://github.com/haiqigeng/5-gtm-configure/releases/tag/v11.0.0)** reorganizes the skill
around one command entry point, focused documentation routes and shared validation rules. It fixes
GA4 field-scope mapping, enforces exact field shapes and keeps server review assertions separate from
native API payloads. See the [changelog](CHANGELOG.md) for changes, validation and limitations.

Only `configuration-contract@8.0` and `configuration-run@6.0` are supported. Create fresh contracts
and runs from approved inputs. Obsolete commands and schema migrations are intentionally absent.

## Install

Download `configure-gtm-v11.0.0.zip` from the release and extract its `configure-gtm` folder into your
host's skills directory. Replace the previous skill folder completely so removed paths do not remain.
Keep any active run artifacts separately; they are not installation files.

Python 3.11+ is required. Install the runtime dependency into the Python environment used by the host:

```shell
python -m pip install -r configure-gtm/scripts/requirements.txt
python configure-gtm/scripts/configure_gtm.py --help
```

The Codex relay additionally uses Node.js and PowerShell 7. Claude Code and Gemini CLI use the optional
official MCP SDK: install `scripts/requirements-mcp.txt` instead. Follow the relevant
[Codex guide](references/adapters/codex.md), [SDK host guide](references/adapters/mcp-sdk.md),
or [custom adapter contract](references/adapters/custom.md). Host support does not certify a live
configuration or model session.

Invoke the skill with `$configure-gtm` and the approved requirements and target workspace identities.
Begin with [SKILL.md](SKILL.md); load only the references selected by its routing table.

## Supported work and boundaries

| Route | Intended scope |
| --- | --- |
| Web | Supported tags, triggers, variables, templates, folders, Google tag settings and explicitly authorized workspace resources |
| Server | Clients, Event Data variables, tags, triggers, templates, scoped Transformations and settings |
| Pipeline | Authorized sender/receiver graph, transport ownership, consent propagation, exact field shapes and destination-specific deduplication |
| Organization | Folder creation, rename and reuse with target authority and container evidence; no collection changes |

Analytics semantics come from approved inputs. Media mechanics come from current official product
documentation and inspected templates. One target never grants authority over another. The runtime
checks authenticated identity, baseline and drift, journals uncertain writes, verifies saved native
objects and requires a read-only no-op convergence check before reporting `Configured`.

Results use `Configured`, `Partial`, `Blocked` or `Deferred`. Configuration does not prove runtime
behavior. The skill excludes tracking-plan design, general audit/cleanup, runtime QA, publication,
GTM version creation, infrastructure provisioning and legal decisions. Unsupported native topologies,
including triggerless setup/cleanup-only tags, remain blocked. Draft acceptance precedes any external,
separately authorized publication; see [pipeline workflow](references/pipeline/architecture-and-workflow.md).

## Commands

All commands use `python scripts/configure_gtm.py COMMAND`; each provides `--help`.

| Command | Purpose |
| --- | --- |
| `import-plan` | Import approved GA4 handoff semantics with exact field names/scopes |
| `prepare` | Compile a configuration request into the current contract |
| `validate-contract` | Validate structure and cross-object semantics |
| `conformance` | Compare approved tracking-plan semantics with a contract |
| `compare` | Compare normalized native object graphs |
| `run` | Initialize, inspect, validate, checkpoint, reopen or render a durable run |
| `mcp` | Discover and execute through the Codex MCP relay |
| `mcp-host` | Execute through the optional official MCP SDK |

## Repository map

| Location | Responsibility |
| --- | --- |
| `SKILL.md`, `agents/` | Discovery, concise entry instructions and routing |
| `references/core/` | Authority, evidence, authoring, workflow, execution and acceptance |
| `references/adapters/` | Adapter profile, discovery, quotas and host-specific setup |
| Other `references/` folders | Conditional domain and vendor guidance |
| `schemas/` | Executed structural contracts; semantic rules remain in Python |
| `scripts/configure_gtm.py` | Single lazy-loading command router |
| `scripts/gtm_configure/core/` | Common models, schema loading, JSON and privacy primitives |
| `scripts/gtm_configure/domain/` | Shared field, consent, authority, web, server and pipeline rules |
| `scripts/gtm_configure/intake/` | Approved-input import and request compilation |
| `scripts/gtm_configure/runtime/` | Durable execution, state, validation and saved verification |
| `scripts/gtm_configure/adapters/` | MCP discovery, calls and transport |
| `scripts/gtm_configure/comparison/` | Type-strict JSON, native and semantic comparisons |
| `tests/` | Regression, schema, transport, recovery and release checks |
| `tools/` | Repository-only release validation and deterministic packaging |

See [maintenance](references/maintenance.md) for rule ownership. No compatibility facades are shipped.

## Development and release

```shell
python -m pip install -e ".[dev]"
python -m ruff format --no-cache --check scripts tests tools
python -m ruff check --no-cache scripts tests tools
python -B -m pytest tests -q -p no:cacheprovider
python tools/check_release.py --tag v11.0.0
python tools/build_skill_package.py --output dist/configure-gtm-v11.0.0.zip
git diff --check
```

CI runs on Linux/Python 3.11 and Windows/Python 3.13, with Node.js 22 and PowerShell 7 for relay tests.
Tagging the checked commit `v11.0.0` triggers release validation and deterministic archive creation.
The workflow publishes the current changelog section, archive and SHA-256 checksum. The archive
contains the skill and its self-contained regression suite, excluding repository-only tooling and
the broader development fixtures.

The refactor retains the measured folder scenario's one mutation and ten adapter calls. Entry
instructions are 57% shorter and the selected Codex adapter reading path 71% shorter; word counts
are reading proxies, not billed-token or dollar measurements. Stricter schema checks add local work
(about 3 ms for the small fixture; cold import about 191 ms versus 28 ms). These are local fixture
measurements, not end-to-end GTM benchmarks.

Read [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md) before contributing.
Licensed under [MIT](LICENSE).
