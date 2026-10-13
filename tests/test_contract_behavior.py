"""Behavioral tests owned by contract."""

from support import input_and_execution as fixture_input_and_execution


class TestInputAndExecution(fixture_input_and_execution.AuditRegressionsFixture):
    def test_both_validators_reject_structural_leaks(self):
        contract = fixture_input_and_execution.valid_web_contract()
        contract["implementation"]["objects"][0]["intended"]["parameter"] = [
            fixture_input_and_execution.row("access_token")
        ]
        with self.assertRaisesRegex(ValueError, "literal secret"):
            fixture_input_and_execution.validate_contract(
                fixture_input_and_execution.approve_mutations(contract)
            )
        run = fixture_input_and_execution.create_from_contract(
            fixture_input_and_execution.valid_web_contract(),
            run_id="canary",
            source_locator="Synthetic request",
        )
        run["run"]["id"] = 'access_token = "' + fixture_input_and_execution.CANARY + '"'
        with self.assertRaisesRegex(ValueError, "literal secret"):
            fixture_input_and_execution.validate_document(run)
