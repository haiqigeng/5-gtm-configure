"""Behavioral tests owned by adapters."""

from support import mutation_recovery as fixture_mutation_recovery


class TestMutationRecovery(fixture_mutation_recovery.NativeAndRecoveryTestsFixture):
    def test_structured_mcp_rejections_and_unknown_outcomes(self):
        for mutation in (False, True):
            for code, cls in (
                (401, fixture_mutation_recovery.AuthenticationError),
                (429, fixture_mutation_recovery.RateLimitError),
                (400, fixture_mutation_recovery.AdapterExecutionError),
                (403, fixture_mutation_recovery.AdapterExecutionError),
            ):
                response = {
                    "isError": True,
                    "content": [
                        {
                            "type": "text",
                            "text": fixture_mutation_recovery.json.dumps(
                                {"error": {"code": code, "message": "must not persist raw detail"}}
                            ),
                        }
                    ],
                }
                with self.subTest(code=code, mutation=mutation), self.assertRaises(cls) as caught:
                    fixture_mutation_recovery.unwrap(response, mutation=mutation)
                self.assertNotIn("raw detail", str(caught.exception))
                self.assertNotIsInstance(
                    caught.exception, fixture_mutation_recovery.AmbiguousWriteError
                )
            with self.assertRaises(
                fixture_mutation_recovery.AmbiguousWriteError
                if mutation
                else fixture_mutation_recovery.AdapterExecutionError
            ) as caught:
                fixture_mutation_recovery.unwrap(
                    {
                        "isError": True,
                        "content": [{"type": "text", "text": "HTTP 401, safe to retry"}],
                    },
                    mutation=mutation,
                )
            if not mutation:
                self.assertNotIsInstance(
                    caught.exception, fixture_mutation_recovery.AmbiguousWriteError
                )

    def test_cold_reference_loads_missing_family_and_retains_complete_cache(self):
        calls = []
        target = {"target_id": "w", "account_id": "1", "container_id": "2", "workspace_id": "3"}
        profile = {
            "tool_prefix": "",
            "workspace_path": [],
            "container_path": [],
            "status_path": [],
            "families": {
                "folder": {
                    "actions": ["list"],
                    "page_size": 10,
                    "first_page": 1,
                    "list_path": [],
                    "object_path": [],
                }
            },
        }

        def call(tool, arguments):
            calls.append((tool, arguments["action"]))
            return [
                {
                    "folderId": "4",
                    "name": "Folder",
                    "accountId": "1",
                    "containerId": "2",
                    "workspaceId": "3",
                }
            ]

        # MCP returns a structured list inside a response object.
        adapter = fixture_mutation_recovery.McpTargetAdapter(
            target, profile, lambda t, a: {"structuredContent": call(t, a)}
        )
        adapter.cache["folder"] = []  # incomplete cache must never imply absence
        self.assertEqual(adapter._resolve_reference("w::folder::Folder", "folderId"), "4")
        self.assertEqual(adapter._resolve_reference("w::folder::Folder", "folderId"), "4")
        self.assertEqual(calls, [("gtm_folder", "list")])
        adapter.cache["folder"] = []
        adapter.known_ids["w::folder::Folder"] = "stale"
        with self.assertRaises(fixture_mutation_recovery.AdapterExecutionError):
            adapter._resolve_reference("w::folder::Folder", "folderId")
