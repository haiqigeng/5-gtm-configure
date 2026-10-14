# Browser/server deduplication

## Contents

- [Require a contract only for overlap](#require-a-contract-only-for-overlap)
- [Choose one occurrence identity](#choose-one-occurrence-identity)
- [Configure shared ID generation](#configure-shared-id-generation)
- [Map vendor fields independently](#map-vendor-fields-independently)
- [Prove runtime equality externally](#prove-runtime-equality-externally)

## Require a contract only for overlap

Create a dedup contract when the same destination event can reach the same platform through more
than one ingestion route. Choose `single-channel`, `server-replaces-browser`, `dual-shared-id`,
`platform-native`, or `not-applicable` from current product evidence. The exact product contract determines its occurrence fields. A generic `dual-shared-id` contract is invalid for Google Ads
or Floodlight: use their current product-specific replacement/duplication mechanism and fields.

## Choose one occurrence identity

In an authorized web-only run, prepare browser and transporter consumers without inventing a
server target. Link `external_receiver_dependency_id` to a requirement-scoped external dependency
describing receiver ownership and required verification. For a supplied stable source, provide
`consumer_bindings` with the exact native `field_path` for every browser/transporter ID field;
generated sources use the existing `generation.consumer_bindings`. References in notes or an
unrelated field do not prove identity mapping. Full pipeline mode still requires receiver proof.

For `dual-shared-id`, use one value everywhere:

1. For dual-delivery purchase, require the approved stable transaction/order/occurrence identity
   supported by the exact vendor; retain any separate cross-channel identifier it also requires.
2. For another event, use a stable approved occurrence ID such as a lead ID.
3. Otherwise use an explicitly supplied site/dataLayer event ID, an inspected template-native
   occurrence identity, or the approved shared generation route below.
4. If none meets the occurrence and delivery contract, keep overlap blocked or use the approved
   single delivery channel.

The source value may map to different browser/server fields. One occurrence has one shared stable
identity, distinct from user/session identity and preserved unchanged through retries and receivers.

A template-native source qualifies only when its reviewed behavior produces one shared value for
the exact occurrence and execution paths. Two references to a variable do not themselves prove
equal resolved values.

## Bind native identity fields

For supplied IDs, `consumer_bindings` covers exactly the browser and transporter object keys.
For generated IDs, the same bindings live in `generation.consumer_bindings`. Each path must name
its declared `browser_field` or `transported_parameter`: metadata and unrelated parameters cannot
prove identity. Native Parameter rows and event-settings tables are resolved by their actual field
names. A single-component path such as `["event_id"]` selects that effective native field,
including inspected shared settings variables; a local override must still use the shared source.
Include those settings variables as same-target objects with their native bodies and dependencies.

Use the proved identity `field_flows` to identify participating receivers: match the requirement,
`destination_field` to `server_field`, and Event Data path to `server_event_data_path`. Those
`receiver_owner` keys must belong to the matching event flow; unrelated destination consumers
need not carry this vendor's identity field. Each participating receiver's effective `server_field` must reference an included, active,
same-target native Event Data variable (`type: "ed"`) whose `keyPath` equals
`server_event_data_path`. Include that variable and its consumer dependency. A literal, missing
mapping, unrelated Event Data path or generator variable fails this static gate. The current
supported route requires that explicit Event Data mapping; template-internal automatic identity
behavior needs an inspected implementation route rather than a declaration in notes. Product
field meaning and live occurrence equality still require the independent review below.

## Configure shared ID generation

For an approved non-purchase dual-delivery event without a stable source ID, create or reuse one
variable using an inspected maintained variable template. Prefer a suitable reviewed Gallery
template over writing a random Custom JavaScript function. Stape's
[Unique Event ID template](https://github.com/stape-io/unique-event-id-variable) is one candidate,
not a universal requirement or Google endorsement. Inspect its current code/version, permissions,
missing-event behavior, window state and collision limitations. Its current implementation combines
page state with the GTM event index; it is not a guaranteed UUID or a stable business/order ID.
The inspected generator contract establishes per-occurrence stability across all consumer evaluations.

Use `source_type: "generated-event-id"` with `strategy: "dual-shared-id"`. Its `generation` record
applies even when the generator variable already exists; `template-native` is not a way to bypass
these generation checks. The record
contains `template_object_key`, `review_locator`, and
`consumer_bindings`. Each binding names `object_key` and a `field_path` array inside its native
`intended` body. String path components select named GTM Parameter rows; integers select list
positions. Example: `["parameter", "eventId", "value"]`. Inspect that this is the actual vendor ID
field; a path existing in JSON does not establish its product meaning.

The review locator must identify the template source/version and permission review, its association
with the saved native type, and evidence that repeated reads on one event are stable while distinct
events receive distinct IDs. Include the installed template as a `reuse`/`untouched` operation with
its authoritative `object_id` and full inspected `templateData`; the generator variable depends on
it. If installation is needed, complete the separately authorized template import and readback
first, then use its observed native type in the variable's native configuration. The installed
source's `INFO.id` supplies that native type binding. Follow [template governance](../templates.md).

Bind every browser and transporter consumer's actual native ID field to that one variable. This generated-ID route covers the same direct source-event triggers in one web container, once
per event. Sequencing, replay, cross-event/container and purchase routes require a supplied stable
identity materialized upstream.
Inspect the complete tag inventory for inbound setup/cleanup references as well. Stape's
[sequencing warning](https://stape.io/blog/gtm-tag-sequencing-event-id-fix) documents a mismatch in
sequenced paths. Those paths require an ID materialized upstream and then mapped as a supplied
stable source; merely evaluating a generator in each tag is insufficient.

Send the ID in the transport event and consume that exact Event Data value in every relevant
server destination, without regeneration. Keep vendor-specific companion keys and event/asset
mapping. Saved readback verifies the template, variable, field bindings and graph; it cannot prove
browser execution, cross-request deduplication or random uniqueness.

## Map vendor fields independently

Open current official product guidance and the installed template. The source is vendor-neutral,
but the destination fields, companion identifiers, event names, assets, and windows are not. For
example, Snap currently distinguishes browser `client_dedup_id`, CAPI `event_id`, browser
`transaction_id`, and CAPI `custom_data.order_id`; retain each documented role independently of
value equality.

## Prove runtime equality externally

Record that runtime recette must independently prove same occurrence, same resolved identifier, same asset,
compatible event name, browser/transporter timing, server consumption without regeneration, and
distinct identifiers across repeated events, reloads, and SPA transitions. Saved GTM readback
cannot certify deduplication.
