# Server Transformations

## Contents

- [Use the narrowest owner](#use-the-narrowest-owner)
- [Classify blast radius](#classify-blast-radius)
- [Preserve shapes and semantics](#preserve-shapes-and-semantics)
- [Verify consumers](#verify-consumers)

## Use the narrowest owner

Choose, in order: native automatic mapping, direct Event Data, template mapping/projection, narrow
server variable, scoped Transformation, then an explicitly authorized custom server template or
HTTP route. Do not add a broad Transformation merely to reshape one destination's item list.

## Classify blast radius

A single-destination Transformation can be routine when its exact tag scope is proven. A shared
allow, augment, redact, or exclude rule affecting several destinations is high impact. Capture
pre-change state, every affected tag, match conditions, parameter actions, order interactions, and
explicit authority before mutation.

## Preserve shapes and semantics

Never flatten, stringify, coerce, truncate, or drop a non-scalar field without approved semantics
and an explicit parser/owner. Use allowlists and redaction carefully: a field removed before a tag
runs cannot be recovered by that tag. Keep destination-specific field names outside approved
analytics semantics.

## Verify consumers

Read back Transformation type, parameters, scope/conditions, affected tags, folder, fingerprint,
and ordering evidence. Record that server recette must independently compare Event Data before and after the
Transformation and each destination's outgoing payload.

Official foundation:
https://developers.google.com/tag-platform/tag-manager/server-side/transformations
