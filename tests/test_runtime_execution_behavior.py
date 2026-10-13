"""Behavioral tests owned by runtime execution."""

from support import adapters as fixture_adapters
from support import authenticated_delivery as fixture_authenticated_delivery
from support import durable_evidence as fixture_durable_evidence
from support import field_binding as fixture_field_binding
from support import input_and_execution as fixture_input_and_execution
from support import mutation_recovery as fixture_mutation_recovery
from support import native_boundaries as fixture_native_boundaries
from support import native_execution as fixture_native_execution
from support import phase_contracts as fixture_phase_contracts
from support import transport_and_state as fixture_transport_and_state
from support import web_authority as fixture_web_authority


class TestAdapters(fixture_adapters.CurrentAdapterRuntimeTestFixture):
    def test_exhausted_rate_limit_keeps_its_specific_classification(self) -> None:
        class AlwaysLimitedAdapter(fixture_adapters.FakeAdapter):
            def mutate(self, operation):
                raise fixture_adapters.RateLimitError(
                    "documented rate limit", retry_after_seconds=0
                )

        run = fixture_adapters.create_from_contract(
            fixture_adapters.valid_web_contract(),
            run_id="RUN-RATE-CLASS",
            source_locator="approved",
        )
        target = run["run"]["targets"][0]
        adapter = AlwaysLimitedAdapter()
        adapter.bind_target(target)
        registry = fixture_adapters.TargetAdapterRegistry()
        registry.register(target, adapter, fixture_adapters.capabilities("tag", "trigger"))
        with fixture_adapters.tempfile.TemporaryDirectory() as temporary:
            path = fixture_adapters.Path(temporary) / "run.json"
            fixture_adapters.atomic_write(path, run)
            fixture_adapters.execute_ready_operations(
                path,
                registry,
                max_rate_limit_retries=0,
                sleep=lambda _: None,
            )
            persisted = path.read_text(encoding="utf-8")
        self.assertIn("documented rate limit", persisted)
        self.assertNotIn("unexpected_adapter_failure", persisted)

    def test_unexpected_adapter_error_is_scrubbed_and_checkpointed(self) -> None:
        class ExplodingAdapter(fixture_adapters.FakeAdapter):
            def read(self, operation):
                raise RuntimeError("X-API-Key: TOPSECRET123")

        run = fixture_adapters.with_complete_baselines(
            fixture_adapters.create_from_contract(
                fixture_adapters.valid_web_contract(),
                run_id="RUN-ADAPTER-ERROR",
                source_locator="approved",
            )
        )
        target = run["run"]["targets"][0]
        adapter = ExplodingAdapter()
        adapter.bind_target(target)
        registry = fixture_adapters.TargetAdapterRegistry()
        registry.register(target, adapter, fixture_adapters.capabilities("tag", "trigger"))
        with fixture_adapters.tempfile.TemporaryDirectory() as temporary:
            path = fixture_adapters.Path(temporary) / "run.json"
            fixture_adapters.atomic_write(path, run)
            fixture_adapters.execute_ready_operations(path, registry, sleep=lambda _: None)
            persisted = path.read_text(encoding="utf-8")
        self.assertNotIn("TOPSECRET123", persisted)
        self.assertIn("unexpected_adapter_failure", persisted)

    def test_adapter_identity_is_rechecked_before_execution(self) -> None:
        run = fixture_adapters.with_complete_baselines(
            fixture_adapters.create_from_contract(
                fixture_adapters.valid_web_contract(),
                run_id="RUN-WRONG-TARGET",
                source_locator="approved input",
            )
        )
        target = run["run"]["targets"][0]
        adapter = fixture_adapters.FakeAdapter()
        adapter.bind_target(target)
        registry = fixture_adapters.TargetAdapterRegistry()
        registry.register(target, adapter, fixture_adapters.capabilities("tag", "trigger"))
        adapter.observed_identity["workspace_id"] = "different-workspace"
        with fixture_adapters.tempfile.TemporaryDirectory() as temporary:
            path = fixture_adapters.Path(temporary) / "run.json"
            fixture_adapters.atomic_write(path, run)
            fixture_adapters.execute_ready_operations(path, registry, sleep=lambda _: None)
            result = fixture_adapters.load_document(path)
        self.assertEqual(adapter.mutations, [])
        errors = [
            item.get("baseline_error", {}).get("error", "") for item in result["target_results"]
        ]
        self.assertTrue(any("authenticated adapter identity differs" in value for value in errors))

    def test_documented_nonapplied_rate_limit_retries_within_bound(self) -> None:
        contract = fixture_adapters.valid_web_contract()
        adapter = fixture_adapters.FakeAdapter(rate_limit_once={"Google tag - Web transport"})
        delays: list[float] = []
        run, _ = self._execute(
            contract,
            {"web-main": (adapter, fixture_adapters.capabilities("tag", "trigger"), None)},
            max_rate_limit_retries=1,
            sleep=delays.append,
        )
        self.assertEqual(run["object_changes"][0]["state"], "verified")
        self.assertEqual(adapter.attempts["Google tag - Web transport"], 2)
        self.assertEqual(delays, [0])

    def test_execution_captures_and_retains_authenticated_baseline(self) -> None:
        class BaselineAdapter(fixture_adapters.FakeAdapter):
            def list_resource_page(self, resource_family, cursor):
                if resource_family == "tag":
                    return {
                        "items": [{"name": "Existing safe tag", "type": "html"}],
                        "next_cursor": None,
                    }
                return {"items": [], "next_cursor": None}

        run = fixture_adapters.create_from_contract(
            fixture_adapters.valid_web_contract(),
            run_id="RUN-AUTH-BASELINE",
            source_locator="approved",
        )
        target = run["run"]["targets"][0]
        adapter = BaselineAdapter()
        adapter.bind_target(target)
        registry = fixture_adapters.TargetAdapterRegistry()
        registry.register(target, adapter, fixture_adapters.capabilities("tag", "trigger"))
        with fixture_adapters.tempfile.TemporaryDirectory() as temporary:
            path = fixture_adapters.Path(temporary) / "run.json"
            fixture_adapters.atomic_write(path, run)
            fixture_adapters.execute_ready_operations(path, registry, sleep=lambda _: None)
            result = fixture_adapters.load_document(path)
        baseline = result["container_baselines"][0]
        self.assertEqual(
            baseline["capture_evidence"]["captured_by"], "authenticated-adapter-runtime"
        )
        self.assertEqual(baseline["resources"]["tag"][0]["name"], "Existing safe tag")

    def test_failed_client_stops_dependents_but_not_an_independent_web_object(self) -> None:
        contract = fixture_adapters.valid_pipeline_contract(cutover=True)
        web_only = fixture_adapters.valid_web_contract()
        block_key = "web-main::trigger::CMP - Analytics denied"
        block_trigger = next(
            fixture_adapters.deepcopy(item)
            for item in web_only["implementation"]["objects"]
            if item["object_key"] == block_key
        )
        contract["implementation"]["objects"].append(block_trigger)
        direct_topology = fixture_adapters.deepcopy(web_only["consent_topologies"][0])
        direct_topology["consent_topology_id"] = "CONSENT-DIAGNOSTICS"
        direct_topology["destination"] = "Diagnostics"
        contract["consent_topologies"].append(direct_topology)
        client = contract["implementation"]["objects"][1]
        client.update(
            {
                "action": "create",
                "intended": {
                    "type": "ga4-client",
                    "priority": 10,
                },
                "evidence": ["approved-input", "official-current"],
                "risk": "high-impact",
            }
        )
        contract["implementation"]["objects"].append(
            {
                "target_id": "web-main",
                "resource_family": "tag",
                "name": "Independent - Diagnostics",
                "object_key": "web-main::tag::Independent - Diagnostics",
                "action": "create",
                "requirement_ids": ["REQ-PAGE"],
                "depends_on": [
                    "web-main::trigger::CMP - Analytics granted",
                    block_key,
                ],
                "justification": "Independent approved web destination",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {
                    "type": "html",
                    "event_name": "diagnostic",
                    "firingTriggerId": ["web-main::trigger::CMP - Analytics granted"],
                    "blockingTriggerId": [block_key],
                    "tagFiringOption": "oncePerEvent",
                },
            }
        )
        contract["execution_topologies"].append(
            {
                "tag_object_key": "web-main::tag::Independent - Diagnostics",
                "requirement_ids": ["REQ-PAGE"],
                "lifecycle_role": "event-driven",
                "normal_triggers": [
                    {
                        "trigger_object_key": "web-main::trigger::CMP - Analytics granted",
                        "role": "source-event",
                        "type": "custom-event",
                    }
                ],
                "consent_mode": "strict-basic",
                "consent_topology_ids": ["CONSENT-DIAGNOSTICS"],
                "blocking_trigger_keys": [block_key],
                "blocking_event_scope": ".*",
                "built_in_consent_checks": ["analytics_storage"],
                "additional_consent_checks": [],
                "firing_option": "once-per-event",
                "may_precede_cmp": False,
                "pre_cmp_policy": "not-applicable",
                "page_view_capable": False,
                "page_view_destinations": [],
                "page_view_occurrences": [],
                "ecommerce_route": "not-applicable",
                "manual_ecommerce_fields": [],
                "evidence": ["official-current", "container-confirmed"],
            }
        )
        server = fixture_adapters.FakeAdapter(fail_names={"GA4 Client - Web transport"})
        web = fixture_adapters.FakeAdapter()
        run, _ = self._execute(
            contract,
            {
                "web-main": (web, fixture_adapters.capabilities("tag", "trigger"), None),
                "server-main": (
                    server,
                    fixture_adapters.capabilities("client", "tag", "trigger"),
                    None,
                ),
            },
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(states["GA4 Client - Web transport"], "failed")
        self.assertEqual(states["GA4 - page_view"], "planned")
        self.assertEqual(states["Google tag - Web transport"], "planned")
        self.assertEqual(states["Independent - Diagnostics"], "verified")
        self.assertIn("Independent - Diagnostics", web.mutations)

    def test_one_failed_destination_does_not_block_an_independent_destination(self) -> None:
        contract = fixture_adapters.valid_pipeline_contract()
        meta_key = "server-main::tag::Meta - PageView"
        server_trigger_key = "server-main::trigger::Event Data - page_view"
        web_transport_key = "web-main::tag::Google tag - Web transport"
        contract["implementation"]["objects"].append(
            {
                "target_id": "server-main",
                "resource_family": "tag",
                "name": "Meta - PageView",
                "object_key": meta_key,
                "action": "create",
                "requirement_ids": ["REQ-PAGE"],
                "depends_on": [
                    "server-main::client::GA4 Client - Web transport",
                    server_trigger_key,
                ],
                "justification": "Approved independent server destination",
                "evidence": ["approved-input", "official-current"],
                "risk": "routine",
                "intended": {
                    "type": "meta-capi",
                    "event_name": "PageView",
                    "firingTriggerId": [server_trigger_key],
                    "blockingTriggerId": [],
                },
            }
        )
        contract["consent_topologies"].append(
            {
                "consent_topology_id": "CONSENT-META",
                "destination": "Meta",
                "requirement_ids": ["REQ-PAGE"],
                "consent_mode": "product-specific",
                "transport_behavior": "always-transported",
                "web_enforcement": {"mechanism": "transport-trigger-only"},
                "server_enforcement": {
                    "mechanism": "server-template-native-consent",
                    "template_support": "Installed Meta template consent field",
                },
                "signal_authority": "product-native",
                "signal_source": "Installed Meta server template consent input",
                "unknown_state_behavior": "explicit-policy",
                "event_coverage": ["page_view"],
                "intentional_double_gate": False,
                "server_tag_keys": [meta_key],
                "transporter_tag_keys": [web_transport_key],
                "transporter_destination_vendor_block": False,
            }
        )
        contract["pipelines"][0]["consent_topology_ids"].append("CONSENT-META")
        contract["pipelines"][0]["event_flows"][0]["server_consumer_keys"].append(meta_key)
        contract["pipelines"][0]["operation_dependencies"].append(meta_key)
        next(
            item
            for item in contract["implementation"]["objects"]
            if item["object_key"] == contract["pipelines"][0]["cutover_operation_key"]
        )["depends_on"].append(meta_key)
        server = fixture_adapters.FakeAdapter(
            existing={"GA4 Client - Web transport"}, fail_names={"Meta - PageView"}
        )
        web = fixture_adapters.FakeAdapter()
        run, _ = self._execute(
            contract,
            {
                "web-main": (web, fixture_adapters.capabilities("tag", "trigger"), None),
                "server-main": (
                    server,
                    fixture_adapters.capabilities("client", "tag", "trigger"),
                    None,
                ),
            },
        )
        states = {item["name"]: item["state"] for item in run["object_changes"]}
        self.assertEqual(states["GA4 - page_view"], "verified")
        self.assertEqual(states["Meta - PageView"], "failed")
        self.assertEqual(states["Google tag - Web transport"], "planned")

    def test_replace_requires_both_remove_and_create_capabilities(self) -> None:
        contract = fixture_adapters.valid_web_contract()
        operation = contract["implementation"]["objects"][0]
        operation.update(
            {
                "action": "replace",
                "object_id": "tag-100",
                "pre_change": fixture_adapters.deepcopy(operation["intended"]),
                "replacement_reason": "Replace the incompatible saved Google tag",
                "evidence": [
                    "approved-input",
                    "official-current",
                    "container-confirmed",
                ],
                "risk": "high-impact",
            }
        )
        matrix = fixture_adapters.capabilities("tag", "trigger")
        matrix["tag"]["create"] = False
        adapter = fixture_adapters.FakeAdapter(existing={"Google tag - Web transport"})
        run, _ = self._execute(
            contract,
            {"web-main": (adapter, matrix, None)},
        )
        saved = run["object_changes"][0]
        self.assertEqual(saved["state"], "failed")
        self.assertIn("governed replace", saved["journal"][-1]["error"])
        self.assertNotIn("Google tag - Web transport", adapter.mutations)


class TestNativeExecutionRecoveryCorrections(
    fixture_native_execution.RecoveryCorrectionsTestsFixture
):
    def test_quota_retry_rechecks_native_delta_with_and_without_fingerprint(self):
        for fingerprint in (True, False):
            for drift in (True, False):
                with (
                    self.subTest(fingerprint=fingerprint, drift=drift),
                    fixture_native_execution.tempfile.TemporaryDirectory() as directory,
                ):
                    req = fixture_native_execution.request()
                    backend = fixture_native_execution.FakeGtm(req)
                    contract = fixture_native_execution.compile_request(req)
                    path = fixture_native_execution.Path(directory) / "create.json"
                    fixture_native_execution.atomic_write(
                        path,
                        fixture_native_execution.create_from_contract(
                            contract, run_id="create", source_locator="synthetic"
                        ),
                    )
                    registry, _ = fixture_native_execution.bind(contract, backend)
                    fixture_native_execution.execute_ready_operations(path, registry)
                    saved = fixture_native_execution.deepcopy(
                        next(
                            v
                            for v in backend.data["tag"].values()
                            if v["name"] == req["objects"][0]["name"]
                        )
                    )
                    if not fingerprint:
                        saved.pop("fingerprint")
                        backend.data["tag"][saved["tagId"]].pop("fingerprint")
                    update = fixture_native_execution.request()
                    row = update["objects"][0]
                    row.update(
                        action="update",
                        object_id=saved["tagId"],
                        pre_change=fixture_native_execution.deepcopy(saved),
                    )
                    row["intended"]["notes"] = "approved new note"
                    contract = fixture_native_execution.compile_request(update)
                    path = fixture_native_execution.Path(directory) / "update.json"
                    fixture_native_execution.atomic_write(
                        path,
                        fixture_native_execution.create_from_contract(
                            contract, run_id="update", source_locator="synthetic"
                        ),
                    )
                    original_call = backend.call
                    attempts = []

                    def limited(tool, args):
                        if args["action"] == "update":
                            attempts.append(fixture_native_execution.deepcopy(args))
                            if len(attempts) == 1:
                                raise fixture_native_execution.RateLimitError(
                                    "rejected quota", retry_after_seconds=0
                                )
                        return original_call(tool, args)

                    backend.call = limited
                    registry, _ = fixture_native_execution.bind(contract, backend)

                    def backoff(_):
                        if drift:
                            backend.data["tag"][saved["tagId"]]["notes"] = "concurrent edit"

                    fixture_native_execution.execute_ready_operations(path, registry, sleep=backoff)
                    operation = next(
                        o
                        for o in fixture_native_execution.load_document(path)["object_changes"]
                        if o["resource_family"] == "tag"
                    )
                    self.assertEqual(len(attempts), 1 if drift else 2)
                    self.assertEqual(operation["state"] == "verified", not drift)
                    if fingerprint and not drift:
                        self.assertEqual(attempts[1]["fingerprint"], saved["fingerprint"])


class TestFieldBinding(fixture_field_binding.StartupTestFixture):
    def test_invalid_later_profile_prevents_all_authenticated_calls(self):
        _, adapters, identities = self.run_startup(invalid_profile=True)
        self.assertEqual(identities, [])
        self.assertTrue(all(not adapter.mutations for adapter in adapters.values()))

    def test_all_available_targets_converge(self):
        run, _, _ = self.run_startup()
        self.assertTrue(all(o["state"] == "verified" for o in run["object_changes"]))
        self.assertTrue(run["idempotency"]["checked"])


class TestWebAuthority(fixture_web_authority.EffectiveConfigurationGuardrailsTestFixture):
    def test_missing_tag_inventory_prevents_variable_only_mutation(self):
        run = fixture_web_authority.create_from_contract(
            fixture_web_authority.settings_contract(), run_id="SETTINGS", source_locator="approved"
        )
        target = run["run"]["targets"][0]
        adapter = fixture_web_authority.FakeAdapter(existing={"Google Settings"})
        adapter.bind_target(target)
        registry = fixture_web_authority.TargetAdapterRegistry()
        registry.register(target, adapter, fixture_web_authority.capabilities("variable"))
        with fixture_web_authority.tempfile.TemporaryDirectory() as temporary:
            path = fixture_web_authority.Path(temporary) / "run.json"
            fixture_web_authority.atomic_write(path, run)
            fixture_web_authority.execute_ready_operations(path, registry)
            result = fixture_web_authority.load_document(path)
        self.assertEqual(adapter.mutations, [])
        self.assertEqual(result["object_changes"][0]["state"], "planned")
        self.assertIn(
            "required resource families", result["target_results"][0]["baseline_error"]["error"]
        )

    def test_new_shared_settings_consumer_after_baseline_prevents_the_write(self):
        class NewConsumerAdapter(fixture_web_authority.FakeAdapter):
            tag_lists = 0

            def list_resource_page(self, resource_family, cursor):
                if resource_family != "tag":
                    return super().list_resource_page(resource_family, cursor)
                self.tag_lists += 1
                items = (
                    []
                    if self.tag_lists == 1
                    else [
                        {
                            "name": "New unrelated tag",
                            "type": "googtag",
                            "configSettingsVariable": "{{Google Settings}}",
                        }
                    ]
                )
                return {"items": items, "next_cursor": None}

        run = fixture_web_authority.create_from_contract(
            fixture_web_authority.settings_contract(),
            run_id="NEW-CONSUMER",
            source_locator="approved",
        )
        target = run["run"]["targets"][0]
        adapter = NewConsumerAdapter(existing={"Google Settings"})
        adapter.bind_target(target)
        registry = fixture_web_authority.TargetAdapterRegistry()
        registry.register(target, adapter, fixture_web_authority.capabilities("tag", "variable"))
        with fixture_web_authority.tempfile.TemporaryDirectory() as temporary:
            path = fixture_web_authority.Path(temporary) / "run.json"
            fixture_web_authority.atomic_write(path, run)
            fixture_web_authority.execute_ready_operations(path, registry)
            result = fixture_web_authority.load_document(path)
        self.assertEqual(adapter.mutations, [])
        self.assertEqual(adapter.tag_lists, 2)
        self.assertEqual(result["object_changes"][0]["state"], "failed")
        self.assertIn("unreviewed current consumers", str(result["object_changes"][0]["journal"]))

    def test_initial_execution_replaces_fabricated_baseline_with_actual_consumers(self):
        class ConsumerAdapter(fixture_web_authority.FakeAdapter):
            def list_resource_page(self, resource_family, cursor):
                items = (
                    [
                        {
                            "name": "Unreviewed tag",
                            "type": "googtag",
                            "configSettingsVariable": "{{Google Settings}}",
                        }
                    ]
                    if resource_family == "tag"
                    else []
                )
                return {"items": items, "next_cursor": None}

        contract = fixture_web_authority.valid_web_contract()
        contract["implementation"]["objects"].append(
            fixture_web_authority.settings_contract()["implementation"]["objects"][0]
        )
        fixture_web_authority.approve_mutations(contract)
        run = fixture_web_authority.with_complete_baselines(
            fixture_web_authority.create_from_contract(
                contract, run_id="BASELINE", source_locator="approved"
            )
        )
        target = run["run"]["targets"][0]
        adapter = ConsumerAdapter(existing={"Google Settings"})
        adapter.bind_target(target)
        registry = fixture_web_authority.TargetAdapterRegistry()
        registry.register(
            target, adapter, fixture_web_authority.capabilities("tag", "trigger", "variable")
        )
        with fixture_web_authority.tempfile.TemporaryDirectory() as temporary:
            path = fixture_web_authority.Path(temporary) / "run.json"
            fixture_web_authority.atomic_write(path, run)
            fixture_web_authority.execute_ready_operations(path, registry)
            result = fixture_web_authority.load_document(path)
        self.assertEqual(adapter.mutations, [])
        self.assertTrue(all(item["state"] == "planned" for item in result["object_changes"]))
        self.assertIn(
            "every authenticated baseline consumer",
            str(result["target_results"][0]["baseline_error"]),
        )

    def test_readback_failure_after_a_successful_write_remains_uncertain(self):
        for failure in (
            fixture_web_authority.RateLimitError("rate limit", retry_after_seconds=0),
            fixture_web_authority.AdapterExecutionError("read failed"),
        ):

            class ReadbackFailure(fixture_web_authority.FakeAdapter):
                def mutate(self, operation):
                    super().mutate(operation)
                    return None  # Partial response still requires readback.

                def read(self, operation):
                    if operation["name"] in self.saved:
                        raise failure
                    return super().read(operation)

            run = fixture_web_authority.create_from_contract(
                fixture_web_authority.valid_web_contract(),
                run_id="READBACK",
                source_locator="approved",
            )
            target = run["run"]["targets"][0]
            adapter = ReadbackFailure()
            adapter.bind_target(target)
            registry = fixture_web_authority.TargetAdapterRegistry()
            registry.register(target, adapter, fixture_web_authority.capabilities("tag", "trigger"))
            with fixture_web_authority.tempfile.TemporaryDirectory() as temporary:
                path = fixture_web_authority.Path(temporary) / "run.json"
                fixture_web_authority.atomic_write(path, fixture_web_authority.deepcopy(run))
                fixture_web_authority.execute_ready_operations(
                    path, registry, max_rate_limit_retries=0
                )
                result = fixture_web_authority.load_document(path)
            wrote = [item for item in result["object_changes"] if item["name"] in adapter.mutations]
            self.assertTrue(wrote)
            self.assertTrue(all(item["state"] == "uncertain" for item in wrote))
            self.assertTrue(all(value == 1 for value in adapter.attempts.values()))


class TestAuthenticatedDelivery(fixture_authenticated_delivery.Audit102FollowupFixture):
    def test_identity_and_absence_checks_survive_call_reduction(self):
        for mode in (
            "normal",
            "initial-identity-mismatch",
            "wrong-native-scope",
            "create-collision",
            "reuse-drift",
        ):
            with (
                self.subTest(mode=mode),
                fixture_authenticated_delivery.tempfile.TemporaryDirectory() as directory,
            ):
                backend = fixture_authenticated_delivery.FakeGtm(
                    fixture_authenticated_delivery.request()
                )
                calls = fixture_authenticated_delivery.Counter()

                def call(tool, arguments):
                    key = (tool.removeprefix("synthetic__"), arguments["action"])
                    calls[key] += 1
                    self.assertEqual(arguments["accountId"], "account-1")
                    self.assertEqual(arguments["containerId"], "GTM-WEBTEST")
                    if key[0] != "gtm_container":
                        self.assertEqual(arguments["workspaceId"], "workspace-web")
                    result = backend.call(tool, arguments)
                    if mode == "initial-identity-mismatch" and key == ("gtm_workspace", "get"):
                        result["workspaceId"] = "unauthorized-workspace"
                    if mode == "wrong-native-scope" and key == ("gtm_trigger", "get"):
                        result["workspaceId"] = "unauthorized-workspace"
                    if (
                        mode == "create-collision"
                        and key == ("gtm_tag", "list")
                        and calls[key] == 2
                    ):
                        result["tag"].append(
                            {
                                **backend.scope,
                                "tagId": "777",
                                "name": "GA4 - generate_lead",
                                "type": "html",
                                "parameter": [],
                            }
                        )
                    if mode == "reuse-drift" and key == ("gtm_trigger", "get"):
                        result["type"] = "timer"
                    return result

                path = fixture_authenticated_delivery.Path(directory) / "run.json"
                document = fixture_authenticated_delivery.run_document()
                fixture_authenticated_delivery.atomic_write(path, document)
                target = document["run"]["targets"][0]
                adapter = fixture_authenticated_delivery.McpTargetAdapter(
                    target,
                    fixture_authenticated_delivery.deepcopy(fixture_authenticated_delivery.PROFILE),
                    call,
                )
                registry = fixture_authenticated_delivery.TargetAdapterRegistry()
                if mode == "initial-identity-mismatch":
                    with self.assertRaises(fixture_authenticated_delivery.AdapterExecutionError):
                        registry.register(target, adapter, adapter.capabilities())
                    self.assertEqual(backend.writes, [])
                    continue
                registry.register(target, adapter, adapter.capabilities())
                fixture_authenticated_delivery.execute_ready_operations(path, registry)
                if mode == "normal":
                    fixture_authenticated_delivery.verify_idempotent_rerun(path, registry)
                    self.assertEqual(
                        fixture_authenticated_delivery.load_document(path)["run"]["status"],
                        "Configured",
                    )
                    self.assertEqual(len(backend.writes), 1)
                    self.assertEqual(calls["gtm_workspace", "get"], 1)
                    self.assertEqual(calls["gtm_container", "get"], 1)
                    self.assertEqual(calls["gtm_tag", "list"], 3)
                    # The fixture page size is two: a full page requires an empty terminal page.
                    self.assertEqual(calls["gtm_trigger", "list"], 4)
                elif mode == "create-collision":
                    self.assertEqual(len(backend.writes), 1)
                    with self.assertRaisesRegex(
                        fixture_authenticated_delivery.AdapterExecutionError,
                        "exhaustion is unproved",
                    ):
                        fixture_authenticated_delivery.verify_idempotent_rerun(path, registry)
                    self.assertNotEqual(
                        fixture_authenticated_delivery.load_document(path)["run"]["status"],
                        "Configured",
                    )
                else:
                    self.assertEqual(backend.writes, [])
                    self.assertNotEqual(
                        fixture_authenticated_delivery.load_document(path)["run"]["status"],
                        "Configured",
                    )


class TestInputAndExecution(fixture_input_and_execution.AuditRegressionsFixture):
    def test_isolated_runtime_does_not_list_unrelated_capabilities(self):
        class Source(fixture_input_and_execution.FakeAdapter):
            def list_resource_page(self, family, cursor):
                if family == "variable":
                    raise AssertionError("Unrelated variable inventory requested")
                return super().list_resource_page(family, cursor)

        adapter = Source()
        run = fixture_input_and_execution.create_from_contract(
            fixture_input_and_execution.valid_web_contract(),
            run_id="scoped-baseline",
            source_locator="Synthetic request",
        )
        target = run["run"]["targets"][0]
        adapter.bind_target(target)
        registry = fixture_input_and_execution.TargetAdapterRegistry()
        registry.register(
            target, adapter, fixture_input_and_execution.capabilities("tag", "trigger", "variable")
        )
        with fixture_input_and_execution.tempfile.TemporaryDirectory() as temp:
            path = fixture_input_and_execution.Path(temp) / "run.json"
            fixture_input_and_execution.atomic_write(path, run)
            fixture_input_and_execution.execute_ready_operations(path, registry)
            self.assertEqual(
                set(
                    fixture_input_and_execution.load_document(path)["container_baselines"][0][
                        "resource_families"
                    ]
                ),
                {"tag", "trigger"},
            )


class TestNativeBoundaries(fixture_native_boundaries.NativeBoundaryTestsFixture):
    def test_applied_write_invalid_reply_is_read_back_without_duplicate(self):
        for shape in ("empty", "invalid-json", "missing-id", "wrong-scope", "missing-path"):
            with self.subTest(shape=shape):
                req = fixture_native_boundaries.request()
                backend = fixture_native_boundaries.FakeGtm(req)
                profile = fixture_native_boundaries.deepcopy(fixture_native_boundaries.PROFILE)
                if shape == "missing-path":
                    profile["families"]["tag"]["object_path"] = ["saved"]

                def call(tool, args):
                    result = backend.call(tool, args)
                    if args["action"] == "create":
                        if shape == "empty":
                            return {"content": []}
                        if shape == "invalid-json":
                            return {"content": [{"type": "text", "text": "invalid"}]}
                        if shape == "missing-id":
                            return {k: v for k, v in result.items() if k != "tagId"}
                        if shape == "wrong-scope":
                            return {**result, "workspaceId": "other"}
                        return result
                    return (
                        {"saved": result}
                        if shape == "missing-path"
                        and tool.endswith("gtm_tag")
                        and args["action"] == "get"
                        else result
                    )

                registry, _ = self.start(req, call, profile)
                fixture_native_boundaries.execute_ready_operations(self.path, registry)
                self.assert_configured(registry)
                self.assertEqual(len(backend.writes), 1)
                create_index = next(
                    i for i, (_, a) in enumerate(backend.calls) if a["action"] == "create"
                )
                self.assertTrue(
                    any(a["action"] == "get" for _, a in backend.calls[create_index + 1 :])
                )
                fresh, _ = self.registry(req, backend.call)
                fixture_native_boundaries.execute_ready_operations(self.path, fresh)
                self.assert_configured(fresh)
                self.assertEqual(len(backend.writes), 1)

    def test_failed_recovery_stays_uncertain_until_fresh_authoritative_read(self):
        req = fixture_native_boundaries.request()
        backend = fixture_native_boundaries.FakeGtm(req)

        def call(tool, args):
            result = backend.call(tool, args)
            if args["action"] == "create":
                backend.hide_once = True
                return {"content": []}
            return result

        registry, _ = self.start(req, call)
        fixture_native_boundaries.execute_ready_operations(self.path, registry)
        document = fixture_native_boundaries.load_document(self.path)
        operation = next(o for o in document["object_changes"] if o["resource_family"] == "tag")
        self.assertEqual(operation["state"], "uncertain")
        fresh, adapter = self.registry(req, backend.call)
        fixture_native_boundaries.execute_ready_operations(self.path, fresh)
        self.assertEqual(len(backend.writes), 1)
        comparison, saved = fixture_native_boundaries.build_verification_comparison(
            operation, adapter.read(operation)
        )
        fixture_native_boundaries.atomic_write(
            self.path,
            fixture_native_boundaries.checkpoint_operation(
                fixture_native_boundaries.load_document(self.path),
                operation_id=operation["operation_id"],
                state="verified",
                note="Fresh recovery read",
                comparison=comparison,
                saved=saved,
            ),
        )
        self.assert_configured(fresh)
        self.assertEqual(len(backend.writes), 1)

    def test_predispatch_failure_remains_failed(self):
        req = fixture_native_boundaries.request()
        backend = fixture_native_boundaries.FakeGtm(req)

        def call(tool, args):
            if args["action"] == "create":
                raise fixture_native_boundaries.AdapterExecutionError(
                    "Local schema refused dispatch"
                )
            return backend.call(tool, args)

        registry, _ = self.start(req, call)
        fixture_native_boundaries.execute_ready_operations(self.path, registry)
        self.assertFalse(backend.writes)
        self.assertEqual(
            next(
                o
                for o in fixture_native_boundaries.load_document(self.path)["object_changes"]
                if o["resource_family"] == "tag"
            )["state"],
            "failed",
        )


class TestPhaseContracts(fixture_phase_contracts.CurrentContractAndRunTestFixture):
    def test_target_identity_and_resource_family_are_isolated(self) -> None:
        contract = fixture_phase_contracts.valid_pipeline_contract()
        duplicate = fixture_phase_contracts.deepcopy(contract["targets"][0])
        duplicate["container_id"] = "GTM-OTHER"
        contract["targets"].append(duplicate)
        with self.assertRaisesRegex(
            fixture_phase_contracts.ContractValidationError, "duplicate target_id"
        ):
            fixture_phase_contracts.validate_contract(contract)

        contract = fixture_phase_contracts.valid_pipeline_contract()
        contract["implementation"]["objects"][2]["resource_family"] = "client"
        with self.assertRaisesRegex(
            fixture_phase_contracts.ContractValidationError, "priority.*required property"
        ):
            fixture_phase_contracts.validate_contract(contract)

    def test_configuration_run_has_no_recette_consumer_contract(self) -> None:
        run = fixture_phase_contracts.create_from_contract(
            fixture_phase_contracts.valid_pipeline_contract(),
            run_id="RUN-NO-RECETTE-COUPLING",
            source_locator="approved input",
            timestamp="2026-08-18T00:00:00Z",
        )
        self.assertNotIn("recette_handoff", run)


class TestDurableEvidence(fixture_durable_evidence.CurrentRegressionHardeningTestFixture):
    def test_complete_baseline_is_bound_to_resources_and_identity_registry(self) -> None:
        run = fixture_durable_evidence.materialize(fixture_durable_evidence.valid_web_contract())
        baseline = run["container_baselines"][0]
        baseline["resources"]["tag"].append({"name": "Injected", "type": "html"})
        baseline["family_counts"]["tag"] += 1
        with self.assertRaisesRegex(
            fixture_durable_evidence.RunValidationError, "resource_identities"
        ):
            fixture_durable_evidence.validate_run(run)

        baseline["resource_identities"]["tag"].append("web-main::tag::Injected")
        with self.assertRaisesRegex(fixture_durable_evidence.RunValidationError, "fingerprint"):
            fixture_durable_evidence.validate_run(run)

        baseline["fingerprint"] = fixture_durable_evidence.canonical_sha256(
            {
                "resources": baseline["resources"],
                "workspace_changes": baseline["preexisting_workspace_changes"],
                "capture_evidence": baseline["capture_evidence"],
            }
        )
        self.assertEqual(fixture_durable_evidence.validate_run(run)["schema_version"], "7.0")

    def test_action_semantics_fail_closed_for_every_high_risk_shape(self) -> None:
        cases = []
        remove = fixture_durable_evidence.valid_web_contract()
        action = remove["implementation"]["objects"][0]
        action.update(
            {
                "action": "remove",
                "object_id": "tag-100",
                "pre_change": fixture_durable_evidence.deepcopy(action["intended"]),
                "evidence": ["approved-input", "official-current", "container-confirmed"],
                "risk": "high-impact",
            }
        )
        action.pop("intended")
        remove["execution_topologies"] = []
        remove["page_view_decisions"] = []
        action.pop("approval")
        cases.append((remove, "approval"))

        rename = fixture_durable_evidence.valid_web_contract()
        action = rename["implementation"]["objects"][0]
        action.update(
            {
                "action": "rename",
                "object_id": "tag-100",
                "pre_change": fixture_durable_evidence.deepcopy(action["intended"]),
                "evidence": ["approved-input", "official-current", "container-confirmed"],
            }
        )
        cases.append((rename, "new_name"))

        reuse = fixture_durable_evidence.valid_web_contract()
        action = reuse["implementation"]["objects"][0]
        action.update(
            {
                "action": "reuse",
                "evidence": ["official-current", "container-confirmed"],
            }
        )
        action.pop("intended")
        cases.append((reuse, "intended"))

        for contract, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(
                    fixture_durable_evidence.ContractValidationError, message
                ):
                    fixture_durable_evidence.validate_contract(contract)


class TestNativeExecutionNativeBinding(fixture_native_execution.NativeBindingTestsFixture):
    def test_identity_mismatch_is_not_cached_and_reconnect_auth_still_fails(self):
        req = fixture_native_execution.request()
        backend = fixture_native_execution.FakeGtm(req)
        changed = {"bad": True, "denied": False}

        def call(tool, args):
            if changed["denied"]:
                return {"isError": True, "structuredContent": {"error": {"code": 401}}}
            result = backend.call(tool, args)
            if changed["bad"] and tool.endswith("gtm_workspace"):
                result["workspaceId"] = "wrong"
            return result

        adapter = fixture_native_execution.McpTargetAdapter(
            req["targets"][0], fixture_native_execution.PROFILE, call
        )
        with self.assertRaises(fixture_native_execution.AdapterExecutionError):
            adapter.identity()
        changed["bad"] = False
        adapter.identity()
        changed["denied"] = True
        with self.assertRaises(fixture_native_execution.AuthenticationError):
            adapter.list_resource_page("tag", None)
        with self.assertRaises(fixture_native_execution.AuthenticationError):
            adapter.mutate(fixture_native_execution.operation("tag"))


class TestMutationRecovery(fixture_mutation_recovery.NativeAndRecoveryTestsFixture):
    def test_read_only_baseline_failure_can_resume_normally(self):
        class Once(fixture_mutation_recovery.FakeAdapter):
            failed = False

            def list_resource_page(self, family, cursor):
                if not self.failed:
                    self.failed = True
                    raise fixture_mutation_recovery.AdapterExecutionError("read-only failure")
                return {"items": [], "next_cursor": None}

        run = fixture_mutation_recovery.create_from_contract(
            fixture_mutation_recovery.valid_web_contract(), run_id="recovery", source_locator="test"
        )
        adapter = Once()
        adapter.bind_target(run["run"]["targets"][0])
        registry = fixture_mutation_recovery.TargetAdapterRegistry()
        registry.register(
            run["run"]["targets"][0],
            adapter,
            fixture_mutation_recovery.capabilities("tag", "trigger"),
        )
        with fixture_mutation_recovery.tempfile.TemporaryDirectory() as directory:
            path = fixture_mutation_recovery.Path(directory) / "run.json"
            fixture_mutation_recovery.atomic_write(path, run)
            fixture_mutation_recovery.execute_ready_operations(path, registry)
            self.assertFalse(adapter.mutations)
            failed = fixture_mutation_recovery.load_document(path)
            self.assertTrue(all(o["state"] == "planned" for o in failed["object_changes"]))
            self.assertIn(
                "read-only failure", failed["target_results"][0]["baseline_error"]["error"]
            )
            fixture_mutation_recovery.execute_ready_operations(path, registry)
            result = fixture_mutation_recovery.load_document(path)
            self.assertTrue(all(o["state"] == "verified" for o in result["object_changes"]))
            self.assertNotIn("baseline_error", result["target_results"][0])

    def test_only_complete_notes_delta_skips_consumer_scan(self):
        before = {"type": "c", "parameter": [{"key": "value", "type": "template", "value": "a"}]}
        operation = {
            "resource_family": "variable",
            "action": "update",
            "pre_change": before,
            "intended": {**fixture_mutation_recovery.deepcopy(before), "notes": "reviewed"},
        }
        self.assertFalse(fixture_mutation_recovery.requires_variable_consumer_check(operation))
        operation["intended"]["parameter"][0]["value"] = "b"
        self.assertTrue(fixture_mutation_recovery.requires_variable_consumer_check(operation))
        operation["intended"] = {"notes": "partial snapshot"}
        self.assertTrue(fixture_mutation_recovery.requires_variable_consumer_check(operation))


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_execution_needs_a_complete_relevant_baseline(self):
        run = fixture_transport_and_state.create_from_contract(
            fixture_transport_and_state.valid_web_contract(),
            run_id="BASELINE",
            source_locator="synthetic",
        )
        self.assertEqual(fixture_transport_and_state.inspect_document(run)["ready_operations"], [])
        with self.assertRaisesRegex(fixture_transport_and_state.RunValidationError, "baseline"):
            fixture_transport_and_state.checkpoint_operation(
                run,
                operation_id=run["object_changes"][1]["operation_id"],
                state="in_progress",
                note="synthetic",
            )
        with self.assertRaisesRegex(
            fixture_transport_and_state.RunValidationError, "resource families"
        ):
            resources = {"folder": []}
            fixture_transport_and_state.run_state.record_target_baseline(
                run,
                target_id="web-main",
                resources=resources,
                captured_at="2026-09-05",
                preexisting_workspace_changes=[],
                capture_evidence=fixture_transport_and_state.complete_capture_evidence(
                    resources, run["run"]["targets"][0]
                ),
            )
        self.assertTrue(
            fixture_transport_and_state.inspect_document(
                fixture_transport_and_state.with_complete_baselines(run)
            )["ready_operations"]
        )

    def test_authentication_failure_stops_the_target(self):
        run = fixture_transport_and_state.with_complete_baselines(
            fixture_transport_and_state.create_from_contract(
                fixture_transport_and_state.valid_web_contract(),
                run_id="AUTH",
                source_locator="synthetic",
            )
        )
        operation_id = fixture_transport_and_state.inspect_document(run)["ready_operations"][0]
        run = fixture_transport_and_state.checkpoint_operation(
            run,
            operation_id=operation_id,
            state="failed",
            note="Target reauthentication needed",
            error="authentication_required: synthetic",
        )
        self.assertEqual(fixture_transport_and_state.inspect_document(run)["ready_operations"], [])
