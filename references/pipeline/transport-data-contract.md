# Transport data contract

## Contents

- [Prove every layer](#prove-every-layer)
- [Select the transport owner](#select-the-transport-owner)
- [Govern shapes](#govern-shapes)
- [Assign page-view ownership](#assign-page-view-ownership)
- [Route environments safely](#route-environments-safely)
- [Hand off runtime proof](#record-the-runtime-boundary)

## Prove every layer

For every outgoing field, record:

1. approved source path, type, shape, and timing;
2. resolved web variable and type;
3. wire parameter and encoded shape;
4. claiming Client behavior;
5. server Event Data key path and type;
6. server mapping or Transformation owner;
7. installed-template field and destination type;
8. missing behavior and runtime verification note.

Each source path and its claiming-Client/Event Data projection requires explicit provenance and
shape evidence.

## Select the transport owner

Reuse a compatible Google tag when measurement identity, endpoint, consent, page-view ownership,
and environment lifecycle align. Create a dedicated transport Google tag only when one of those
concerns needs isolation. Use a Constant or LUT for the endpoint only when reuse, safe environment
routing, or ownership clarity justifies it; a literal owned field can be simpler.

Bind the pipeline endpoint to the saved endpoint field of that owner. In each linked consent
topology, enumerate the actual web tags that can emit transported occurrences. A sender without a
direct endpoint must bind the same destination identity as the owner so its inherited endpoint is
provable. Native endpoint/destination bindings establish transport ownership.

## Govern shapes

There is no universal rule that a server container accepts only two arrays. For the documented
Google tag → Google Analytics Client route, `items` is an array and `user_data` is an object with
nested paths. Prove any other non-scalar field through the exact sender protocol, Client-generated
Event Data, and destination template.

If a required nested shape cannot survive, set the field flow `blocked` unless an approved
serialization method has a named server parse owner. The approved shape/cardinality survives end to end through its named serialization/parse owners.

Prefer native destination mapping, direct Event Data, a template mapping table/item projection, or
a narrow server variable before a scoped Transformation. A broad Transformation is not a local
array converter for one media tag.

## Assign page-view ownership

For every measurement destination, decide whether page view comes from the Google tag, a dedicated
event tag, another proven route, or intentionally nowhere. Reconcile automatic page view, Enhanced
Measurement, SPA events, and any direct-browser destination before enabling server transport.
Assign the approved route one effective owner for each destination/occurrence.

## Route environments safely

Use explicit hostname/environment mapping when endpoints differ. Unknown hosts resolve to a closed or intentionally non-production outcome. Record
CSP and tagging-domain work as external infrastructure dependencies.

## Record the runtime boundary

Static readback proves configuration, not transport behavior. Record the unresolved runtime
verification dependency without claiming it was executed. A separate recette independently uses
the tracking plan and live GTM/Preview evidence to reconcile browser request, claiming Client,
generated Event Data, server trigger, resolved variables, outgoing request, response, consent, and
any cross-preview value that must match.

Official foundations:

- https://developers.google.com/tag-platform/tag-manager/server-side/send-data
- https://developers.google.com/tag-platform/tag-manager/server-side/common-event-data
