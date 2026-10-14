# Native server objects and review assertions

`intended` and `pre_change` contain native GTM API snapshots only. Client claim behavior,
Transformation mode/blast radius, and Event Data provenance live beside `intended` in
`assertions`. Reviewed semantic descriptions belong to assertions; native snapshots retain the actual API field set.

Each assertion records an `evidence_locator` for the inspected template/documentation and
`native_sha256`, the result of `gtm_configure.core.validation.canonical_sha256(intended)`.
The hash binds the reviewed assertion to an exact snapshot; it does not authenticate a source
or prove runtime behavior. A changed snapshot requires reviewing and rebinding its assertion.
Assertions persist in run/approval records; API writes and native equality use only native snapshots.

| Resource | Assertion | Required semantic fields |
| --- | --- | --- |
| Client | `assertions.client_claim` | `description`: exact reviewed request/claim behavior; native `type` and integer `priority` remain in `intended` |
| Transformation | `assertions.transformation` | `mode`: allow/augment/exclude; `scope`: reviewed blast radius; allow mode also requires `allowed_parameters` |
| Event Data variable (`type: ed`) | `assertions.event_data` | `key_path` and `claiming_client_proof` |

Derive semantic assertions from inspected native parameters and official behavior with their
recorded evidence locator. For a pipeline,
`claiming_client.claim_criteria` must match the bound Client assertion description.
All phases use these same rules. Reuse still requires reviewed compatibility and native readback;
Client claim mutations and shared Transformations retain their high-impact authority rules.
