"""Behavioral tests owned by report."""

from support import authenticated_delivery as fixture_authenticated_delivery
from support import consent_and_fields as fixture_consent_and_fields
from support import durable_evidence as fixture_durable_evidence
from support import input_and_execution as fixture_input_and_execution
from support import native_execution as fixture_native_execution
from support import transport_and_state as fixture_transport_and_state


class TestAuthenticatedDelivery(fixture_authenticated_delivery.Audit102FollowupFixture):
    @fixture_authenticated_delivery.patch(
        "gtm_configure.runtime.validation.validate_document", new=lambda value: value
    )
    def test_report_data_cannot_inject_sections_links_html_or_code_fences(self):
        document = fixture_authenticated_delivery.run_document()
        payload = "Name\r\n## Executive summary\n[approve](https://example.invalid/phish) <img src=x> ` ```` \u202e"
        document["object_changes"][0]["name"] = payload
        document["object_changes"][0]["justification"] = payload
        document["run"]["id"] = payload
        document["external_dependencies"] = [
            {"status": "open", "owner": payload, "action": payload}
        ]
        for embedded in (False, True):
            report = fixture_authenticated_delivery.render_markdown(
                document, embed_machine=embedded
            )
            human = report.split("`````json")[0]
            self.assertEqual(human.count("\n## Executive summary\n"), 1)
            self.assertNotIn("[approve](", human)
            self.assertNotIn("<img", human)
            self.assertNotIn("\u202e", human)
            if embedded:
                self.assertEqual(
                    fixture_authenticated_delivery.json.loads(
                        report.split("`````json\n")[1].rsplit("\n`````", 1)[0]
                    )["run"]["id"],
                    payload,
                )
        self.assertEqual(document["run"]["id"], payload)


class TestInputAndExecution(fixture_input_and_execution.AuditRegressionsFixture):
    def test_runtime_to_render_has_no_canary_bytes(self):
        class Source(fixture_input_and_execution.FakeAdapter):
            def list_resource_page(self, family, cursor):
                return {
                    "items": super().list_resource_page(family, cursor)["items"]
                    + [
                        {
                            "name": "Existing sensitive tag",
                            "tagId": "sensitive-existing",
                            "type": "gaawe",
                            "parameter": [fixture_input_and_execution.row("token_secret")],
                        }
                    ]
                    if family == "tag"
                    else super().list_resource_page(family, cursor)["items"],
                    "next_cursor": None,
                }

        adapter = Source()
        run = fixture_input_and_execution.create_from_contract(
            fixture_input_and_execution.valid_web_contract(),
            run_id="end-to-end",
            source_locator="Synthetic request",
        )
        target = run["run"]["targets"][0]
        adapter.bind_target(target)
        registry = fixture_input_and_execution.TargetAdapterRegistry()
        registry.register(
            target, adapter, fixture_input_and_execution.capabilities("tag", "trigger")
        )
        with fixture_input_and_execution.tempfile.TemporaryDirectory() as temp:
            path = fixture_input_and_execution.Path(temp) / "run.json"
            fixture_input_and_execution.atomic_write(path, run)
            fixture_input_and_execution.execute_ready_operations(path, registry)
            fixture_input_and_execution.verify_idempotent_rerun(path, registry)
            result = fixture_input_and_execution.load_document(path)
            self.assertEqual(result["run"]["status"], "Configured")
            output = fixture_input_and_execution.render_markdown(result, embed_machine=True)
            (fixture_input_and_execution.Path(temp) / "result.md").write_text(
                output, encoding="utf-8"
            )
            self.assertIn("Credential-like literal", output)
            for artifact in fixture_input_and_execution.Path(temp).rglob("*"):
                if artifact.is_file():
                    self.assertNotIn(
                        fixture_input_and_execution.CANARY.encode(),
                        artifact.read_bytes(),
                        str(artifact),
                    )

    @fixture_input_and_execution.patch(
        "gtm_configure.runtime.validation.validate_document", new=lambda value: value
    )
    def test_delta_report_summarizes_unchanged_objects(self):
        run = fixture_input_and_execution.create_from_contract(
            fixture_input_and_execution.valid_web_contract(),
            run_id="render",
            source_locator="Synthetic request",
        )
        prototype = fixture_input_and_execution.deepcopy(run["object_changes"][0])
        prototype["action"] = "reuse"
        prototype["name"] = "UNCHANGED_DETAIL"
        run["object_changes"].extend(
            fixture_input_and_execution.deepcopy(prototype) for _ in range(80)
        )
        output = fixture_input_and_execution.render_markdown(run)
        self.assertIn("Objects without planned changes: 80", output)
        self.assertNotIn("UNCHANGED_DETAIL", output)
        self.assertIn("before → intended", output)


