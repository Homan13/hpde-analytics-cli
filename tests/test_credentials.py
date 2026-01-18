"""
Tests for the credentials module.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from hpde_analytics_cli.auth.credentials import (
    APP_NAME,
    KEY_CONSUMER_KEY,
    KEY_CONSUMER_SECRET,
    CredentialManager,
    get_credential_manager,
)


class TestCredentialManager:
    """Tests for CredentialManager class."""

    def test_init_default_app_name(self):
        """Test initialization with default app name."""
        manager = CredentialManager()
        assert manager.app_name == APP_NAME

    def test_init_custom_app_name(self):
        """Test initialization with custom app name."""
        manager = CredentialManager(app_name="custom-app")
        assert manager.app_name == "custom-app"

    def test_get_credentials_from_env_success(self):
        """Test retrieving credentials from environment variables."""
        manager = CredentialManager()

        with patch.dict(
            os.environ, {"MSR_CONSUMER_KEY": "test_key", "MSR_CONSUMER_SECRET": "test_secret"}
        ):
            key, secret = manager.get_credentials_from_env()
            assert key == "test_key"
            assert secret == "test_secret"

    def test_get_credentials_from_env_missing(self):
        """Test retrieving credentials when env vars are not set."""
        manager = CredentialManager()

        with patch.dict(os.environ, {}, clear=True):
            # Remove the keys if they exist
            os.environ.pop("MSR_CONSUMER_KEY", None)
            os.environ.pop("MSR_CONSUMER_SECRET", None)

            key, secret = manager.get_credentials_from_env()
            assert key is None
            assert secret is None

    def test_get_credentials_from_env_partial(self):
        """Test retrieving credentials when only one env var is set."""
        manager = CredentialManager()

        with patch.dict(os.environ, {"MSR_CONSUMER_KEY": "test_key"}, clear=True):
            os.environ.pop("MSR_CONSUMER_SECRET", None)
            key, secret = manager.get_credentials_from_env()
            assert key == "test_key"
            assert secret is None

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", False)
    def test_keyring_available_when_not_installed(self):
        """Test keyring_available returns False when keyring is not installed."""
        manager = CredentialManager()
        assert manager.keyring_available() is False

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", True)
    @patch("hpde_analytics_cli.auth.credentials.keyring")
    def test_keyring_available_when_working(self, mock_keyring):
        """Test keyring_available returns True when keyring works."""
        mock_keyring.get_password.return_value = None
        manager = CredentialManager()
        assert manager.keyring_available() is True

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", True)
    @patch("hpde_analytics_cli.auth.credentials.keyring")
    def test_keyring_available_when_failing(self, mock_keyring):
        """Test keyring_available returns False when keyring raises exception."""
        mock_keyring.get_password.side_effect = Exception("Backend not available")
        manager = CredentialManager()
        assert manager.keyring_available() is False

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", True)
    @patch("hpde_analytics_cli.auth.credentials.keyring")
    def test_get_credentials_from_keyring_success(self, mock_keyring):
        """Test retrieving credentials from keyring."""
        mock_keyring.get_password.side_effect = lambda app, key: {
            KEY_CONSUMER_KEY: "keyring_key",
            KEY_CONSUMER_SECRET: "keyring_secret",
        }.get(key)

        manager = CredentialManager()
        key, secret = manager.get_credentials_from_keyring()
        assert key == "keyring_key"
        assert secret == "keyring_secret"

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", False)
    def test_get_credentials_from_keyring_not_available(self):
        """Test keyring credentials when keyring not available."""
        manager = CredentialManager()
        key, secret = manager.get_credentials_from_keyring()
        assert key is None
        assert secret is None

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", True)
    @patch("hpde_analytics_cli.auth.credentials.keyring")
    def test_get_credentials_priority_keyring_first(self, mock_keyring):
        """Test that keyring credentials take priority over env vars."""
        mock_keyring.get_password.side_effect = lambda app, key: {
            KEY_CONSUMER_KEY: "keyring_key",
            KEY_CONSUMER_SECRET: "keyring_secret",
        }.get(key)

        manager = CredentialManager()

        with patch.dict(
            os.environ, {"MSR_CONSUMER_KEY": "env_key", "MSR_CONSUMER_SECRET": "env_secret"}
        ):
            key, secret = manager.get_credentials()
            assert key == "keyring_key"
            assert secret == "keyring_secret"

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", False)
    def test_get_credentials_fallback_to_env(self):
        """Test that env vars are used when keyring not available."""
        manager = CredentialManager()

        with patch.dict(
            os.environ, {"MSR_CONSUMER_KEY": "env_key", "MSR_CONSUMER_SECRET": "env_secret"}
        ):
            key, secret = manager.get_credentials()
            assert key == "env_key"
            assert secret == "env_secret"

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", False)
    def test_get_credentials_raises_when_none_found(self):
        """Test that ValueError is raised when no credentials found."""
        manager = CredentialManager()

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MSR_CONSUMER_KEY", None)
            os.environ.pop("MSR_CONSUMER_SECRET", None)

            with pytest.raises(ValueError) as exc_info:
                manager.get_credentials()

            assert "No credentials found" in str(exc_info.value)

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", True)
    @patch("hpde_analytics_cli.auth.credentials.keyring")
    def test_store_credentials_success(self, mock_keyring):
        """Test storing credentials in keyring."""
        mock_keyring.get_password.return_value = None  # For keyring_available check

        manager = CredentialManager()
        result = manager.store_credentials("new_key", "new_secret")

        assert result is True
        assert mock_keyring.set_password.call_count == 2

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", False)
    def test_store_credentials_keyring_not_available(self, capsys):
        """Test storing credentials when keyring not available."""
        manager = CredentialManager()
        result = manager.store_credentials("key", "secret")

        assert result is False
        captured = capsys.readouterr()
        assert "keyring not available" in captured.out.lower()

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", True)
    @patch("hpde_analytics_cli.auth.credentials.keyring")
    def test_delete_credentials_success(self, mock_keyring):
        """Test deleting credentials from keyring."""
        mock_keyring.get_password.return_value = None  # For keyring_available check

        manager = CredentialManager()
        result = manager.delete_credentials()

        assert result is True
        assert mock_keyring.delete_password.call_count == 2

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", False)
    def test_delete_credentials_keyring_not_available(self):
        """Test deleting credentials when keyring not available."""
        manager = CredentialManager()
        result = manager.delete_credentials()
        assert result is False

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", True)
    @patch("hpde_analytics_cli.auth.credentials.keyring")
    def test_has_stored_credentials_true(self, mock_keyring):
        """Test has_stored_credentials returns True when credentials exist."""
        mock_keyring.get_password.side_effect = lambda app, key: {
            KEY_CONSUMER_KEY: "key",
            KEY_CONSUMER_SECRET: "secret",
        }.get(key)

        manager = CredentialManager()
        assert manager.has_stored_credentials() is True

    @patch("hpde_analytics_cli.auth.credentials.KEYRING_AVAILABLE", True)
    @patch("hpde_analytics_cli.auth.credentials.keyring")
    def test_has_stored_credentials_false(self, mock_keyring):
        """Test has_stored_credentials returns False when credentials don't exist."""
        mock_keyring.get_password.return_value = None

        manager = CredentialManager()
        assert manager.has_stored_credentials() is False


class TestGetCredentialManager:
    """Tests for get_credential_manager function."""

    def test_returns_credential_manager_instance(self):
        """Test that get_credential_manager returns a CredentialManager instance."""
        manager = get_credential_manager()
        assert isinstance(manager, CredentialManager)
        assert manager.app_name == APP_NAME
