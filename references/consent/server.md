# Server consent and data governance

## Record topology per destination

Record consent mode, transport policy, exact web/server enforcement, signal authority, unknown-state
behavior and event coverage. Each active server destination binds one effective mechanism:
`incoming-google-consent-native`, `server-template-native-consent`,
`server-additional-consent-check` when that exact template exposes/requires it,
`server-blocking-trigger`, or `none` under its explicit policy.

## Assign collection and destination roles

| Role | Required policy and mechanism |
| --- | --- |
| Direct browser destination | Its own [web consent](web.md) and [lifecycle](lifecycle.md). |
| Web transporter | Approved browser-collection fields/timing and eligibility, with documented signals on each applicable event. |
| Google server destination | [Google-native state](google.md#server-pipeline-ownership) carried from its web owner and processed by the receiving tag. |
| Non-Google destination | Exact approved template-native mechanism or one server exception covering each destination event. |
| Hybrid | Independent declared authority per destination and its required transported signal. |

Carrier policy is resolved independently of downstream eligibility. Where the approved design also
uses a destination-vendor block on the transporter, bind that native block and its covered event scope,
distinct roles and intentional double-gate justification. Unresolved carrier policy holds the affected
architecture. Required native state handling can coexist with a separate basic eligibility role.

Strict/basic Google collection requires approved pre-transport eligibility. `always-transported`
with `incoming-google-consent-native` needs the corresponding approved advanced/native policy.
Bind actual server block references separately from ordinary Event Data business triggers.

## Establish event coverage

Every event capable of firing the destination carries its documented grant/deny/unknown state.
Readiness, consent updates and business occurrences retain distinct semantics. Unknown/absent state
fails closed unless the explicit policy establishes another supported outcome.
[Lifecycle](lifecycle.md) owns event recovery and revocation expectations.

## Limit data exposure

[Identity](../data/identity.md) owns permitted values and consumer scope. Apply destination-local
mapping or a scoped [Transformation](../server/transformations.md) to restrict fields to authorized
consumers, with recorded policy and technical ownership.

Official foundation:
https://developers.google.com/tag-platform/tag-manager/server-side/consent-mode
