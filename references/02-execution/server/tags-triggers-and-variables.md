# Server tags, triggers, and variables

## Contents

- [Trigger from Event Data](#trigger-from-event-data)
- [Use server variables deliberately](#use-server-variables-deliberately)
- [Configure tags from their own schema](#configure-tags-from-their-own-schema)
- [Bind saved topology](#bind-saved-topology)

## Trigger from Event Data

Use server Custom Event triggers or exact server variable conditions against generated Event Data.
Do not copy web click, form, DOM-ready, history, scroll, timer, visibility, YouTube, or dataLayer
trigger logic. A server all-events trigger is acceptable only for a destination designed to process
all claimed events; a vendor conversion tag normally uses the exact transported event and any
approved filter.

## Use server variables deliberately

Prefer automatic event-data mapping when the native/template tag documents it. Otherwise use a
direct Event Data variable for one key path, a supported template mapping table for a destination
projection, or a narrow server variable template. Constants are appropriate for stable IDs and
safe references, not literal credentials. Never assume a nested dataLayer object survives the
claiming Client.

## Configure tags from their own schema

Inspect the exact server tag/template version. Map business events to the vendor's server product,
not to its Pixel schema or GA4 by analogy. Record destination identity, event/action, time/source,
matching fields, item cardinality, consent, dedup strategy, automatic fields, credentials, and
outgoing request cues. A direct vendor API product does not prove that a compatible GTM server
template exists.

## Bind saved topology

Bind semantic trigger and variable references to the exact saved tag fields. Read back returned
IDs, translate them into target-scoped semantic references, and compare the whole intended object.
Do not synthesize web built-in trigger IDs in a server graph.
