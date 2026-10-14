# 14.0 field-readiness audit

**Decision: ready for a controlled field test.** The known ownership and execution mechanisms
identified in CG-73/74 and the prior real-run review are corrected and exercised. This audit does
not establish bug-free software or live vendor delivery. Evaluated on 14 October 2026.

## Evaluation boundary

Baseline: v13.1.0, commit `a6a756af7905461ee8a8003355ab40fe1db770c7`. A frozen checkout was used for
the same-workload comparison. The manager reviews the coding agents' changes, probes the invariants
independently, and owns the release decision. No live GTM writes or publication are part of this audit.

The gates cover authority and source fidelity; native product functionality; schema and policy
ownership; consent and identity; cross-target dependencies; privacy and evidence; transport,
concurrency and recovery; instruction routing; tests and packaging; and speed and cost. A static
file map is evidence of coverage, not proof that every instruction coordinates correctly in use.

## Changes by owning mechanism

| Finding | Owning mechanism and acceptance |
| --- | --- |
| CG-73, duplicated records | Tag policies retain choices; native firing, blocks, consent settings and page-view behavior are read from the native graph. Shared consent policy is referenced once. Obsolete fields fail the current schema. |
| CG-74, overloaded attribution | Operation requirements authorize changes. Dependency demand is derived separately, while field owners are explicit. Adding a consumer cannot silently expand mutation authority. |
| RUN-01, template identity | Installed source establishes native consumer identity; resource IDs and gallery identities have separate roles. |
| RUN-02, native defaults | Comparison owns evidence-backed equivalent serialization. Other fields and types remain strict across all adapters. |
| RUN-03, host transport | The packaged relay owns bounded large replies, cancellation, worker completion and Unicode transport. |
| RUN-04, diagnostics | Sanitized connector causes remain actionable. A textual error does not convert an uncertain dispatched write into proved rejection. |
| RUN-05, recovery lineage | Revision changes unsent current-run work while preserving verified intent and evidence. Outstanding writes require reconciliation. |
| RUN-06, additive authoring | Compilation derives repeated facts and dependencies from the resolved native graph. Authored inputs retain policy and approval decisions. |
| RUN-07, circular conformance | Source conformance requires an independent source projection with provenance. Equality against implementation-derived input is labeled semantic equality. |
| RUN-08, template privacy | Exact inspected context separates public template fixtures from operational secrets; full-content hashes preserve source integrity through redaction. |
| RUN-09, reporting | Saved completion derives from verified evidence. Human blockers group the actual root causes while retaining detailed machine evidence. |
| RUN-10, unbound enhanced-conversion data | A supported native consumer references the sanctioned user-data source in the approved product and event scope. An unused variable is insufficient. |
| RUN-11, repeated event parameters | Compatible repeated mappings have a shared native owner; effective values and local overrides retain their semantics. |
| RUN-12, transport consent | Collection eligibility, transported state and destination eligibility are distinct. Native Google consent processing is distinct from a second configured gate. |
| RUN-13, encoding drift | UTF-8 boundaries preserve source text through compilation, transport and recovery. Independent source comparison remains necessary. |

## Final verification

| Gate | Result |
| --- | --- |
| Repository suite | 565 tests and 488 subtests passed with relay tests required; 145.74 seconds under branch coverage. |
| Extracted runtime archive | 32 packaged tests passed; command router and skill-creator validation passed. |
| Structural coherence | Release and architecture gates passed; 148 Python files passed formatting and lint. No dependency cycles, private cross-module calls, duplicated structural vocabularies or stale active version claims were found by these gates. |
| Independent manager probes | 17/17 passed: five compact request routes, obsolete fact rejection, requirement typo rejection, authority/demand separation, local blockers, order independence, native defaults and diagnostic redaction. |
| Revision ownership | 9/9 independently constructed scenarios passed. Verified prerequisites leave planned consumers amendable; verified consumers retain their owned policy, field proof and authorization. Nested schema references resolve at their defining resource. |
| Captured native graph | All 121 captured objects passed candidate comparison; all 121 unexplained-field mutants were rejected. This reuses saved evidence and is not a fresh read or independent source-conformance proof. |
| Privacy | 29 external canary/control/overblocking vectors matched the frozen baseline exactly: zero canary leaks, 24 flagged cases. Full-source integrity and hidden-value comparison remain distinct. |
| Functionality | Reviewed 14 resource families, eight packaged MCP families, eight analytics products, 13 media/partner directories and seven CMP families against 68 official URLs. The separate matrix distinguishes guidance, deterministic checks, synthetic behavior, authentic source and live saved evidence. |

Coverage used the same source tree boundary and branch instrumentation on both versions. Statement
coverage rose from 81.61% (6,227/7,630) to 82.60% (6,654/8,056). Branch coverage rose from 74.14%
(2,939/3,964) to 75.34% (3,080/4,088). There are still 1,008 uncovered branches. Child-process
execution is excluded from these coverage totals and is exercised separately through host tests.
Coverage improves the evidence; it does not replace review of the actual behavior.

