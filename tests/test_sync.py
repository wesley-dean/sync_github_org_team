"""Offline unit tests for GitHub organization-to-team synchronization.

The application's external imports are replaced during module loading so this
suite requires only Python's standard library and cannot reach GitHub.
"""

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock, Mock, patch


def load_application():
    """Import sync.py using fake external dependencies and safe configuration."""
    dotenv = ModuleType("dotenv")
    dotenv.load_dotenv = Mock(return_value=None)

    github = ModuleType("github")
    github.Github = Mock(name="Github")

    path = Path(__file__).resolve().parents[1] / "sync.py"
    spec = importlib.util.spec_from_file_location("sync_under_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load sync.py for unit testing")

    application = importlib.util.module_from_spec(spec)
    environment = {
        "PAT": "offline-test-token",
        "ORG": "example-org",
        "TEAM_NAME": "everyone",
        "DRY_RUN": "True",
        "USER_FILTERS": "{}",
        "DELAY": "0",
    }
    with patch.dict(os.environ, environment):
        with patch.dict(sys.modules, {"dotenv": dotenv, "github": github}):
            spec.loader.exec_module(application)

    return application


sync = load_application()


def user(login):
    """Return a minimal stand-in for a PyGithub user."""
    return SimpleNamespace(login=login)


class ConfigurationTests(unittest.TestCase):
    """Check parsing of dry-run flags without changing remote state."""

    def test_dry_run_defaults_to_enabled(self):
        self.assertTrue(sync.is_dry_run())

    def test_dry_run_accepts_documented_values(self):
        for value in ("true", "TRUE", "yes", "YES"):
            with self.subTest(value=value):
                self.assertTrue(sync.is_dry_run(value))

        for value in ("false", "FALSE", "no", "NO"):
            with self.subTest(value=value):
                self.assertFalse(sync.is_dry_run(value))

    def test_dry_run_fails_closed_for_unknown_values(self):
        for value in ("", "maybe", "0", "1", "disabled"):
            with self.subTest(value=value):
                self.assertTrue(sync.is_dry_run(value))


class MembershipLookupTests(unittest.TestCase):
    """Exercise organization and team read operations."""

    def test_group_logins_returns_login_keys(self):
        group = MagicMock()
        group.get_members.return_value = [user("alice"), user("bob")]
        self.assertEqual(sync.get_group_logins(group), {"alice": True, "bob": True})
        group.get_members.assert_called_once_with()

    def test_group_logins_handles_empty_group(self):
        group = MagicMock()
        group.get_members.return_value = []
        self.assertEqual(sync.get_group_logins(group), {})

    def test_group_logins_deduplicates_logins(self):
        group = MagicMock()
        group.get_members.return_value = [user("alice"), user("alice")]
        self.assertEqual(sync.get_group_logins(group), {"alice": True})

    def test_existing_team_is_reused_without_creating_one(self):
        org = MagicMock()
        other = SimpleNamespace(name="other")
        expected = SimpleNamespace(name="everyone")
        org.get_teams.return_value = [other, expected]

        self.assertIs(sync.create_team_if_not_exists("everyone", org), expected)
        org.create_team.assert_not_called()

    def test_missing_team_is_created(self):
        org = MagicMock()
        org.get_teams.return_value = [SimpleNamespace(name="other")]
        expected = org.create_team.return_value

        self.assertIs(sync.create_team_if_not_exists("everyone", org), expected)
        org.create_team.assert_called_once_with("everyone")

    def test_team_names_are_matched_exactly(self):
        org = MagicMock()
        org.get_teams.return_value = [SimpleNamespace(name="Everyone")]

        sync.create_team_if_not_exists("everyone", org)
        org.create_team.assert_called_once_with("everyone")


class FilterTests(unittest.TestCase):
    """Exercise the supported login filter rules."""

    def test_no_filters_means_no_exclusion(self):
        with patch.object(sync, "USER_FILTERS", {}):
            self.assertIsNone(sync.allow_user(user("alice")))

    def test_reject_regex_excludes_matching_member(self):
        filters = {"login": {"reject": ["^bot"]}}
        with patch.object(sync, "USER_FILTERS", filters):
            self.assertIs(sync.allow_user(user("bot-helper")), False)
            self.assertIsNone(sync.allow_user(user("alice")))

    def test_regex_matching_is_case_insensitive(self):
        filters = {"login": {"reject": ["^bot"]}}
        with patch.object(sync, "USER_FILTERS", filters):
            self.assertIs(sync.allow_user(user("BOT-helper")), False)

    def test_allow_regex_overrides_rejection(self):
        filters = {"login": {"reject": ["^bot"], "allow": ["admin$"]}}
        with patch.object(sync, "USER_FILTERS", filters):
            self.assertIs(sync.allow_user(user("bot-admin")), True)
            self.assertIs(sync.allow_user(user("bot-helper")), False)

    def test_allow_without_rejection_preserves_default(self):
        filters = {"login": {"allow": ["^alice$"]}}
        with patch.object(sync, "USER_FILTERS", filters):
            self.assertIsNone(sync.allow_user(user("bob")))

    def test_multiple_reject_patterns_are_checked(self):
        filters = {"login": {"reject": ["^bot", "-service$"]}}
        with patch.object(sync, "USER_FILTERS", filters):
            self.assertIs(sync.allow_user(user("ci-service")), False)
            self.assertIs(sync.allow_user(user("bot-helper")), False)
            self.assertIsNone(sync.allow_user(user("alice")))


