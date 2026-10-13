# v12.0.0 validation record

Compared locally on 2026-10-13 against the frozen v11.0.0 tag, using the same Python environment.
The review response and ownership boundaries are mapped in [architecture](architecture.md).

| Gate | Observed result |
| --- | --- |
| Repository regressions | 459 tests and 508 subtests pass; relay runtimes required; no skips |
| Extracted runtime archive | 28 packaged tests pass |
| Independent forward test | Web and pipeline prepare, initialize, validate, conform and render successfully; fresh baselines are correctly required before execution |
| Architecture | No detected duplicate literal constant owners, substantial identical function bodies, private cross-module access, inverted core/domain imports, dependency cycles or unreferenced top-level definitions |
| Schema and interface | Shared records reject unknown keys; current versions, routed links, filename labels and every packaged CLI help pass |
| Code and package | Ruff lint/format, skill scaffold, Git whitespace and deterministic package checks pass |
| Single create, large inventory | 51 API calls in both versions; one write |
| 20 events | 63 API calls, 40 writes and 18 list pages in both versions |
| Local 20-event compute | 1.8 s on v11.0.0; 1.9 s on v12.0.0 in the paired measurement |
| Artifact size | Request 45 KB and contract 62 KB unchanged; run 519 KB to 521 KB |
| Error/recovery probe | All 16 outcomes identical across baseline-read and create failures |
| Synthetic redaction | Zero surviving secret canaries: 18 leak and 5 control cases; 4 of 6 non-secret cases accepted in both versions |
| Local export redaction | Identical flags across 614 distinct objects from four exports; only aggregate counts retained |
| Report injection | Zero injected summary headings or active injected links in both versions |
| Branch coverage | 72.9% to 73.1% with the same harness; statement coverage 80.5% to 80.9% |

## Interpretation and limits

The two conservatively blocked non-secret canaries are public browser API-key/token examples.
This release preserves that existing privacy policy; it does not broaden credential acceptance.
The export sample differs from the earlier review's five-container sample, so its counts are not
a direct comparison with that report. Raw exports and their contents are absent from this repository.

Coverage instruments the main pytest process and excludes child-process CLI paths. The earlier
review's approximately 77% branch figure used a different measurement setup; the table reports
a fresh comparison of both tags with one harness. Small local timing differences are not network
latency or billing estimates. The hash prefix accounts for the small run-size increase.

Audit tools were run unchanged where their imports permitted it. The local test harness redirects
pre-refactor module names; redaction probes received only source-path loader adaptations. No
compatibility aliases are included in the runtime package. All original regression methods were
retained when moving them to behavior owners; new cases cover the changed invariants.

The largest web-domain coordinator was decomposed by feature. Several cohesive functions still
exceed 200 lines; line count is diagnostic rather than a release rule. Static analysis is conservative
and cannot prove that every semantically similar rule has been unified. There is no live GTM smoke
run, vendor acceptance, publication or version creation in this evidence.