### Actual desktop execution

The distributed relay was exercised through actual Codex `exec_command` / `write_stdin`, PowerShell,
Python, durable journals and OS locks, with synthetic MCP callbacks. A 1,800,136-byte Unicode
template completed as Configured with five verified operations and fresh no-op convergence.
Raw and canonical source hashes matched. The run used 21 synthetic MCP calls, 905 desktop session
calls and 359.519 seconds, with the supported 180-second per-call timeout. Its durable run was
9,551,708 bytes. This is a substantial stress-case transport cost, not a fast-path claim.

A separate actual desktop test deliberately held a dispatched create. At the 20-second relay
deadline, packaged STOP confirmed worker exit, retained the uncertain write journal, and released
the lock. It took 20.124 seconds, 12 synthetic MCP calls and 13 desktop session calls. Cancellation
does not establish whether an already dispatched remote write was applied.

An earlier large-response attempt required forced OS interruption after 805.318 seconds. That
trial exposed per-chunk wait overhead, which was corrected in the relay's existing transport
mechanism before the successful test. Forced interruption and packaged STOP have separate receipts.
The final transport, CLI, engine and relay bytes retain the successful host-test hashes.

## Baseline and performance

The frozen baseline suite passed 509 tests and 508 subtests in 90.57 seconds. Branch coverage was
74.14% (2,939/3,964 branches); statement coverage was 81.61%. Child-process execution is excluded
from this measurement, so host integration is checked through separate behavioral tests.

| Same workload | v13.1.0 | v14.0.0 |
| --- | --- | --- |
| One creation, padded 190 tags / 120 variables / 80 triggers | 51 calls, one write, 44 list pages; 1.008 s local compute | 51 calls, one write, 44 list pages; 1.030 s |
| 20 events, padded 40 tags / 30 variables / 40 triggers | 63 calls, 40 writes, 18 list pages; 2.2 s | 63 calls, 40 writes, 18 list pages; 2.0 s |
| 20-event request / contract / run | 45 / 62 / 521 KiB | 36 / 53 / 511 KiB |

These are controlled connector-call counts and single local timing observations,
not estimates of Google quota units or model token cost. They cannot be compared numerically with
the much larger, interrupted real configuration task.

In the same compact UTF-8 fixture measurement, tag records shrink from 18–19 keys to seven;
shared consent records shrink from 15 to 11. Combined policy bytes decrease by 42.0% for one web
event, 48.1% for shared events and 40.4% for the pipeline case. Native payload bytes are unchanged.
The total compact requests shrink by 7.0–9.5%; folder and Client requests are unchanged.

The entrypoint stays at 436 whitespace-delimited words. The 78 instruction files grow from
36,848 to 37,877 words (2.8%), reflecting actual relay, revision and product semantics. They remain
progressively routed. The exact-paragraph scan finds no repeated paragraph of at least 18 words.
Manual review distinguishes target-state/evidence boundaries from behavioral prohibitions; word
counts alone do not establish absence of prompt debt. Current schemas reject obsolete authoring
forms; the product has no compatibility layer or historical migration path.

## Mapping and evidence limits

`tools/check_architecture.py` generates the complete maintained-file inventory, package membership,
Python dependency and definition map, validation sites, schema pointers, Markdown links and hashes.
[Architecture](architecture.md) identifies rule owners and the JavaScript relay lifecycle.
The release attaches the map generated from the checked commit: 287 maintained files, 158 packaged
files, 62 Python modules and 364 definitions. It includes schema constraints and ownership
annotations, code failure sites, imports, instruction links and file hashes. The JavaScript relay
has an explicit lifecycle owner map in the architecture document. Static ownership gates cover
identifiable duplication and layer violations; semantic ownership also requires the scenario probes.

See [the functionality audit](release-14.0-functionality.md) for product-specific source links and
capability limits. Setup/cleanup-only execution units remain unsupported. Vendor-native schemas,
SDK behavior and implicit server forwarding require inspection of the selected implementation.

The inspected prior real task eventually reached 121 verified objects and fresh no-op convergence.
That establishes saved agreement with that candidate. It does not validate the candidate's source
semantics, shared-parameter design, runtime consent, actual requests or vendor receipt by itself.
Its saved browser Ads tag now references the approved user-data variable. That browser consumer
does not require Ads user data in the GA4 transporter. A future approved server Ads route requires
its own sender/receiver and downstream data-disposition evidence. The previous live graph still has
the repeated page mappings; this release changes the skill and does not modify that workspace.

Field acceptance still needs a separately authorized realistic run through the released skill,
followed by website/server Preview and the relevant vendor checks. Readiness means the known
mechanisms have been corrected and exercised within these limits; it is not a claim of zero bugs.
