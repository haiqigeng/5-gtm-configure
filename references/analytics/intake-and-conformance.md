# Tracking-plan fidelity and conformance

## Preserve approved semantics

[Authority](../core/authority.md) assigns analytics design to the approved tracking plan or exact
analyst decision. Implement its event/classification, outgoing fields/namespaces, sources/literals,
transformations/missing behavior, timing, repeatability and business filters. Technical GTM choices
realize that contract through authorized targets, variables, references, consent and execution.
A changed collection decision requires an explicit amendment.

## Resolve the relevant source scope

Classify relevant artifact parts as `included`, `reference-only`, `excluded` with reason, or
`ambiguous` with the needed decision. Approval determines scope independently of sheet visibility.
Hold only affected dependent requirements. Preserve stable requirement identity and sheet/cell/row
locators; use an immutable supplied ID or stable business ID such as `GA4::generate_lead`.
Mutable row order remains in the locator. The run initializer consumes a validated contract.

### Import a ga4-tracking-plan delivery

Use `scripts/configure_gtm.py import-plan` on the complete approved delivery. It validates handoff
`2.0.0`, canonical plan `6.0.0` and SHA-256 for every inventoried artifact, retaining producer version
as provenance. The normalized machine requirements are authoritative intake; XLSX is the human
review surface. Event IDs become `GA4::<event_name>`.

The [collection field model](../core/authoring.md#collection-field-model) maps declared destination
and scope, preserving source paths, nullable/conditional semantics, business timing and clearing
instructions. `ga4_user_id` maps to `configuration_fields.user_id` with the original source and
approved [identity lifecycle](../data/identity.md). `other` stays in `unresolved_fields` because its
destination surface is unspecified. Resolve it with amended approved requirements and retain the
original delivery plus amendment. [Readiness](../core/execution.md#contain-failures-by-dependency)
holds dependent operations until destination and implementation are resolved.

A suite workbook alone needs its complete approved machine delivery. Independent client plans use
the general semantic intake above. Current contracts are consumed directly; historical deliveries
remain evidence under the [maintenance policy](../maintenance.md).

## Resolve technical discrepancies

[Evidence review](../core/evidence.md#research-procedure) owns `blocking-error`, `advisory` and
`implementation-note` classification. For a material discrepancy record requirement, approved value,
official finding, class, impact, source and required decision before the affected write. Valid
advisories preserve the approved contract; unmet applicable requirements hold their dependent graph.
Unresolved blockers remain in the handoff. Required, conditional, recommended and optional fields
retain their documented classification.

## Prove exact conformance

Freeze the approved projection from the original source and explicit amendments before authoring
the implementation. Retain the original artifact hash and sheet/cell/row locators with that projection;
recovery consumes the same immutable UTF-8 evidence. Compare approved versus intended semantics:
included IDs, event names, timing,
repeatability, filters, exact field sets/namespaces and source paths/literals. Use importer output
`approved-semantics.json` directly when available. GTM infrastructure stays outside that semantic
projection. A difference requires correction, blocking classification or an explicit amendment.

The proof chain is:

`approved requirements -> intended requirements -> reviewed native intent -> verified saved native state`

Schemas validate both semantic projections before equality. Supported topologies and scalar GA4
bindings have deterministic native proof; the agent reviews other supported scopes. Runtime
comparison verifies saved native fields against that reviewed intent.

## Use the deterministic comparator

Each JSON projection contains `scope` (`included`, `reference_only`, `excluded`) and `requirements`
with unique stable string IDs and collection semantics. Parameter maps represent unordered field
sets. Requirement/scope-list order is non-semantic; nested arrays remain ordered. Metadata outside
`scope`/`requirements` stays outside the comparison.

~~~powershell
python "<skill-dir>/scripts/configure_gtm.py" conformance --approved approved.json --candidate intended.json
~~~

Exit `0`: semantic projection equality; `1`: deterministic difference; `2`: invalid input/invocation.
The comparator establishes equality of its inputs. Source fidelity comes from the independently
frozen source projection and amendments; a projection generated from the candidate does not establish
that independence. Preserve the result with implementation evidence and bind behavior checks to the
exact final candidate hash. Saved-state proof uses native comparison and convergence,
completing the chain above through the same approved requirements.
