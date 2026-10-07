"""
Tests for the main CLI module.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from hpde_analytics_cli import paths
from hpde_analytics_cli.main import (
    create_parser,
    handle_credential_commands,
    load_environment,
)


class TestCreateParser:
    """Tests for create_parser function."""

    def test_parser_creation(self):
        """Test that parser is created successfully."""
        parser = create_parser()
        assert parser is not None
        assert parser.prog == "hpde-analytics-cli"

    def test_parser_configure_arg(self):
        """Test --configure argument."""
        parser = create_parser()
        args = parser.parse_args(["--configure"])
        assert args.configure is True

    def test_parser_credential_status_arg(self):
        """Test --credential-status argument."""
        parser = create_parser()
        args = parser.parse_args(["--credential-status"])
        assert args.credential_status is True

    def test_parser_auth_arg(self):
        """Test --auth argument."""
        parser = create_parser()
        args = parser.parse_args(["--auth"])
        assert args.auth is True

    def test_parser_discover_arg(self):
        """Test --discover argument."""
        parser = create_parser()
        args = parser.parse_args(["--discover"])
        assert args.discover is True

    def test_parser_export_arg(self):
        """Test --export argument."""
        parser = create_parser()
        args = parser.parse_args(["--export"])
        assert args.export is True

    def test_parser_report_arg(self):
        """Test --report argument."""
        parser = create_parser()
        args = parser.parse_args(["--report"])
        assert args.report is True

    def test_parser_event_id_arg(self):
        """Test --event-id argument."""
        parser = create_parser()
        args = parser.parse_args(["--event-id", "EVENT123"])
        assert args.event_id == "EVENT123"

    def test_parser_org_id_arg(self):
        """Test --org-id argument."""
        parser = create_parser()
        args = parser.parse_args(["--org-id", "ORG456"])
        assert args.org_id == "ORG456"

    def test_parser_output_dir_arg(self):
        """Test --output-dir argument."""
        parser = create_parser()
        args = parser.parse_args(["--output-dir", "/path/to/output"])
        assert args.output_dir == "/path/to/output"

    def test_parser_export_dir_arg(self):
        """Test --export-dir argument."""
        parser = create_parser()
        args = parser.parse_args(["--export-dir", "/path/to/export"])
        assert args.export_dir == "/path/to/export"

    def test_parser_report_file_arg(self):
        """Test --report-file argument."""
        parser = create_parser()
        args = parser.parse_args(["--report-file", "/path/to/report.xlsx"])
        assert args.report_file == "/path/to/report.xlsx"

    def test_parser_name_arg(self):
        """Test --name argument."""
        parser = create_parser()
        args = parser.parse_args(["--name", "HPDE_TT_1_2025"])
        assert args.name == "HPDE_TT_1_2025"

    def test_parser_verbose_arg(self):
        """Test --verbose argument."""
        parser = create_parser()
        args = parser.parse_args(["--verbose"])
        assert args.verbose is True

    def test_parser_verbose_short_arg(self):
        """Test -v argument."""
        parser = create_parser()
        args = parser.parse_args(["-v"])
        assert args.verbose is True

    def test_parser_defaults(self):
        """Test parser default values."""
        parser = create_parser()
        args = parser.parse_args([])

        assert args.configure is False
        assert args.credential_status is False
        assert args.auth is False
        assert args.discover is False
        assert args.export is False
        assert args.report is False
        assert args.verbose is False
        assert args.event_id is None
        assert args.org_id is None

    def test_parser_combined_args(self):
        """Test multiple arguments together."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "--export",
                "--org-id",
                "ORG123",
                "--event-id",
                "EVENT456",
                "--name",
                "TestExport",
                "--verbose",
            ]
        )

        assert args.export is True
        assert args.org_id == "ORG123"
        assert args.event_id == "EVENT456"
        assert args.name == "TestExport"
        assert args.verbose is True


class TestHandleCredentialCommands:
    """Tests for handle_credential_commands function."""

    @patch("hpde_analytics_cli.main.CredentialManager")
    def test_configure_success(self, mock_manager_class):
        """Test --configure command success."""
        mock_manager = MagicMock()
        mock_manager.configure_interactive.return_value = True
        mock_manager_class.return_value = mock_manager

        args = MagicMock()
        args.configure = True
        args.credential_status = False

        with pytest.raises(SystemExit) as exc_info:
            handle_credential_commands(args)

        assert exc_info.value.code == 0
        mock_manager.configure_interactive.assert_called_once()

    @patch("hpde_analytics_cli.main.CredentialManager")
    def test_configure_failure(self, mock_manager_class):
        """Test --configure command failure."""
        mock_manager = MagicMock()
        mock_manager.configure_interactive.return_value = False
        mock_manager_class.return_value = mock_manager

        args = MagicMock()
        args.configure = True
        args.credential_status = False

        with pytest.raises(SystemExit) as exc_info:
            handle_credential_commands(args)

        assert exc_info.value.code == 1

    @patch("hpde_analytics_cli.main.CredentialManager")
    def test_credential_status(self, mock_manager_class):
        """Test --credential-status command."""
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        args = MagicMock()
        args.configure = False
        args.credential_status = True

        with pytest.raises(SystemExit) as exc_info:
            handle_credential_commands(args)

        assert exc_info.value.code == 0
        mock_manager.show_status.assert_called_once()

    def test_no_credential_command(self):
        """Test when no credential command is given."""
        args = MagicMock()
        args.configure = False
        args.credential_status = False

        result = handle_credential_commands(args)

        assert result is False