class TestDurableEvidence(fixture_durable_evidence.CurrentRegressionHardeningTestFixture):
    def test_markdown_preserves_analyst_operational_detail_without_recette_coupling(self) -> None:
        run = fixture_durable_evidence.materialize(
            fixture_durable_evidence.valid_pipeline_contract()
        )
        markdown = fixture_durable_evidence.render_markdown(run)
        for heading in (
            "## Executive summary",
            "## Analyst and developer object change log",
            "## Requirement, payload, and consent mapping",
            "## Per-tag web execution policy",
            "## Client-to-server pipeline proof",
            "## External actions, publication, and recette",
        ):
            self.assertIn(heading, markdown)
        self.assertIn("Rationale:", markdown)

    def test_report_exposes_native_id_from_saved_object_not_context(self) -> None:
        run = fixture_durable_evidence.materialize(fixture_durable_evidence.valid_web_contract())
        operation = next(item for item in run["object_changes"] if not item["dependencies"])
        saved = fixture_durable_evidence.expected_graph(operation)
        saved["objects"][0]["triggerId"] = "saved-trigger-501"
        saved["context_objects"] = [
            {
                "target_id": operation["target_id"],
                "object_type": "trigger",
                "name": "Unrelated trigger",
                "triggerId": "unrelated-trigger-999",
            }
        ]
        run = fixture_durable_evidence.checkpoint_operation(
            run,
            operation_id=operation["operation_id"],
            state="verified",
            note="Authoritative readback matched.",
            saved=saved,
        )
        markdown = fixture_durable_evidence.render_markdown(run)
        self.assertIn("Saved object ID: saved-trigger-501", markdown)
        self.assertNotIn("unrelated-trigger-999", markdown)
        self.assertIn("Readback comparison: passed", markdown)