class MembershipMutationTests(unittest.TestCase):
    """Verify dry runs do not mutate team membership."""

    def setUp(self):
        self.member = user("alice")
        self.team = MagicMock()
        self.team.name = "everyone"

    def test_dry_run_skips_addition(self):
        with patch.object(sync, "is_dry_run", return_value=True):
            self.assertIsNone(sync.add_member_to_team(self.member, self.team))
        self.team.add_membership.assert_not_called()

    def test_live_addition_calls_team_api(self):
        with patch.object(sync, "is_dry_run", return_value=False):
            result = sync.add_member_to_team(self.member, self.team)
        self.team.add_membership.assert_called_once_with(self.member)
        self.assertIs(result, self.team.add_membership.return_value)

    def test_dry_run_skips_removal(self):
        with patch.object(sync, "is_dry_run", return_value=True):
            self.assertIsNone(sync.remove_member_from_team(self.member, self.team))
        self.team.remove_member.assert_not_called()

    def test_live_removal_uses_login(self):
        with patch.object(sync, "is_dry_run", return_value=False):
            result = sync.remove_member_from_team(self.member, self.team)
        self.team.remove_member.assert_called_once_with("alice")
        self.assertIs(result, self.team.remove_member.return_value)


class SynchronizationTests(unittest.TestCase):
    """Run main() against an entirely mocked GitHub service."""

    def run_sync(self, org_logins, team_logins, filters=None, dry_run=False):
        github = MagicMock()
        organization = github.get_organization.return_value
        team = MagicMock()
        team.name = "everyone"

        members = {login: user(login) for login in org_logins}
        organization.get_members.return_value = [members[name] for name in org_logins]
        team.get_members.return_value = [user(name) for name in team_logins]
        github.get_user.side_effect = members.__getitem__

        with (
            patch.object(sync, "Github", return_value=github) as github_factory,
            patch.object(sync, "create_team_if_not_exists", return_value=team) as find_team,
            patch.object(sync, "USER_FILTERS", filters if filters is not None else {}),
            patch.object(sync, "is_dry_run", return_value=dry_run),
            patch.object(sync.time, "sleep") as sleep,
        ):
            sync.main()

        github_factory.assert_called_once_with(
            login_or_token=sync.PAT, base_url=sync.API_URL
        )
        github.get_organization.assert_called_once_with(sync.ORG)
        find_team.assert_called_once_with(sync.TEAM_NAME, organization)
        return github, team, members, sleep

    def test_adds_missing_allowed_user(self):
        _, team, members, sleep = self.run_sync(
            ["alice", "bob"], ["alice"]
        )
        team.add_membership.assert_called_once_with(members["bob"])
        team.remove_member.assert_not_called()
        sleep.assert_called_once_with(0.0)

    def test_removes_present_rejected_user(self):
        filters = {"login": {"reject": ["^bot"]}}
        _, team, _, sleep = self.run_sync(
            ["bot-helper"], ["bot-helper"], filters=filters
        )
        team.remove_member.assert_called_once_with("bot-helper")
        team.add_membership.assert_not_called()
        sleep.assert_not_called()

    def test_keeps_existing_allowed_user(self):
        _, team, _, _ = self.run_sync(["alice"], ["alice"])
        team.add_membership.assert_not_called()
        team.remove_member.assert_not_called()

    def test_does_not_add_rejected_user(self):
        filters = {"login": {"reject": ["^bot"]}}
        _, team, _, _ = self.run_sync(["bot-helper"], [], filters=filters)
        team.add_membership.assert_not_called()
        team.remove_member.assert_not_called()

    def test_allow_override_adds_previously_rejected_user(self):
        filters = {"login": {"reject": ["^bot"], "allow": ["admin$"]}}
        _, team, members, _ = self.run_sync(
            ["bot-admin"], [], filters=filters
        )
        team.add_membership.assert_called_once_with(members["bot-admin"])

    def test_dry_run_never_changes_membership(self):
        filters = {"login": {"reject": ["^bot"]}}
        github, team, _, _ = self.run_sync(
            ["alice", "bot-helper"], ["bot-helper"],
            filters=filters, dry_run=True,
        )
        team.add_membership.assert_not_called()
        team.remove_member.assert_not_called()
        self.assertEqual(github.get_user.call_count, 2)

    def test_empty_organization_does_no_work(self):
        github, team, _, sleep = self.run_sync([], [])
        github.get_user.assert_not_called()
        team.add_membership.assert_not_called()
        team.remove_member.assert_not_called()
        sleep.assert_not_called()

    def test_sleep_occurs_only_between_members(self):
        _, team, _, sleep = self.run_sync(
            ["alice", "bob", "carol"],
            ["alice", "bob", "carol"],
        )
        self.assertEqual(sleep.call_count, 2)
        sleep.assert_any_call(0.0)
        team.add_membership.assert_not_called()
        team.remove_member.assert_not_called()


if __name__ == "__main__":
    unittest.main()