class TestLoadEnvironment:
    """Tests for load_environment function."""

    @pytest.fixture(autouse=True)
    def isolated_env(self, tmp_path, monkeypatch):
        """Run in an empty directory with the user config dir pointed somewhere empty."""
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)
        monkeypatch.setenv(paths.ENV_CONFIG_DIR, str(tmp_path / "config"))
        return work

    @patch("hpde_analytics_cli.main.load_dotenv")
    def test_loads_env_from_working_directory(self, mock_load_dotenv, isolated_env):
        """A .env beside the user, not beside the installed package, is what gets read."""
        env_file = isolated_env / ".env"
        env_file.write_text("MSR_BASE_URL=https://example.test\n")

        load_environment(verbose=False)

        mock_load_dotenv.assert_called_once()
        assert mock_load_dotenv.call_args[0][0].resolve() == env_file.resolve()

    @patch("hpde_analytics_cli.main.load_dotenv")
    def test_loads_project_env_before_user_env(self, mock_load_dotenv, isolated_env, tmp_path):
        """Project .env is loaded first so its keys win; the user file fills the rest."""
        project_env = isolated_env / ".env"
        project_env.write_text("MSR_BASE_URL=https://project.test\n")
        config = tmp_path / "config"
        config.mkdir()
        user_env = config / ".env"
        user_env.write_text("MSR_CALLBACK_PORT=9999\n")

        load_environment(verbose=False)

        loaded = [call[0][0].resolve() for call in mock_load_dotenv.call_args_list]
        assert loaded == [project_env.resolve(), user_env.resolve()]

    @patch("hpde_analytics_cli.main.load_dotenv")
    def test_skips_when_no_env(self, mock_load_dotenv, isolated_env):
        """No .env anywhere is not an error, and nothing is loaded."""
        load_environment(verbose=False)
        mock_load_dotenv.assert_not_called()

    @patch("hpde_analytics_cli.main.load_dotenv")
    def test_verbose_output(self, mock_load_dotenv, isolated_env, capsys):
        """Test verbose output when loading .env."""
        (isolated_env / ".env").write_text("MSR_BASE_URL=https://example.test\n")

        load_environment(verbose=True)

        captured = capsys.readouterr()
        assert "Loaded environment" in captured.out


class TestPopulateEmailsParser:
    """Tests for --populate-emails argument parsing."""

    def test_parser_populate_emails_arg(self):
        """Test --populate-emails flag."""
        parser = create_parser()
        args = parser.parse_args(["--populate-emails"])
        assert args.populate_emails is True

    def test_parser_sheet_id_arg(self):
        """Test --sheet-id argument."""
        parser = create_parser()
        args = parser.parse_args(["--sheet-id", "abc123"])
        assert args.sheet_id == "abc123"

    def test_parser_worksheet_arg(self):
        """Test --worksheet argument."""
        parser = create_parser()
        args = parser.parse_args(["--worksheet", "Form Responses 1"])
        assert args.worksheet == "Form Responses 1"

    def test_parser_name_column_default(self):
        """Default --name-column should be 'name'."""
        parser = create_parser()
        args = parser.parse_args([])
        assert args.name_column == "name"

    def test_parser_email_column_default(self):
        """Default --email-column should be 'email'."""
        parser = create_parser()
        args = parser.parse_args([])
        assert args.email_column == "email"

    def test_parser_group_filter_default(self):
        """Default --group-filter should be 'novice'."""
        parser = create_parser()
        args = parser.parse_args([])
        assert args.group_filter == "novice"

    def test_parser_group_filter_custom(self):
        """Custom --group-filter value should be stored."""
        parser = create_parser()
        args = parser.parse_args(["--group-filter", "beginner hpde"])
        assert args.group_filter == "beginner hpde"

    def test_parser_service_account_key_arg(self):
        """Test --service-account-key argument."""
        parser = create_parser()
        args = parser.parse_args(["--service-account-key", "/path/to/key.json"])
        assert args.service_account_key == "/path/to/key.json"

    def test_parser_service_account_key_default(self):
        """Default --service-account-key should be None."""
        parser = create_parser()
        args = parser.parse_args([])
        assert args.service_account_key is None

    def test_parser_dry_run_arg(self):
        """Test --dry-run flag."""
        parser = create_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_parser_dry_run_default(self):
        """Default --dry-run should be False."""
        parser = create_parser()
        args = parser.parse_args([])
        assert args.dry_run is False

    def test_parser_combined_populate_emails(self):
        """Test full --populate-emails command with all arguments."""
        parser = create_parser()
        args = parser.parse_args(
            [
                "--populate-emails",
                "--sheet-id",
                "abc123",
                "--export-dir",
                "/path/to/export",
                "--name-column",
                "Student Name",
                "--email-column",
                "D",
                "--group-filter",
                "novice hpde",
                "--service-account-key",
                "/path/to/key.json",
                "--verbose",
            ]
        )
        assert args.populate_emails is True
        assert args.sheet_id == "abc123"
        assert args.export_dir == "/path/to/export"
        assert args.name_column == "Student Name"
        assert args.email_column == "D"
        assert args.group_filter == "novice hpde"
        assert args.service_account_key == "/path/to/key.json"
        assert args.verbose is True


class TestCLIIntegration:
    """Integration tests for CLI."""

    def test_help_output(self, capsys):
        """Test that --help works."""
        parser = create_parser()

        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--help"])

        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "hpde-analytics-cli" in captured.out
        assert "--configure" in captured.out
        assert "--export" in captured.out
        assert "--report" in captured.out

    def test_parser_description(self):
        """Test parser description."""
        parser = create_parser()

        # Access description
        assert "HPDE Analytics" in parser.description
        assert "MotorsportsReg" in parser.description
