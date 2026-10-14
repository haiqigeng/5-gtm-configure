"""Behavioral tests owned by packaging."""

from check_release import CURRENT_RELEASE
from support import transport_and_state as fixture_transport_and_state


class TestTransportAndState(fixture_transport_and_state.UtilityEvolutionTestFixture):
    def test_git_failure_is_not_a_clean_release(self):
        with fixture_transport_and_state.patch("check_release.subprocess.run") as command:
            command.return_value = fixture_transport_and_state.subprocess.CompletedProcess(
                ["git"], 128, "", "synthetic failure"
            )
            errors = fixture_transport_and_state.check_git_state(
                tag=f"v{CURRENT_RELEASE}", require_tag=True, require_clean=True
            )
        self.assertEqual(len(errors), 2)
        self.assertTrue(all("git exited 128" in error for error in errors))
