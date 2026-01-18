"""
Credential Manager Module

Securely stores and retrieves OAuth credentials using the system keyring.
Falls back to environment variables/.env file if keyring is unavailable.
"""

import getpass
import os
from typing import Optional, Tuple

# Application identifier for keyring storage
APP_NAME = "hpde-analytics-cli"

# Credential keys
KEY_CONSUMER_KEY = "msr_consumer_key"
KEY_CONSUMER_SECRET = "msr_consumer_secret"

# Try to import keyring, but don't fail if unavailable
try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False


class CredentialManager:
    """
    Manages OAuth credentials with secure storage.

    Priority order for credential retrieval:
    1. System keyring (if available and credentials stored)
    2. Environment variables
    3. Interactive prompt (for --configure)
    """

    def __init__(self, app_name: str = APP_NAME):
        """
        Initialize the credential manager.

        Args:
            app_name: Application identifier for keyring storage
        """
        self.app_name = app_name

    def keyring_available(self) -> bool:
        """Check if keyring is available and functional."""
        if not KEYRING_AVAILABLE:
            return False

        # Test if keyring backend is actually working
        try:
            # Try to get a non-existent key to test functionality
            keyring.get_password(self.app_name, "__test__")
            return True
        except Exception:
            return False

    def get_credentials_from_keyring(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Retrieve credentials from system keyring.

        Returns:
            Tuple of (consumer_key, consumer_secret) or (None, None) if not found
        """
        if not self.keyring_available():
            return None, None

        try:
            consumer_key = keyring.get_password(self.app_name, KEY_CONSUMER_KEY)
            consumer_secret = keyring.get_password(self.app_name, KEY_CONSUMER_SECRET)
            return consumer_key, consumer_secret
        except Exception:
            return None, None

    def get_credentials_from_env(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Retrieve credentials from environment variables.

        Returns:
            Tuple of (consumer_key, consumer_secret) or (None, None) if not found
        """
        consumer_key = os.environ.get("MSR_CONSUMER_KEY")
        consumer_secret = os.environ.get("MSR_CONSUMER_SECRET")
        return consumer_key, consumer_secret

    def get_credentials(self) -> Tuple[str, str]:
        """
        Get credentials from the best available source.

        Priority:
        1. System keyring
        2. Environment variables

        Returns:
            Tuple of (consumer_key, consumer_secret)

        Raises:
            ValueError: If credentials cannot be found from any source
        """
        # Try keyring first
        consumer_key, consumer_secret = self.get_credentials_from_keyring()
        if consumer_key and consumer_secret:
            return consumer_key, consumer_secret

        # Fall back to environment variables
        consumer_key, consumer_secret = self.get_credentials_from_env()
        if consumer_key and consumer_secret:
            return consumer_key, consumer_secret

        # No credentials found
        raise ValueError(
            "No credentials found. Run with --configure to set up credentials, "
            "or set MSR_CONSUMER_KEY and MSR_CONSUMER_SECRET environment variables."
        )

    def store_credentials(self, consumer_key: str, consumer_secret: str) -> bool:
        """
        Store credentials in system keyring.

        Args:
            consumer_key: OAuth consumer key
            consumer_secret: OAuth consumer secret

        Returns:
            True if stored successfully, False otherwise
        """
        if not self.keyring_available():
            print("Warning: System keyring not available. Cannot store credentials securely.")
            return False

        try:
            keyring.set_password(self.app_name, KEY_CONSUMER_KEY, consumer_key)
            keyring.set_password(self.app_name, KEY_CONSUMER_SECRET, consumer_secret)
            return True
        except Exception as e:
            print(f"Warning: Failed to store credentials in keyring: {e}")
            return False

    def delete_credentials(self) -> bool:
        """
        Delete credentials from system keyring.

        Returns:
            True if deleted successfully, False otherwise
        """
        if not self.keyring_available():
            return False

        try:
            keyring.delete_password(self.app_name, KEY_CONSUMER_KEY)
            keyring.delete_password(self.app_name, KEY_CONSUMER_SECRET)
            return True
        except Exception:
            return False

    def has_stored_credentials(self) -> bool:
        """
        Check if credentials are stored in keyring.

        Returns:
            True if credentials exist in keyring
        """
        consumer_key, consumer_secret = self.get_credentials_from_keyring()
        return bool(consumer_key and consumer_secret)

    def configure_interactive(self) -> bool:
        """
        Interactively configure credentials via command line prompts.

        Returns:
            True if configuration successful
        """
        print("\n" + "=" * 60)
        print("HPDE Analytics - Credential Configuration")
        print("=" * 60)

        if not self.keyring_available():
            print("\nWarning: System keyring is not available.")
            print("Credentials will need to be set via environment variables.")
            print("\nTo use environment variables, add to your .env file:")
            print("  MSR_CONSUMER_KEY=your_key_here")
            print("  MSR_CONSUMER_SECRET=your_secret_here")
            return False

        print("\nThis will store your MotorsportsReg OAuth credentials securely")
        print("in your system's credential manager (Keychain/Credential Locker).")

        # Check for existing credentials
        if self.has_stored_credentials():
            print("\nExisting credentials found in keyring.")
            response = input("Do you want to replace them? (y/N): ").strip().lower()
            if response != "y":
                print("Configuration cancelled.")
                return False

        print("\nEnter your MotorsportsReg OAuth credentials:")
        print("(These are provided by MotorsportsReg for API access)")
        print()

        # Get consumer key
        consumer_key = input("Consumer Key: ").strip()
        if not consumer_key:
            print("Error: Consumer key cannot be empty.")
            return False

        # Get consumer secret (hidden input)
        consumer_secret = getpass.getpass("Consumer Secret: ").strip()
        if not consumer_secret:
            print("Error: Consumer secret cannot be empty.")
            return False

        # Store credentials
        if self.store_credentials(consumer_key, consumer_secret):
            print("\n[OK] Credentials stored securely in system keyring.")
            print("     You can now run the application without environment variables.")
            return True
        else:
            print("\n[ERROR] Failed to store credentials.")
            return False

    def show_status(self) -> None:
        """Display current credential configuration status."""
        print("\n" + "=" * 60)
        print("Credential Status")
        print("=" * 60)

        # Check keyring availability
        print(f"\nSystem keyring available: {'Yes' if self.keyring_available() else 'No'}")

        # Check keyring credentials
        keyring_key, keyring_secret = self.get_credentials_from_keyring()
        has_keyring = bool(keyring_key and keyring_secret)
        print(f"Credentials in keyring: {'Yes' if has_keyring else 'No'}")

        # Check environment variables
        env_key, env_secret = self.get_credentials_from_env()
        has_env = bool(env_key and env_secret)
        print(f"Credentials in environment: {'Yes' if has_env else 'No'}")

        # Show which source will be used
        if has_keyring:
            print("\n[Active] Using credentials from system keyring")
        elif has_env:
            print("\n[Active] Using credentials from environment variables")
        else:
            print("\n[Warning] No credentials configured")
            print("          Run with --configure to set up credentials")

        print()


def get_credential_manager() -> CredentialManager:
    """Get a configured credential manager instance."""
    return CredentialManager()
