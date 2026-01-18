"""
OAuth 1.0a authentication module for MotorsportsReg API.

Implements the three-legged OAuth flow:
1. Request token retrieval
2. User authorization
3. Access token exchange
"""

import json
import os
import socket
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from requests_oauthlib import OAuth1Session

# Default callback port for local OAuth flow
DEFAULT_CALLBACK_PORT = 8089


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler that captures OAuth callback parameters."""

    oauth_verifier = None
    oauth_token = None

    def do_GET(self):
        """Handle GET request from OAuth callback."""
        # Parse the query string
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        # Log what we received for debugging
        print(f"\n  [Callback] Received request: {self.path}")

        # Ignore non-callback requests (favicon, root path, etc.)
        if not parsed.path.startswith("/callback"):
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            response = """
            <html>
            <head><title>Waiting...</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <p>Waiting for MotorsportsReg authorization callback...</p>
                <p>Please complete the authorization on motorsportreg.com</p>
            </body>
            </html>
            """
            self.wfile.write(response.encode())
            return

        print(f"  [Callback] OAuth parameters: {params}")

        # Extract OAuth parameters
        OAuthCallbackHandler.oauth_verifier = params.get("oauth_verifier", [None])[0]
        OAuthCallbackHandler.oauth_token = params.get("oauth_token", [None])[0]

        # Check for OAuth error response
        oauth_error = params.get("error", [None])[0]
        error_description = params.get("error_description", ["Unknown error"])[0]

        # Send response to browser
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        if OAuthCallbackHandler.oauth_verifier:
            response = """
            <html>
            <head><title>Authorization Successful</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: green;">Authorization Successful!</h1>
                <p>You can close this window and return to the terminal.</p>
                <p>Verification code received. The script will continue automatically.</p>
            </body>
            </html>
            """
        elif oauth_error:
            response = f"""
            <html>
            <head><title>Authorization Denied</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: red;">Authorization Denied</h1>
                <p>Error: {oauth_error}</p>
                <p>{error_description}</p>
            </body>
            </html>
            """
        else:
            response = f"""
            <html>
            <head><title>Authorization Issue</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h1 style="color: orange;">Missing Verification Code</h1>
                <p>Received callback but no oauth_verifier parameter.</p>
                <p>Parameters received: {params}</p>
            </body>
            </html>
            """

        self.wfile.write(response.encode())

    def log_message(self, format, *args):
        """Suppress HTTP server logging."""
        pass


class MSROAuth:
    """Handles OAuth 1.0a authentication with MotorsportsReg API."""

    REQUEST_TOKEN_URL = "/rest/tokens/request"
    AUTHORIZE_URL = "/index.cfm/event/oauth"  # MSR-specific OAuth authorization page
    ACCESS_TOKEN_URL = "/rest/tokens/access"
    ME_URL = "/rest/me.json"  # Use .json suffix for JSON response

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        base_url: str = "https://api.motorsportreg.com",
        callback_url: Optional[str] = None,
        callback_port: int = DEFAULT_CALLBACK_PORT,
        token_file: Optional[str] = None,
    ):
        """
        Initialize the OAuth handler.

        Args:
            consumer_key: OAuth consumer key from MotorsportsReg
            consumer_secret: OAuth consumer secret from MotorsportsReg
            base_url: API base URL
            callback_url: OAuth callback URL (defaults to localhost)
            callback_port: Port for local callback server
            token_file: Path to store/load access tokens
        """
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.base_url = base_url.rstrip("/")
        self.callback_port = callback_port
        self.callback_url = callback_url or f"http://localhost:{callback_port}/callback"

        # Token storage
        if token_file is None:
            project_root = Path(__file__).parent.parent.parent
            self.token_file = project_root / "tokens" / "access_token.json"
        else:
            self.token_file = Path(token_file)

        # OAuth tokens (populated during auth flow)
        self.request_token = None
        self.request_token_secret = None
        self.access_token = None
        self.access_token_secret = None
        self.profile_id: Optional[str] = None
        self.organizations: List[Dict[str, Any]] = []

        # Try to load existing tokens
        self._load_tokens()

    def _load_tokens(self) -> bool:
        """
        Load access tokens from file if they exist.

        Returns:
            True if tokens were loaded successfully, False otherwise
        """
        if not self.token_file.exists():
            return False

        try:
            with open(self.token_file, "r") as f:
                data = json.load(f)
                self.access_token = data.get("access_token")
                self.access_token_secret = data.get("access_token_secret")
                self.profile_id = data.get("profile_id")
                self.organizations = data.get("organizations", [])

                if self.access_token and self.access_token_secret:
                    print(f"Loaded existing access tokens from {self.token_file}")
                    return True
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load tokens: {e}")

        return False

    def _save_tokens(self) -> None:
        """Save access tokens to file."""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "access_token": self.access_token,
            "access_token_secret": self.access_token_secret,
            "profile_id": self.profile_id,
            "organizations": self.organizations,
        }

        with open(self.token_file, "w") as f:
            json.dump(data, f, indent=2)

        print(f"Access tokens saved to {self.token_file}")

    def has_valid_tokens(self) -> bool:
        """Check if we have access tokens that might be valid."""
        return bool(self.access_token and self.access_token_secret)

    def get_request_token(self) -> Tuple[str, str]:
        """
        Step 1: Obtain a request token from MotorsportsReg.

        Returns:
            Tuple of (request_token, request_token_secret)

        Raises:
            Exception: If request token retrieval fails
        """
        print("\n[Step 1/3] Requesting temporary token...")

        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            callback_uri=self.callback_url,
        )

        url = f"{self.base_url}{self.REQUEST_TOKEN_URL}"
        response = oauth.fetch_request_token(url)

        self.request_token = response.get("oauth_token")
        self.request_token_secret = response.get("oauth_token_secret")

        if not self.request_token:
            raise Exception("Failed to obtain request token")

        print(f"  Request token obtained: {self.request_token[:20]}...")
        return self.request_token, self.request_token_secret

    def get_authorization_url(self) -> str:
        """
        Step 2: Generate the authorization URL for user to visit.

        Returns:
            URL string for user to authorize the application
        """
        if not self.request_token:
            raise Exception("Must obtain request token first")

        # MotorsportsReg uses the main site for authorization
        auth_base = "https://www.motorsportreg.com"
        auth_url = f"{auth_base}{self.AUTHORIZE_URL}?oauth_token={self.request_token}"

        print("\n[Step 2/3] User authorization required")
        print("-" * 60)
        print("Please visit this URL to authorize the application:")
        print(f"\n  {auth_url}\n")
        print("-" * 60)

        return auth_url

    def get_access_token(self, verifier: str) -> dict:
        """
        Step 3: Exchange request token for access token.

        Args:
            verifier: The oauth_verifier code from authorization

        Returns:
            Dict containing access_token, access_token_secret, profile_id

        Raises:
            Exception: If access token exchange fails
        """
        print("\n[Step 3/3] Exchanging for access token...")

        oauth = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.request_token,
            resource_owner_secret=self.request_token_secret,
            verifier=verifier,
        )

        url = f"{self.base_url}{self.ACCESS_TOKEN_URL}"
        response = oauth.fetch_access_token(url)

        self.access_token = response.get("oauth_token")
        self.access_token_secret = response.get("oauth_token_secret")
        self.profile_id = response.get("userid") or response.get("profile_id")

        if not self.access_token:
            raise Exception("Failed to obtain access token")

        print(f"  Access token obtained: {self.access_token[:20]}...")
        if self.profile_id:
            print(f"  Profile ID: {self.profile_id}")

        # Save tokens for future use
        self._save_tokens()

        return {
            "access_token": self.access_token,
            "access_token_secret": self.access_token_secret,
            "profile_id": self.profile_id,
        }

    def get_oauth_session(self) -> OAuth1Session:
        """
        Get an authenticated OAuth1Session for making API requests.

        Returns:
            Configured OAuth1Session instance

        Raises:
            Exception: If no valid access tokens available
        """
        if not self.has_valid_tokens():
            raise Exception("No valid access tokens. Please authenticate first.")

        session = OAuth1Session(
            self.consumer_key,
            client_secret=self.consumer_secret,
            resource_owner_key=self.access_token,
            resource_owner_secret=self.access_token_secret,
        )

        # Set default headers to request JSON responses
        session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        return session

    def validate_connection(self) -> Dict[str, Any]:
        """
        Validate the OAuth connection by calling /rest/me endpoint.

        Returns:
            User profile data including organizations

        Raises:
            Exception: If validation fails
        """
        print("\nValidating connection...")

        session = self.get_oauth_session()
        url = f"{self.base_url}{self.ME_URL}"

        response = session.get(url)

        if response.status_code == 401:
            # Tokens are invalid, clear them
            self.access_token = None
            self.access_token_secret = None
            if self.token_file.exists():
                self.token_file.unlink()
            raise Exception("Authentication failed - tokens are invalid or expired")

        response.raise_for_status()

        data = response.json()

        # MSR wraps responses in {"response": {"profile": {...}}}
        if "response" in data:
            data = data["response"]
        if "profile" in data:
            profile_data = data["profile"]
        else:
            profile_data = data

        # Extract organization info
        self.organizations = profile_data.get("organizations", [])

        # Update saved tokens with organization info
        self._save_tokens()

        return profile_data

    def _start_callback_server(self) -> HTTPServer:
        """Start a local HTTP server to receive the OAuth callback."""
        # Reset handler state
        OAuthCallbackHandler.oauth_verifier = None
        OAuthCallbackHandler.oauth_token = None

        server = HTTPServer(("localhost", self.callback_port), OAuthCallbackHandler)
        server.timeout = 300  # 5 minute timeout

        return server

    def _wait_for_callback(self, server: HTTPServer, max_requests: int = 10) -> str:
        """Wait for the OAuth callback and return the verifier."""
        print(f"\nWaiting for authorization callback on port {self.callback_port}...")
        print("(Press Ctrl+C to cancel)\n")

        # Handle multiple requests (browser may make favicon/other requests)
        for _ in range(max_requests):
            server.handle_request()

            verifier = OAuthCallbackHandler.oauth_verifier
            if verifier:
                return verifier

        raise Exception(
            "No verification code received from callback. "
            "Please ensure you complete the authorization on motorsportreg.com"
        )

    def run_auth_flow(self, auto_open_browser: bool = True) -> dict:
        """
        Run the complete OAuth authentication flow interactively.

        Args:
            auto_open_browser: Automatically open authorization URL in browser

        Returns:
            User profile data from /rest/me

        Raises:
            Exception: If any step of the auth flow fails
        """
        print("=" * 60)
        print("MotorsportsReg OAuth 1.0a Authentication")
        print("=" * 60)

        # Check for existing valid tokens
        if self.has_valid_tokens():
            print("\nFound existing access tokens. Validating...")
            try:
                profile = self.validate_connection()
                print("\n[OK] Connection validated successfully!")
                return profile
            except Exception as e:
                print(f"\nExisting tokens invalid: {e}")
                print("Starting fresh authentication flow...")

        # Start callback server before requesting token
        server = self._start_callback_server()

        try:
            # Step 1: Get request token
            self.get_request_token()

            # Step 2: Get authorization URL
            auth_url = self.get_authorization_url()

            # Open browser automatically if requested
            if auto_open_browser:
                print("\n" + "!" * 60)
                print("IMPORTANT: Copy and paste this URL into your browser:")
                print(f"\n  {auth_url}\n")
                print("!" * 60)
                print("\nAttempting to open browser automatically...")
                try:
                    webbrowser.open(auth_url)
                except Exception as e:
                    print(f"  Could not open browser automatically: {e}")
                print("\nIf the wrong page opens, manually navigate to the URL above.")
            else:
                print("\nPlease open the URL above in your browser.")

            # Step 3: Wait for callback with verifier
            verifier = self._wait_for_callback(server)
            print(f"\n  Received verifier: {verifier[:20]}...")

            # Step 4: Exchange for access token
            self.get_access_token(verifier)

            # Validate the new tokens
            profile = self.validate_connection()

            print("\n" + "=" * 60)
            print("[OK] Authentication successful!")
            print("=" * 60)

            return profile

        finally:
            server.server_close()


def create_oauth_from_env() -> MSROAuth:
    """
    Create an MSROAuth instance using credentials from keyring or environment.

    Credential sources (in priority order):
        1. System keyring (if available and configured)
        2. Environment variables (MSR_CONSUMER_KEY, MSR_CONSUMER_SECRET)

    Other environment variables:
        MSR_BASE_URL: API base URL (optional)
        MSR_CALLBACK_URL: OAuth callback URL (optional, defaults to localhost)
        MSR_CALLBACK_PORT: Port for callback server (optional, default 8089)

    Returns:
        Configured MSROAuth instance

    Raises:
        ValueError: If credentials cannot be found from any source
    """
    # Import credential manager to get credentials from keyring or env
    from hpde_analytics_cli.auth.credentials import CredentialManager

    credential_manager = CredentialManager()

    try:
        consumer_key, consumer_secret = credential_manager.get_credentials()
    except ValueError:
        raise ValueError(
            "No credentials found. Run with --configure to set up credentials, "
            "or set MSR_CONSUMER_KEY and MSR_CONSUMER_SECRET environment variables."
        )

    base_url = os.getenv("MSR_BASE_URL", "https://api.motorsportreg.com")
    callback_url = os.getenv("MSR_CALLBACK_URL")  # None = use localhost default
    callback_port = int(os.getenv("MSR_CALLBACK_PORT", str(DEFAULT_CALLBACK_PORT)))

    return MSROAuth(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        base_url=base_url,
        callback_url=callback_url,
        callback_port=callback_port,
    )
