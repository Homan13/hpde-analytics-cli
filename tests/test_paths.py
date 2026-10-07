"""
Tests for filesystem path resolution.

The property under test throughout is that no user-facing path depends on where the
package happens to be installed. See CODE_REVIEW.md #2.
"""

import json
import os
import stat
import sys

import pytest

from hpde_analytics_cli import paths


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Point the per-user config directory at a temporary directory."""
    target = tmp_path / "config"
    monkeypatch.setenv(paths.ENV_CONFIG_DIR, str(target))
    return target


class TestConfigDir:
    def test_honours_env_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv(paths.ENV_CONFIG_DIR, str(tmp_path / "custom"))
        assert paths.config_dir() == tmp_path / "custom"

    def test_expands_user_in_override(self, monkeypatch):
        monkeypatch.setenv(paths.ENV_CONFIG_DIR, "~/somewhere")
        assert "~" not in str(paths.config_dir())

    def test_falls_back_to_platform_location(self, monkeypatch):
        monkeypatch.delenv(paths.ENV_CONFIG_DIR, raising=False)
        resolved = paths.config_dir()
        assert resolved.is_absolute()
        assert paths.APP_NAME in str(resolved)

    def test_not_inside_site_packages(self, monkeypatch):
        """The whole point of the module: never resolve into the install location."""
        monkeypatch.delenv(paths.ENV_CONFIG_DIR, raising=False)
        package_root = str(os.path.dirname(os.path.dirname(paths.__file__)))
        assert not str(paths.config_dir()).startswith(package_root)


class TestTokenFile:
    def test_lives_in_config_dir(self, config_dir):
        assert paths.token_file() == config_dir / paths.TOKEN_FILENAME

    def test_independent_of_working_directory(self, config_dir, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        first = paths.token_file()
        sub = tmp_path / "elsewhere"
        sub.mkdir()
        monkeypatch.chdir(sub)
        assert paths.token_file() == first


class TestDefaultOutputDir:
    def test_relative_to_working_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert paths.default_output_dir() == tmp_path / paths.OUTPUT_DIRNAME

    def test_follows_working_directory(self, tmp_path, monkeypatch):
        sub = tmp_path / "events"
        sub.mkdir()
        monkeypatch.chdir(sub)
        assert paths.default_output_dir() == sub / paths.OUTPUT_DIRNAME


class TestFindEnvFiles:
    def test_finds_project_env_in_cwd(self, tmp_path, monkeypatch, config_dir):
        monkeypatch.chdir(tmp_path)
        env = tmp_path / ".env"
        env.write_text("MSR_BASE_URL=https://example.test\n")
        assert env.resolve() in [p.resolve() for p in paths.find_env_files()]

    def test_searches_upward_from_cwd(self, tmp_path, monkeypatch, config_dir):
        env = tmp_path / ".env"
        env.write_text("MSR_BASE_URL=https://example.test\n")
        nested = tmp_path / "a" / "b"
        nested.mkdir(parents=True)
        monkeypatch.chdir(nested)
        assert env.resolve() in [p.resolve() for p in paths.find_env_files()]

    def test_includes_user_env(self, tmp_path, monkeypatch, config_dir):
        monkeypatch.chdir(tmp_path)
        config_dir.mkdir(parents=True)
        user_env = config_dir / ".env"
        user_env.write_text("MSR_BASE_URL=https://user.test\n")
        assert user_env.resolve() in [p.resolve() for p in paths.find_env_files()]

    def test_project_env_takes_precedence(self, tmp_path, monkeypatch, config_dir):
        monkeypatch.chdir(tmp_path)
        project_env = tmp_path / ".env"
        project_env.write_text("MSR_BASE_URL=https://project.test\n")
        config_dir.mkdir(parents=True)
        (config_dir / ".env").write_text("MSR_BASE_URL=https://user.test\n")

        found = paths.find_env_files()
        assert len(found) == 2
        assert found[0].resolve() == project_env.resolve()

    def test_returns_empty_when_none_exist(self, tmp_path, monkeypatch, config_dir):
        monkeypatch.chdir(tmp_path)
        assert paths.find_env_files() == []


class TestMigrateLegacyToken:
    def test_no_op_when_nothing_to_migrate(self, config_dir, monkeypatch, tmp_path):
        monkeypatch.setattr(paths, "legacy_token_file", lambda: tmp_path / "absent.json")
        assert paths.migrate_legacy_token(paths.token_file()) is None

    def test_no_op_when_destination_exists(self, config_dir, monkeypatch, tmp_path):
        legacy = tmp_path / "legacy.json"
        legacy.write_text('{"access_token": "old"}')
        monkeypatch.setattr(paths, "legacy_token_file", lambda: legacy)

        destination = paths.token_file()
        destination.parent.mkdir(parents=True)
        destination.write_text('{"access_token": "current"}')

        assert paths.migrate_legacy_token(destination) is None
        assert json.loads(destination.read_text())["access_token"] == "current"
        assert legacy.exists(), "must not consume the legacy file when it was not used"

    def test_moves_token_and_removes_original(self, config_dir, monkeypatch, tmp_path):
        legacy = tmp_path / "legacy.json"
        legacy.write_text('{"access_token": "abc", "access_token_secret": "xyz"}')
        monkeypatch.setattr(paths, "legacy_token_file", lambda: legacy)

        destination = paths.token_file()
        assert paths.migrate_legacy_token(destination) == legacy
        assert json.loads(destination.read_text())["access_token"] == "abc"
        assert not legacy.exists()

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
    def test_migrated_token_is_owner_only(self, config_dir, monkeypatch, tmp_path):
        legacy = tmp_path / "legacy.json"
        legacy.write_text('{"access_token": "abc"}')
        os.chmod(legacy, 0o644)
        monkeypatch.setattr(paths, "legacy_token_file", lambda: legacy)

        destination = paths.token_file()
        paths.migrate_legacy_token(destination)
        assert stat.S_IMODE(destination.stat().st_mode) == 0o600


class TestRestrictPermissions:
    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
    def test_file_becomes_owner_only(self, tmp_path):
        target = tmp_path / "token.json"
        target.write_text("{}")
        os.chmod(target, 0o644)
        paths.restrict_permissions(target)
        assert stat.S_IMODE(target.stat().st_mode) == 0o600

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX permissions")
    def test_directory_becomes_owner_only(self, tmp_path):
        target = tmp_path / "cfg"
        target.mkdir(mode=0o755)
        paths.restrict_permissions(target)
        assert stat.S_IMODE(target.stat().st_mode) == 0o700

    def test_missing_path_is_ignored(self, tmp_path):
        paths.restrict_permissions(tmp_path / "does-not-exist")
