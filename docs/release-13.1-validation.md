# Release 13.1.0 coherence re-audit

Evaluated 2026-10-14 against frozen v13.0.1 commit
`6a13e195b5f95f977a6b13d4a9b5864ed8ece7a3`.
The supported skill routes are **ready for an authorized field test** after this offline pass.
Live GTM testing remains deferred by the user. There is no claim of universal bug freedom or live
vendor certification.

## Whole-skill mapping

The maintained file map and [ownership matrix](architecture.md) cover entry instructions, every
reference, structural schemas, phase-neutral domain rules, intake, runtime, adapters, comparison,
renderer, tests and release tools. The generated release attachment `ownership-map.json` includes
package membership, byte hashes, imports/calls/failure sites, exact schema constraint pointers and
Markdown links/word counts. There are 155 packaged files and 59 runtime Python modules.

The instruction pass assigns authority, evidence, authoring, execution and acceptance to separate
core owners. Mapping, identity, Google placement, collection ownership, consent eligibility,
consent lifecycle, product classification, template lifecycle, routing and adapter behavior retain
one defining guide each. Vendor guides supply their product differences and link to shared owners.
The graph remains progressively loaded through SKILL.md; all files are reachable and links resolve.

## Root mechanisms improved

| Coordination problem | Coherent correction |
| --- | --- |
| Shared rules repeated across core and vendor guides | Define the target state once at the existing owner; replace repeated instructions with local application and owner links. |
| Negative edge-case prose accumulating around mapping, identity and consent | State permitted source/output/consumer/lifecycle invariants, retaining deterministic schema/domain enforcement and concrete product capability limits. |
| Create-absence docs disagree with adapter cache behavior | Describe complete-family cache proof, cache updates, uncertainty readback and final identity inventory at the adapter evidence owner. |
| Adapter routing always loads MCP guidance | Select the required guide from the actual transport through one routing table. |
| Compact authoring implies generated justification | Require explicit object scope justification; the compiler continues deriving only supported mechanical facts. |
| Recovery guidance omits the public action | Name the existing saved-readback checkpoint as the authoritative recovery recording path. |
| Human report omits planned field blockers from its opening view | Render the public state inspection's ready/waiting/blocked/unsafe frontier before object details; retain existing escaping, redaction and verdict derivation. |

The only executable implementation change is `render.py`. Execution, readiness, domain rules,
privacy, adapters, intake, comparison, schemas and producer fixtures are byte-identical to v13.0.1.
No dependency, schema version, compatibility layer or new execution branch was added. Contract 10.0
and run 8.0 remain current. Two report behavior tests cover field-blocker visibility and uncertain
write recovery; existing injection and privacy tests continue to apply.

## Validation and independent review

| Gate | Evidence |
| --- | --- |
| Repository suite | 509 tests and 508 subtests pass with relay tests required; zero skipped. |
| Extracted package | All 32 packaged tests pass. |
| Architecture and packaging | Dependency direction, private access, duplicate definitions/constants/closed-key copies, schemas, links, stale labels, CLI usage, formatting, lint and skill-creator validation pass. |
| Semantic retention | Independent review compares rewritten core, feature and all 13 browser vendor guides against the frozen release and inspects deterministic field/execution/identity owners. No lost authority or capability safeguard was found. |
| Public CLI replay | Prepare, contract validation, conformance where applicable, initialization, inspection and rendering succeed on folder, shared-event and pipeline inputs. Missing justification is correctly rejected. |
| Partial progress | Independent synthetic shared-event execution verifies five ready objects and leaves the unresolved LEAD branch planned/blocked; final human report exposes the same blocker as inspection. |
| Uncertain write | A synthetic applied write with lost response/read outage remains non-resumable. Fresh saved readback plus checkpoint recovers it; convergence reports Configured after exactly one mutation. The report shows the unsafe frontier before recovery and clears it afterward. |
| Pipeline handoff | Unexecuted pipeline remains In progress with open external rollout ownership; neither CLI nor report claims live execution/publication. |
| Error behavior | The same 16 injected error cases produce byte-identical baseline/candidate output. |
| Privacy | Same 18 leak canaries and five controls pass on both versions. Two undeclared public-browser-key inputs retain conservative baseline rejection; evidence-bound declaration tests pass. |
| Report injection | The same probe yields zero forged sections and zero injected live links. |

Independent fixtures, CLI logs, source fingerprints, retention matrix and adapter observations are
retained in the local evaluation folder. Review constraints are human/agent judgments; the static
architecture gate is not claimed to prove semantic uniqueness of all prose.

## Speed and cost

| Measurement | v13.0.1 | v13.1.0 |
| --- | ---: | ---: |
| Entry plus five mandatory core guides, regex words | 8,220 | 5,401 |
| Entry plus all references, regex words | 59,791 | 36,964 |
| Imperative-negative phrase search hits | 586 | 13 |
| Large-container one-create calls | 51 | 51 |
| Twenty-event calls / writes / list pages | 63 / 40 / 18 | 63 / 40 / 18 |
| Twenty-event run size | 521 KiB | 521 KiB |
| Same-input local compute sample | 2.1 s | 2.0 s |
| Packaged files | 155 | 155 |
| Deterministic ZIP bytes | 400,480 | 343,649 |

Core instruction load is 34.29% lighter; total reference text is 38.18% lighter. The remaining phrase
hits describe actual limitations or behavior, rather than appended exception instructions. These
counts are diagnostic evidence, not a quality score. The timing sample does not establish a speedup;
execution paths and remote call counts are unchanged. The report uses an additional local graph
inspection, without adapter calls.

Local archive SHA-256:
`8d101829798ab265959e419518a2cc9b3c67c1c2284fb8ebdd263078322837ec`.
Published assets and installed bytes are checked separately at release installation.

## Field-test boundary

The field test must establish actual host authentication, GTM saved-state behavior, inspected native
template fields, consent/identity timing, transport and vendor receipt for its authorized scope.
Setup/cleanup-only tags remain outside the supported execution model. Other native structures
without deterministic field proof retain inspected agent review.

GA4 User-ID remains a configuration field with its approved lifecycle. An `other` destination remains
an unresolved approved-input decision; it requires an amendment identifying its real destination.
It is intentionally blocked at its owning branch, while independent ready work can proceed.

Raw evidence is retained in `configure-gtm-prose-evaluation-2026-10-14`; private paths and external
client data are excluded from the release repository and installed package.
