"""
MotorsportsReg API client module.

Provides a high-level interface for accessing MotorsportsReg API endpoints.
"""

import time
from typing import Any, Dict, Optional

from requests_oauthlib import OAuth1Session

from hpde_analytics_cli.auth.oauth import MSROAuth


class APIError(Exception):
    """Exception raised for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class MSRClient:
    """Client for interacting with MotorsportsReg API endpoints."""

    def __init__(self, oauth: MSROAuth, organization_id: Optional[str] = None):
        """
        Initialize the API client.

        Args:
            oauth: Authenticated MSROAuth instance
            organization_id: Organization ID for admin API access (optional)
        """
        self.oauth = oauth
        self.base_url = oauth.base_url
        self.organization_id = organization_id

        # Retry configuration
        self.max_retries = 3
        self.retry_delay = 1.0  # seconds

    def _get_session(self) -> OAuth1Session:
        """Get an authenticated OAuth session."""
        return self.oauth.get_oauth_session()

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        include_org_header: bool = True,
        retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Make an authenticated API request.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path (e.g., /rest/me.json)
            params: Query parameters
            include_org_header: Include X-Organization-Id header
            retries: Number of retries (defaults to self.max_retries)

        Returns:
            Parsed JSON response (unwrapped from MSR response envelope)

        Raises:
            APIError: If the request fails
        """
        if retries is None:
            retries = self.max_retries

        session = self._get_session()

        # Ensure endpoint has .json suffix for JSON response
        if not endpoint.endswith(".json"):
            endpoint = endpoint + ".json"

        url = f"{self.base_url}{endpoint}"

        headers = {}
        if include_org_header and self.organization_id:
            headers["X-Organization-Id"] = self.organization_id

        last_error: APIError = APIError("Request failed with unknown error")

        for attempt in range(retries + 1):
            try:
                if method.upper() == "GET":
                    response = session.get(url, params=params, headers=headers)
                elif method.upper() == "POST":
                    response = session.post(url, data=params, headers=headers)
                else:
                    raise APIError(f"Unsupported HTTP method: {method}")

                # Handle response
                if response.status_code == 200:
                    data = response.json()
                    # MSR wraps responses in {"response": {...}}
                    if isinstance(data, dict) and "response" in data:
                        data = data["response"]
                    return data
                elif response.status_code == 401:
                    raise APIError(
                        "Authentication failed - tokens may be invalid or expired",
                        status_code=401,
                        response_body=response.text,
                    )
                elif response.status_code == 403:
                    raise APIError(
                        "Access forbidden - insufficient permissions",
                        status_code=403,
                        response_body=response.text,
                    )
                elif response.status_code == 404:
                    raise APIError(
                        f"Resource not found: {endpoint}",
                        status_code=404,
                        response_body=response.text,
                    )
                elif response.status_code >= 500:
                    # Server error - retry
                    last_error = APIError(
                        f"Server error: {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text,
                    )
                    if attempt < retries:
                        time.sleep(self.retry_delay * (attempt + 1))
                        continue
                    raise last_error
                else:
                    raise APIError(
                        f"Request failed with status {response.status_code}",
                        status_code=response.status_code,
                        response_body=response.text,
                    )

            except APIError:
                raise
            except Exception as e:
                last_error = APIError(f"Request failed: {str(e)}")
                if attempt < retries:
                    time.sleep(self.retry_delay * (attempt + 1))
                    continue
                raise last_error

        raise last_error

    def get_me(self) -> Dict[str, Any]:
        """
        Get the authenticated user's profile.

        Returns:
            User profile data including organizations
        """
        return self._request("GET", "/rest/me", include_org_header=False)

    def get_organization_calendar(self, organization_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the organization's event calendar.

        Args:
            organization_id: Organization ID (uses default if not provided)

        Returns:
            Calendar data with list of events

        Endpoint: GET /rest/calendars/organization/{organization_id}
        """
        org_id = organization_id or self.organization_id
        if not org_id:
            raise ValueError("Organization ID is required")

        return self._request("GET", f"/rest/calendars/organization/{org_id}")

    def get_event_entrylist(self, event_id: str) -> Dict[str, Any]:
        """
        Get the entry list for an event.

        Args:
            event_id: Event ID

        Returns:
            Entry list data

        Endpoint: GET /rest/events/{event_id}/entrylist
        """
        if not event_id:
            raise ValueError("Event ID is required")

        return self._request("GET", f"/rest/events/{event_id}/entrylist")

    def get_event_attendees(self, event_id: str) -> Dict[str, Any]:
        """
        Get complete attendee list for an event.

        Args:
            event_id: Event ID

        Returns:
            Attendee data

        Endpoint: GET /rest/events/{event_id}/attendees
        """
        if not event_id:
            raise ValueError("Event ID is required")

        return self._request("GET", f"/rest/events/{event_id}/attendees")

    def get_event_assignments(self, event_id: str) -> Dict[str, Any]:
        """
        Get event assignments/entries including vehicle information.

        Args:
            event_id: Event ID

        Returns:
            Assignment data with vehicle details

        Endpoint: GET /rest/events/{event_id}/assignments
        """
        if not event_id:
            raise ValueError("Event ID is required")

        return self._request("GET", f"/rest/events/{event_id}/assignments")

    def get_timing_feed(self, event_id: str) -> Dict[str, Any]:
        """
        Get timing and scoring feed for an event.

        Args:
            event_id: Event ID

        Returns:
            Timing/scoring data

        Endpoint: GET /rest/events/{event_id}/feeds/timing
        """
        if not event_id:
            raise ValueError("Event ID is required")

        return self._request("GET", f"/rest/events/{event_id}/feeds/timing")

    def get_all_endpoint_data(self, event_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch data from all available endpoints for field discovery.

        Args:
            event_id: Optional event ID for event-specific endpoints

        Returns:
            Dict with data from each endpoint, keyed by endpoint name
        """
        results = {}

        # Always fetch user profile
        print("  Fetching /rest/me...")
        try:
            results["me"] = self.get_me()
            print("    [OK] User profile retrieved")
        except APIError as e:
            print(f"    [ERROR] {e}")
            results["me"] = {"error": str(e)}

        # Fetch organization calendar
        if self.organization_id:
            print(f"  Fetching organization calendar (org: {self.organization_id})...")
            try:
                results["calendar"] = self.get_organization_calendar()
                print("    [OK] Calendar retrieved")

                # Get first event ID if not provided
                if not event_id:
                    events = results["calendar"].get("events", [])
                    if events:
                        event_id = events[0].get("id")
                        print(f"    Using first event from calendar: {event_id}")
            except APIError as e:
                print(f"    [ERROR] {e}")
                results["calendar"] = {"error": str(e)}

        # Event-specific endpoints (require event_id)
        if event_id:
            event_endpoints = [
                ("entrylist", self.get_event_entrylist, "Entry list"),
                ("attendees", self.get_event_attendees, "Attendees"),
                ("assignments", self.get_event_assignments, "Assignments"),
                ("timing", self.get_timing_feed, "Timing feed"),
            ]

            for key, method, description in event_endpoints:
                print(f"  Fetching {description} (event: {event_id})...")
                try:
                    results[key] = method(event_id)
                    print(f"    [OK] {description} retrieved")
                except APIError as e:
                    print(f"    [ERROR] {e}")
                    results[key] = {"error": str(e)}
        else:
            print("  [SKIP] No event ID available - skipping event-specific endpoints")
            print("         Use --event-id to specify an event, or ensure calendar has events")

        return results


def create_client_from_oauth(oauth: MSROAuth, organization_id: Optional[str] = None) -> MSRClient:
    """
    Create an API client from an authenticated OAuth handler.

    Args:
        oauth: Authenticated MSROAuth instance
        organization_id: Optional organization ID override

    Returns:
        Configured MSRClient instance
    """
    # Use provided org ID, or fall back to first organization from profile
    if not organization_id and oauth.organizations:
        organization_id = oauth.organizations[0].get("id")

    return MSRClient(oauth=oauth, organization_id=organization_id)
