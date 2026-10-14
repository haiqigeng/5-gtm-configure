# Web-to-server pipeline architecture and workflow

## Contents

- [Model the pipeline as a graph](#model-the-pipeline-as-a-graph)
- [Prove authority per target](#prove-authority-per-target)
- [Discover before design](#discover-before-design)
- [Build receiver first](#build-receiver-first)
- [Contain failures by dependency](#contain-failures-by-dependency)
- [Separate saved configuration from publication](#separate-saved-configuration-from-publication)

## Model the pipeline as a graph

Use `pipelines[]`. A pipeline may have several web senders, one receiving server target for a
request class, one intended claiming Client, and several downstream server consumers. Client ownership follows request class; downstream consumers follow the generated events.

For each request class, prove exactly one intended claiming Client and reachability from generated
Event Data to every required destination. Keep the web and server object keys target-scoped:
`<target-id>::<resource-family>::<semantic-name>`.

## Prove authority per target

Establish each sender/receiver's authority under [target authority](../core/authority.md#target-authority).
A discovered endpoint is relationship evidence. Record the requested Client, Transformation,
template and cutover changes explicitly so their impact is reviewed against that authority.

## Discover before design

Capture a complete paginated baseline and adapter capabilities per target. Inspect:

- existing transport owner and endpoint routing;
- Client types, priority, activation/claim criteria, and request classes;
- generated Event Data and non-scalar shapes;
- server destination fan-out and overlapping browser routes;
- consent signal transport and enforcement per destination;
- installed server templates, versions, permissions, allowed hosts, secrets, and defaults;
- page-view ownership, deduplication, environment isolation, and pre-existing workspace changes.

## Build receiver first

The dependency order is receiver-first:

1. Server workspace, baseline, and capabilities.
2. Compatible claiming Client readback or explicitly authorized Client change.
3. Server Event Data variables, scoped Transformations, triggers, and destination tags.
4. Authoritative server readback and graph comparison.
5. Web endpoint/settings variables and transporter event tags.
6. Browser destinations retained for dual delivery and their shared dedup mappings.
7. Mandatory transport-owner cutover, last, whether the sender route is new or changes an existing endpoint.
8. Readback of every target, static pipeline comparison, and identical-rerun no-op.

An active sender requires a complete verified receiver. Earlier isolated sender preparation remains
inactive until that dependency is satisfied.

## Contain failures by dependency

Use [dependency readiness and recovery](../core/execution.md#contain-failures-by-dependency).
The claiming Client is a prerequisite of its receiver consumers and cutover. Destination branches
remain independent where their actual dependencies allow it. Keep recovery frontiers target-scoped
so an overall partial result preserves each target's verified work.

## Separate saved configuration from publication

The configuration verdict follows [acceptance](../core/acceptance.md). Record these separately owned
rollout dependencies in order:

1. run server Preview acceptance against the saved draft;
2. run coordinated web/server Preview and end-to-end acceptance before deployment;
3. obtain the applicable publication authority, then deploy the verified server workspace;
4. deploy the verified web cutover and run postpublication smoke checks.

Google supports testing workspace drafts in [Preview](https://support.google.com/tagmanager/answer/6107056)
and inspecting the receiving pipeline in [server Preview](https://developers.google.com/tag-platform/tag-manager/server-side/debug).

These steps belong to the external rollout owners under [scope](../core/authority.md#boundaries).
The configuration handoff records their pending or independently evidenced state.
