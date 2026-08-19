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
request class, one intended claiming Client, and several downstream server consumers. Do not create
one artificial Client per web tag or assume each incoming event has one destination.

For each request class, prove exactly one intended claiming Client and reachability from generated
Event Data to every required destination. Keep the web and server object keys target-scoped:
`<target-id>::<resource-family>::<semantic-name>`.

## Prove authority per target

Record explicit approved target authority for each account, container, and workspace. A discovered
`server_container_url`, custom domain, server container ID, or shared account is intake evidence,
not permission to mutate. Routine authority may cover isolated tags, triggers, Event Data variables,
folders, and reuse of a compatible Client. Client claim behavior, broad Transformations, template
permission changes, live endpoint cutover, replacement, and removal remain high impact.

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
7. Existing live sender endpoint cutover, last.
8. Readback of every target, static pipeline comparison, and identical-rerun no-op.

Creating an isolated inactive sender earlier is harmless only when it cannot emit. Never point an
active sender at an incomplete or unverified receiver.

## Contain failures by dependency

Stop a failed or uncertain operation and its transitive dependents. Continue independent ready
subtrees when target authority, adapter state, and dependencies remain safe. A failed Client blocks
all events it would claim and the cutover; a failed Meta tag does not block an independent verified
GA4 subtree. Never retry an ambiguous mutation until readback establishes whether it saved.

Record the last verified operation, uncertain frontier, blocked dependents, and next authoritative
readback per target. Overall `Partial` must not hide a completely safe target result.

## Separate saved configuration from publication

Configuration success is saved and readback-verified state; open publication dependencies do not
make it `Blocked`. Record the external order:

1. publish the server workspace;
2. execute server-container recette;
3. publish the web endpoint cutover;
4. execute web and cross-preview/end-to-end recette.

The skill never performs those steps or claims that either preview ran.
