import sys
import unittest
from unittest.mock import patch

from tokstat import cli, config


class TestCLIFullPipeline(unittest.TestCase):
    """Bare `tokstat` must gather usage, render the dashboard and open it."""

    def _run_main(self, argv):
        with patch.object(sys, "argv", ["tokstat"] + argv):
            cli.main()

    def test_bare_tokstat_runs_full_pipeline(self):
        calls = []

        def record(name):
            return lambda *a, **k: calls.append(name)

        with patch.object(cli, "migration") as migration, \
             patch.object(cli, "run_collectors_once", side_effect=record("collect")), \
             patch.object(cli, "generate_dashboard", side_effect=record("render")), \
             patch.object(cli, "_open_dashboard", side_effect=record("open")) as open_dash:
            migration.check_and_run_migrations.side_effect = record("migrate")
            self._run_main([])

        # Exact order contract: migrate -> collect -> render -> open.
        self.assertEqual(calls, ["migrate", "collect", "render", "open"])
        open_dash.assert_called_once_with(config.DASHBOARD_PATH)

    def test_collector_failure_does_not_block_rendering(self):
        with patch.object(cli, "migration"), \
             patch.object(cli, "run_collectors_once", side_effect=RuntimeError("boom")) as collect, \
             patch.object(cli, "generate_dashboard") as render, \
             patch.object(cli, "_open_dashboard"):
            self._run_main([])

        collect.assert_called_once()
        render.assert_called_once()

    def test_no_collect_skips_gathering(self):
        with patch.object(cli, "migration") as migration, \
             patch.object(cli, "run_collectors_once") as collect, \
             patch.object(cli, "generate_dashboard") as render, \
             patch.object(cli, "_open_dashboard") as open_dash:
            self._run_main(["--no-collect"])

        migration.check_and_run_migrations.assert_called_once()
        collect.assert_not_called()
        render.assert_called_once()
        open_dash.assert_called_once()

    def test_no_open_skips_browser(self):
        with patch.object(cli, "migration") as migration, \
             patch.object(cli, "run_collectors_once") as collect, \
             patch.object(cli, "generate_dashboard") as render, \
             patch.object(cli, "_open_dashboard") as open_dash:
            self._run_main(["--no-open"])

        migration.check_and_run_migrations.assert_called_once()
        collect.assert_called_once()
        render.assert_called_once()
        open_dash.assert_not_called()

    def test_no_collect_no_open_renders_only(self):
        with patch.object(cli, "migration"), \
             patch.object(cli, "run_collectors_once") as collect, \
             patch.object(cli, "generate_dashboard") as render, \
             patch.object(cli, "_open_dashboard") as open_dash:
            self._run_main(["--no-collect", "--no-open"])

        collect.assert_not_called()
        render.assert_called_once()
        open_dash.assert_not_called()


class TestCLISubcommands(unittest.TestCase):
    """Subcommand dispatch must still work untouched."""

    @patch("tokstat.cli.cmd_migrate")
    def test_migrate_subcommand(self, cmd):
        with patch.object(sys, "argv", ["tokstat", "migrate", "--force"]):
            cli.main()
        cmd.assert_called_once_with(True)

    @patch("tokstat.cli.cmd_collect")
    def test_collect_subcommand(self, cmd):
        with patch.object(sys, "argv", ["tokstat", "collect", "--once"]):
            cli.main()
        cmd.assert_called_once_with(True)

    @patch("tokstat.cli.cmd_daemon")
    def test_daemon_subcommand(self, cmd):
        with patch.object(sys, "argv", ["tokstat", "daemon", "status"]):
            cli.main()
        cmd.assert_called_once_with("status")

    @patch("tokstat.cli.cmd_sync")
    def test_sync_subcommand(self, cmd):
        with patch.object(sys, "argv", ["tokstat", "sync"]):
            cli.main()
        cmd.assert_called_once_with(lookback_days=None)

    @patch("tokstat.cli.cmd_sync")
    def test_sync_subcommand_with_lookback(self, cmd):
        with patch.object(sys, "argv", ["tokstat", "sync", "--lookback-days", "90"]):
            cli.main()
        cmd.assert_called_once_with(lookback_days=90)


if __name__ == "__main__":
    unittest.main()
