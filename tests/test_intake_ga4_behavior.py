"""Behavioral tests owned by intake ga4."""

from support import authenticated_delivery as fixture_authenticated_delivery
from support import input_and_execution as fixture_input_and_execution
from support import input_integrity as fixture_input_integrity
from support import native_execution as fixture_native_execution
from support import phase_contracts as fixture_phase_contracts
from support import transport_and_state as fixture_transport_and_state
from support import web_authority as fixture_web_authority


class TestInputAndExecution(fixture_input_and_execution.AuditRegressionsFixture):
    def test_intake_still_rejects_old_versions_and_duplicate_singletons(self):
        fixture = fixture_input_and_execution.ROOT / "tests/fixtures/tracking-plan-delivery"
        with fixture_input_and_execution.tempfile.TemporaryDirectory() as temp:
            delivery = fixture_input_and_execution.Path(temp) / "delivery"
            fixture_input_and_execution.shutil.copytree(fixture, delivery)
            handoff_path = delivery / "handoff.json"
            handoff = fixture_input_and_execution.json.loads(
                handoff_path.read_text(encoding="utf-8")
            )
            handoff["handoff_version"] = "1.1.0"
            handoff_path.write_text(
                fixture_input_and_execution.json.dumps(handoff), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                fixture_input_and_execution.verify_delivery(delivery)
            handoff["handoff_version"] = "2.0.0"
            singleton = next(
                item for item in handoff["artifacts"] if item["role"] == "canonical_tracking_plan"
            )
            handoff["artifacts"].append(fixture_input_and_execution.deepcopy(singleton))
            handoff_path.write_text(
                fixture_input_and_execution.json.dumps(handoff), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "Duplicate handoff artifact role"):
                fixture_input_and_execution.verify_delivery(delivery)

    def test_verified_delivery_preserves_configuration_identity(self):
        fixture = fixture_input_and_execution.ROOT / "tests/fixtures/tracking-plan-delivery"
        handoff, plan = fixture_input_and_execution.verify_delivery(fixture)
        before = fixture_input_and_execution.deepcopy(plan)
        imported = fixture_input_and_execution.normalized_approved_semantics(handoff, plan)
        self.assertTrue(
            any(
                "user_id" in item.get("configuration_fields", {})
                for item in imported["requirements"]
            )
        )
        self.assertEqual(plan, before)
        self.assertEqual(handoff["skill"]["name"], "ga4-tracking-plan")


class TestNativeExecution(fixture_native_execution.NativeBindingTestsFixture):
    def test_scope_requires_complete_metadata_or_exact_path_and_rejects_conflicts(self):
        req = fixture_native_execution.request()
        adapter = fixture_native_execution.McpTargetAdapter(
            req["targets"][0], fixture_native_execution.PROFILE, lambda *a: {}
        )
        scope = {
            "accountId": "account-1",
            "containerId": "GTM-WEBTEST",
            "workspaceId": "workspace-web",
        }
        path = "accounts/account-1/containers/GTM-WEBTEST/workspaces/workspace-web/tags/42"
        for raw in (scope, {"path": path}, {**scope, "path": path}):
            adapter._check_scope(raw)
        for raw in (
            {},
            {"accountId": "account-1"},
            {**scope, "workspaceId": "wrong"},
            {**scope, "path": path.replace("/42", "/42/extra")},
            {**scope, "path": path.replace("workspace-web", "wrong")},
            {"path": path, "accountId": "wrong"},
        ):
            with self.assertRaises(fixture_native_execution.AdapterExecutionError):
                adapter._check_scope(raw)


class TestAuthenticatedDelivery(fixture_authenticated_delivery.Audit102FollowupFixture):
    def test_delivery_bytes_and_unresolved_destination_are_preserved(self):
        fixture = fixture_authenticated_delivery.ROOT / "tests/fixtures/tracking-plan-delivery"
        handoff, plan = fixture_authenticated_delivery.verify_delivery(fixture)
        before = fixture_authenticated_delivery.deepcopy(plan)
        imported = fixture_authenticated_delivery.normalized_approved_semantics(handoff, plan)
        self.assertTrue(
            any(
                "user_id" in item.get("configuration_fields", {})
                for item in imported["requirements"]
            )
        )
        self.assertEqual(plan, before)
        self.assertEqual(handoff["skill"]["name"], "ga4-tracking-plan")
        provenance = fixture_authenticated_delivery.json.loads(
            (
                fixture_authenticated_delivery.ROOT
                / "tests/fixtures/tracking-plan-delivery-provenance.json"
            ).read_text(encoding="utf-8-sig")
        )
        self.assertEqual(
            fixture_authenticated_delivery.hashlib.sha256(
                (fixture / "handoff.json").read_bytes()
            ).hexdigest(),
            provenance["handoff_sha256"],
        )


class TestPhaseContracts(fixture_phase_contracts.CurrentContractAndRunTestFixture):
    def test_dual_delivery_requires_one_approved_stable_occurrence_id(self) -> None:
        contract = fixture_phase_contracts.add_nonpurchase_dual_dedup(
            fixture_phase_contracts.valid_pipeline_contract()
        )
        self.assertEqual(
            fixture_phase_contracts.validate_contract(contract)["dedup_contracts"][0]["event_name"],
            "add_to_cart",
        )
        fixture_phase_contracts.create_from_contract(
            contract,
            run_id="RUN-DEDUP",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )

        internal_fallback = fixture_phase_contracts.deepcopy(contract)
        internal_fallback["dedup_contracts"][0]["source_type"] = "gtm-event-scoped-fallback"
        with self.assertRaisesRegex(
            fixture_phase_contracts.ContractValidationError, "source_type.*is not one of"
        ):
            fixture_phase_contracts.validate_contract(internal_fallback)

        separate = fixture_phase_contracts.deepcopy(contract)
        separate["dedup_contracts"][0]["browser_reference"] = "{{DLV - Another ID}}"
        with self.assertRaisesRegex(
            fixture_phase_contracts.ContractValidationError, "one occurrence source"
        ):
            fixture_phase_contracts.validate_contract(separate)


class TestInputIntegrity(fixture_input_integrity.RuntimeHardeningTestFixture):
    def test_tracking_plan_importer_validates_current_records_with_additional_metadata(
        self,
    ) -> None:
        plan = fixture_input_integrity.valid_plan()
        handoff = {
            "skill": {"version": "3.0.0"},
            "plan": {"canonical_sha256": "a" * 64},
            "approval": {"state": "approved"},
        }
        normalized = fixture_input_integrity.normalized_approved_semantics(handoff, plan)
        requirement = normalized["requirements"][0]
        self.assertEqual(requirement["event_name"], "generate_lead")
        self.assertEqual(
            requirement["parameters"]["method"]["source"],
            "event_data.method",
        )

        malformed = fixture_input_integrity.deepcopy(plan)
        malformed["events"][0]["parameters"] = ["not-an-object"]
        with self.assertRaisesRegex(
            fixture_input_integrity.HandoffError, r"parameters\[0\] must be an object"
        ):
            fixture_input_integrity.normalized_approved_semantics(handoff, malformed)

    def test_delivery_inventory_rejects_duplicate_roles_and_wrong_byte_counts(self) -> None:
        with fixture_input_integrity.tempfile.TemporaryDirectory() as temporary:
            root = fixture_input_integrity.Path(temporary)
            plan_path = root / "plan.json"
            plan_path.write_text(
                fixture_input_integrity.json.dumps(fixture_input_integrity.valid_plan()),
                encoding="utf-8",
            )
            digest = fixture_input_integrity.hashlib.sha256(plan_path.read_bytes()).hexdigest()
            artifact = {
                "path": "plan.json",
                "role": "canonical_tracking_plan",
                "bytes": plan_path.stat().st_size,
                "sha256": digest,
            }
            handoff = {
                "handoff_version": "2.0.0",
                "skill": {"name": "ga4-tracking-plan", "version": "3.0.0"},
                "approval": {"state": "approved"},
                "plan": {"canonical_sha256": digest, "schema_version": "6.0.0"},
                "artifacts": [artifact],
            }
            handoff_path = root / "handoff.json"
            handoff_path.write_text(fixture_input_integrity.json.dumps(handoff), encoding="utf-8")
            _, imported = fixture_input_integrity.verify_delivery(root)
            self.assertEqual(imported["events"][0]["event_name"], "generate_lead")

            handoff["artifacts"] = [artifact, {**artifact, "path": "plan.json"}]
            handoff_path.write_text(fixture_input_integrity.json.dumps(handoff), encoding="utf-8")
            with self.assertRaisesRegex(
                fixture_input_integrity.HandoffError, "Duplicate handoff artifact role"
            ):
                fixture_input_integrity.verify_delivery(root)

            handoff["artifacts"] = [{**artifact, "bytes": artifact["bytes"] + 1}]
            handoff_path.write_text(fixture_input_integrity.json.dumps(handoff), encoding="utf-8")
            with self.assertRaisesRegex(
                fixture_input_integrity.HandoffError, "byte-count mismatch"
            ):
                fixture_input_integrity.verify_delivery(root)


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_current_handoff_accepts_multiple_event_schemas_not_legacy_version(self):
        with fixture_transport_and_state.tempfile.TemporaryDirectory() as temporary:
            root = fixture_transport_and_state.Path(temporary)
            artifacts = []
            for name, role in [
                ("plan.json", "canonical_tracking_plan"),
                ("lead.json", "event_push_schema"),
                ("purchase.json", "event_push_schema"),
            ]:
                path = root / name
                path.write_text(
                    fixture_transport_and_state.json.dumps(
                        {"schema_version": "6.0.0"} if name == "plan.json" else {}
                    ),
                    encoding="utf-8",
                )
                artifacts.append(
                    {
                        "path": name,
                        "role": role,
                        "bytes": path.stat().st_size,
                        "sha256": fixture_transport_and_state.hashlib.sha256(
                            path.read_bytes()
                        ).hexdigest(),
                    }
                )
            handoff = {
                "handoff_version": "2.0.0",
                "skill": {"name": "ga4-tracking-plan"},
                "approval": {"state": "approved"},
                "artifacts": artifacts,
                "plan": {"canonical_sha256": artifacts[0]["sha256"], "schema_version": "6.0.0"},
            }
            (root / "handoff.json").write_text(
                fixture_transport_and_state.json.dumps(handoff), encoding="utf-8"
            )
            self.assertEqual(
                fixture_transport_and_state.verify_delivery(root)[1], {"schema_version": "6.0.0"}
            )
            handoff["handoff_version"] = "1.1.0"
            (root / "handoff.json").write_text(
                fixture_transport_and_state.json.dumps(handoff), encoding="utf-8"
            )
            with self.assertRaises(fixture_transport_and_state.HandoffError):
                fixture_transport_and_state.verify_delivery(root)


class TestWebAuthority(fixture_web_authority.EffectiveConfigurationGuardrailsTestFixture):
    def test_official_guidance_decision_is_required_and_survives_handoff(self):
        contract = fixture_web_authority.valid_web_contract()
        source = next(item for item in contract["evidence"] if item["grade"] == "official-current")
        source["locator"] = "https://developers.google.com/analytics/devguides/collection/ga4/views"
        source["title"] = "Measure pageviews"
        source["decision"] = (
            "Google configuration sends the initial page_view; do not add a second initial owner."
        )
        run = fixture_web_authority.create_from_contract(
            contract, run_id="GUIDANCE", source_locator="approved"
        )
        self.assertEqual(run["official_sources"][0]["decision"], source["decision"])
        self.assertIn(source["decision"], fixture_web_authority.render_markdown(run))
        self.assertIn(source["locator"], fixture_web_authority.render_markdown(run))
        source.pop("decision")
        with self.assertRaisesRegex(fixture_web_authority.ContractValidationError, "decision"):
            fixture_web_authority.validate_document(contract)