class TestNativeExecution(fixture_native_execution.RecoveryCorrectionsTestsFixture):
    def test_render_refuses_same_path_and_hardlink_without_touching_run(self):
        with fixture_native_execution.tempfile.TemporaryDirectory() as directory:
            path = fixture_native_execution.Path(directory) / "run.json"
            fixture_native_execution.atomic_write(
                path,
                fixture_native_execution.create_from_contract(
                    fixture_native_execution.valid_web_contract(),
                    run_id="render",
                    source_locator="synthetic",
                ),
            )
            before = path.read_bytes()
            alias = fixture_native_execution.Path(directory) / "alias.json"
            fixture_native_execution.os.link(path, alias)
            for output in (path, alias):
                result = fixture_native_execution.subprocess.run(
                    [
                        fixture_native_execution.sys.executable,
                        str(fixture_native_execution.ROOT / "scripts/configure_gtm.py"),
                        "run",
                        "render",
                        "--run",
                        str(path),
                        "--output",
                        str(output),
                    ],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual(alias.read_bytes(), before)


class TestConsentAndFields(fixture_consent_and_fields.UtilityCorrectionsFixture):
    def test_ungated_policy_executes_and_is_plain_in_report(self):
        doc, backend = fixture_consent_and_fields.execute(
            fixture_consent_and_fields.ungated_request()
        )
        self.assertEqual(doc["run"]["status"], "Configured")
        self.assertEqual(len(backend.writes), 1)
        self.assertIn("No consent gating", fixture_consent_and_fields.render_markdown(doc))

    def test_analyst_report_labels_parameters_and_retains_unknown_fields(self):
        after = {
            "object_type": "tag",
            "target_id": "web-main",
            "parameter": [
                fixture_consent_and_fields.param("eventName", "generate_lead"),
                {
                    "key": "eventSettingsTable",
                    "type": "list",
                    "list": [
                        {
                            "type": "map",
                            "map": [
                                fixture_consent_and_fields.param("parameter", "form_id"),
                                fixture_consent_and_fields.param(
                                    "parameterValue", "{{DLV - form.id}}"
                                ),
                            ],
                        }
                    ],
                },
            ],
            "unknownFeature": {"enabled": True},
        }
        changes = "; ".join(fixture_consent_and_fields.analyst_field_changes({}, after))
        self.assertIn("Event name: absent → generate_lead", changes)
        self.assertIn("form_id = {{DLV - form.id}}", changes)
        self.assertIn("unknownFeature", changes)
        self.assertNotIn("target_id", changes)
        self.assertNotIn("object_type", changes)


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_all_skipped_reports_deferred_not_progress(self):
        run = fixture_transport_and_state.with_complete_baselines(
            fixture_transport_and_state.create_from_contract(
                fixture_transport_and_state.valid_web_contract(),
                run_id="DEFER",
                source_locator="synthetic",
            )
        )
        for operation in run["object_changes"]:
            run = fixture_transport_and_state.checkpoint_operation(
                run, operation_id=operation["operation_id"], state="skipped", note="Not implemented"
            )
        self.assertEqual(run["run"]["status"], "Deferred")


def test_report_surfaces_field_blocker_before_object_details():
    from copy import deepcopy

    from gtm_configure.runtime.state import create_from_contract, inspect_document
    from support.contracts import with_complete_baselines
    from support.identity import user_id_contract

    contract = user_id_contract()
    requirement = contract["requirements"][0]
    field = deepcopy(requirement["configuration_fields"]["user_id"])
    field["destination"] = "other"
    requirement["unresolved_fields"] = {"destination_pending": field}
    binding = deepcopy(contract["implementation"]["field_bindings"][0])
    binding.update(
        field_scope="unresolved", destination_field="destination_pending", status="blocked"
    )
    contract["implementation"]["field_bindings"].append(binding)
    run = with_complete_baselines(
        create_from_contract(contract, run_id="REPORT", source_locator="synthetic")
    )
    inspection = inspect_document(run)
    assert inspection["blocked_operations"]
    output = fixture_durable_evidence.render_markdown(run)
    summary = output.split("## Targets and baseline")[0]
    assert "destination_pending" in summary
    assert "Root " in summary
    assert "dependent operations held" in summary
    assert "Ready operations: none" in summary
    assert "Resumable: true" in summary


def test_report_tracks_uncertain_write_frontier_through_saved_recovery():
    run = fixture_durable_evidence.materialize(fixture_durable_evidence.valid_web_contract())
    operation = next(item for item in run["object_changes"] if not item["dependencies"])
    for state in ("in_progress", "uncertain"):
        run = fixture_durable_evidence.checkpoint_operation(
            run,
            operation_id=operation["operation_id"],
            state=state,
            note="Synthetic dispatched write with unresolved outcome",
        )
    summary = fixture_durable_evidence.render_markdown(run).split("## Targets and baseline")[0]
    assert "Resumable: false" in summary
    assert operation["operation_id"] in summary
    assert "authoritative readback required" in summary
    assert "before replay" in summary
    recovered = fixture_durable_evidence.checkpoint_operation(
        run,
        operation_id=operation["operation_id"],
        state="verified",
        note="Fresh authoritative readback matched",
        saved=fixture_durable_evidence.expected_graph(operation),
    )
    summary = fixture_durable_evidence.render_markdown(recovered).split("## Targets and baseline")[
        0
    ]
    assert "Resumable: true" in summary
    assert "authoritative readback required" not in summary
