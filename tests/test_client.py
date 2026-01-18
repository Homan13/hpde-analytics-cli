"""
Tests for the API client module.
"""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from hpde_analytics_cli.api.client import (
    APIError,
    MSRClient,
    create_client_from_oauth,
)


class TestAPIError:
    """Tests for APIError exception."""

    def test_basic_error(self):
        """Test basic APIError creation."""
        error = APIError("Test error message")
        assert str(error) == "Test error message"
        assert error.status_code is None
        assert error.response_body is None

    def test_error_with_status_code(self):
        """Test APIError with status code."""
        error = APIError("Not found", status_code=404)
        assert error.status_code == 404

    def test_error_with_response_body(self):
        """Test APIError with response body."""
        error = APIError("Error", response_body='{"error": "details"}')
        assert error.response_body == '{"error": "details"}'


class TestMSRClient:
    """Tests for MSRClient class."""

    @pytest.fixture
    def mock_oauth(self):
        """Create a mock OAuth instance."""
        oauth = MagicMock()
        oauth.base_url = "https://api.motorsportreg.com"
        oauth.organizations = [{"id": "test-org-id", "name": "Test Org"}]
        return oauth

    @pytest.fixture
    def client(self, mock_oauth):
        """Create a client instance for testing."""
        return MSRClient(oauth=mock_oauth, organization_id="test-org-id")

    def test_init(self, mock_oauth):
        """Test client initialization."""
        client = MSRClient(oauth=mock_oauth, organization_id="org-123")
        assert client.base_url == "https://api.motorsportreg.com"
        assert client.organization_id == "org-123"
        assert client.max_retries == 3
        assert abs(client.retry_delay - 1.0) < 0.001  # Avoid direct float comparison

    def test_init_without_org_id(self, mock_oauth):
        """Test client initialization without organization ID."""
        client = MSRClient(oauth=mock_oauth)
        assert client.organization_id is None

    def test_get_session(self, client, mock_oauth):
        """Test getting OAuth session."""
        mock_session = MagicMock()
        mock_oauth.get_oauth_session.return_value = mock_session

        session = client._get_session()
        assert session == mock_session
        mock_oauth.get_oauth_session.assert_called_once()

    def test_request_adds_json_suffix(self, client, mock_oauth):
        """Test that .json suffix is added to endpoint."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"data": "test"}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        client._request("GET", "/rest/me")

        # Verify .json was added
        call_args = mock_session.get.call_args
        assert call_args[0][0].endswith(".json")

    def test_request_unwraps_response(self, client, mock_oauth):
        """Test that MSR response envelope is unwrapped."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"user": "data"}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        result = client._request("GET", "/rest/me.json")

        assert result == {"user": "data"}

    def test_request_includes_org_header(self, client, mock_oauth):
        """Test that X-Organization-Id header is included."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        client._request("GET", "/rest/endpoint.json", include_org_header=True)

        call_kwargs = mock_session.get.call_args[1]
        assert "X-Organization-Id" in call_kwargs["headers"]
        assert call_kwargs["headers"]["X-Organization-Id"] == "test-org-id"

    def test_request_excludes_org_header_when_disabled(self, client, mock_oauth):
        """Test that X-Organization-Id header can be excluded."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        client._request("GET", "/rest/endpoint.json", include_org_header=False)

        call_kwargs = mock_session.get.call_args[1]
        assert "X-Organization-Id" not in call_kwargs["headers"]

    def test_request_handles_401_error(self, client, mock_oauth):
        """Test handling of 401 authentication error."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        with pytest.raises(APIError) as exc_info:
            client._request("GET", "/rest/me.json")

        assert exc_info.value.status_code == 401
        assert "Authentication failed" in str(exc_info.value)

    def test_request_handles_403_error(self, client, mock_oauth):
        """Test handling of 403 forbidden error."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.text = "Forbidden"
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        with pytest.raises(APIError) as exc_info:
            client._request("GET", "/rest/me.json")

        assert exc_info.value.status_code == 403
        assert "forbidden" in str(exc_info.value).lower()

    def test_request_handles_404_error(self, client, mock_oauth):
        """Test handling of 404 not found error."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        with pytest.raises(APIError) as exc_info:
            client._request("GET", "/rest/me.json")

        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value).lower()

    def test_request_unsupported_method(self, client, mock_oauth):
        """Test handling of unsupported HTTP method."""
        mock_session = MagicMock()
        mock_oauth.get_oauth_session.return_value = mock_session

        with pytest.raises(APIError) as exc_info:
            client._request("DELETE", "/rest/me.json")

        assert "Unsupported HTTP method" in str(exc_info.value)

    def test_get_me(self, client, mock_oauth):
        """Test get_me method."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"firstName": "Test", "lastName": "User"}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        result = client.get_me()

        assert result == {"firstName": "Test", "lastName": "User"}

    def test_get_organization_calendar(self, client, mock_oauth):
        """Test get_organization_calendar method."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"events": [{"id": "event-1"}]}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        result = client.get_organization_calendar()

        assert "events" in result
        assert len(result["events"]) == 1

    def test_get_organization_calendar_requires_org_id(self, mock_oauth):
        """Test that get_organization_calendar requires organization ID."""
        client = MSRClient(oauth=mock_oauth, organization_id=None)

        with pytest.raises(ValueError) as exc_info:
            client.get_organization_calendar()

        assert "Organization ID is required" in str(exc_info.value)

    def test_get_event_entrylist(self, client, mock_oauth):
        """Test get_event_entrylist method."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"assignments": [{"id": "entry-1"}]}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        result = client.get_event_entrylist("event-123")

        assert "assignments" in result

    def test_get_event_entrylist_requires_event_id(self, client):
        """Test that get_event_entrylist requires event ID."""
        with pytest.raises(ValueError) as exc_info:
            client.get_event_entrylist("")

        assert "Event ID is required" in str(exc_info.value)

    def test_get_event_attendees(self, client, mock_oauth):
        """Test get_event_attendees method."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"attendees": [{"id": "attendee-1"}]}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        result = client.get_event_attendees("event-123")

        assert "attendees" in result

    def test_get_event_attendees_requires_event_id(self, client):
        """Test that get_event_attendees requires event ID."""
        with pytest.raises(ValueError) as exc_info:
            client.get_event_attendees(None)

        assert "Event ID is required" in str(exc_info.value)

    def test_get_event_assignments(self, client, mock_oauth):
        """Test get_event_assignments method."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"assignments": [{"id": "assignment-1"}]}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        result = client.get_event_assignments("event-123")

        assert "assignments" in result

    def test_get_timing_feed(self, client, mock_oauth):
        """Test get_timing_feed method."""
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": {"timing": []}}
        mock_session.get.return_value = mock_response
        mock_oauth.get_oauth_session.return_value = mock_session

        result = client.get_timing_feed("event-123")

        assert "timing" in result


class TestCreateClientFromOAuth:
    """Tests for create_client_from_oauth function."""

    def test_creates_client_with_provided_org_id(self):
        """Test creating client with provided organization ID."""
        mock_oauth = MagicMock()
        mock_oauth.base_url = "https://api.motorsportreg.com"
        mock_oauth.organizations = [{"id": "default-org"}]

        client = create_client_from_oauth(mock_oauth, organization_id="custom-org")

        assert client.organization_id == "custom-org"

    def test_uses_first_organization_as_default(self):
        """Test that first organization is used when no org ID provided."""
        mock_oauth = MagicMock()
        mock_oauth.base_url = "https://api.motorsportreg.com"
        mock_oauth.organizations = [
            {"id": "org-1", "name": "First Org"},
            {"id": "org-2", "name": "Second Org"},
        ]

        client = create_client_from_oauth(mock_oauth)

        assert client.organization_id == "org-1"

    def test_handles_empty_organizations(self):
        """Test handling when no organizations available."""
        mock_oauth = MagicMock()
        mock_oauth.base_url = "https://api.motorsportreg.com"
        mock_oauth.organizations = []

        client = create_client_from_oauth(mock_oauth)

        assert client.organization_id is None
