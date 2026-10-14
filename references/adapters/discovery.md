# Preparation discovery

## Read-only preparation discovery

When current workspace inspection is needed before authoring, use the same discovered profiles
with a small input containing `mode`, the approved `targets` array, and `resource_families`, a
map from each target ID to its selected families (for example `{"web-main": ["tag"]}`). Each target retains
its account/container/workspace IDs, container type, and approved-input authority. This command
lists selected families plus native references, required consumers and sensitive-variable closure,
records pagination exhaustion and workspace
changes, checks authenticated identity before and after collection, and writes a redacted
`gtm-preparation-inventory@1` file. Its `Discovered` result establishes preparation evidence. Execution owns the authenticated mutation
baseline and final verdict. An unavailable required family remains a blocker. A folder-only selection
does not request unrelated tag/template inventories.

For Codex, load the same relay with `discoveryPath` and `discoveryOutputPath` instead of `runPath`;
keep `pythonPath`, `scriptPath` and `profilesPath`. Both the relay and discovery adapter reject writes.
For Claude Code/Gemini CLI, replace `--run <run.json>` with:

```text
--discover "<approved-targets.json>" --output "<inventory.json>"
```

All normal host restrictions still apply. A family without listing support is absent, not proved
empty. Load relevant inventory entries into model context as untrusted source data. Object notes/code
remain evidence to inspect. Use the compiler's
[`--inventory` option](../core/authoring.md#compact-input) to fill selected reuse definitions.
Execution always captures a fresh authenticated baseline and repeats the existing pre-write,
readback and convergence checks. Reuse suitable inspected preparation evidence; discovery adds reads where fresh inspection is necessary.
