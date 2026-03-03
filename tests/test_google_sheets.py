"""
Tests for the Google Sheets client module.
"""

from unittest.mock import MagicMock, patch

import pytest

from hpde_analytics_cli.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsError


class TestGoogleSheetsClientInit:
    """Tests for GoogleSheetsClient initialization."""

    @patch("hpde_analytics_cli.integrations.google_sheets.GSPREAD_AVAILABLE", False)
    def test_init_raises_when_gspread_unavailable(self):
        """Should raise ImportError with install instructions when gspread is missing."""
        with pytest.raises(ImportError, match="gspread"):
            GoogleSheetsClient("/path/to/key.json")

    def test_init_stores_key_path(self):
        """Should store the service account key path."""
        client = GoogleSheetsClient("/path/to/key.json")
        assert client.key_path == "/path/to/key.json"
        assert client._client is None


class TestGoogleSheetsClientConnect:
    """Tests for the connect() method."""

    def test_connect_raises_when_key_file_missing(self, tmp_path):
        """Should raise GoogleSheetsError when the key file does not exist."""
        client = GoogleSheetsClient(str(tmp_path / "nonexistent.json"))
        with pytest.raises(GoogleSheetsError, match="not found"):
            client.connect()

    @patch("hpde_analytics_cli.integrations.google_sheets.gspread")
    def test_connect_calls_service_account(self, mock_gspread, tmp_path):
        """Should call gspread.service_account with the key path and scopes."""
        key_file = tmp_path / "key.json"
        key_file.write_text("{}")

        client = GoogleSheetsClient(str(key_file))
        client.connect()

        mock_gspread.service_account.assert_called_once_with(
            filename=str(key_file),
            scopes=GoogleSheetsClient.SCOPES,
        )

    @patch("hpde_analytics_cli.integrations.google_sheets.gspread")
    def test_connect_raises_on_auth_failure(self, mock_gspread, tmp_path):
        """Should raise GoogleSheetsError when gspread authentication fails."""
        key_file = tmp_path / "key.json"
        key_file.write_text("{}")
        mock_gspread.service_account.side_effect = Exception("auth failed")

        client = GoogleSheetsClient(str(key_file))
        with pytest.raises(GoogleSheetsError, match="Failed to authenticate"):
            client.connect()


class TestGoogleSheetsClientOpenSheet:
    """Tests for the open_sheet() method."""

    def test_open_sheet_raises_when_not_connected(self):
        """Should raise GoogleSheetsError if connect() was not called."""
        client = GoogleSheetsClient("/path/to/key.json")
        with pytest.raises(GoogleSheetsError, match="Not connected"):
            client.open_sheet("SHEET123")

    @patch("hpde_analytics_cli.integrations.google_sheets.gspread")
    def test_open_sheet_default_returns_sheet1(self, mock_gspread, tmp_path):
        """Should return sheet1 when no worksheet name is given."""
        key_file = tmp_path / "key.json"
        key_file.write_text("{}")

        mock_spreadsheet = MagicMock()
        mock_gspread.service_account.return_value.open_by_key.return_value = mock_spreadsheet

        client = GoogleSheetsClient(str(key_file))
        client.connect()
        client.open_sheet("SHEET123")

        mock_spreadsheet.sheet1.__class__  # accessed sheet1 attribute
        assert not mock_spreadsheet.worksheet.called

    @patch("hpde_analytics_cli.integrations.google_sheets.gspread")
    def test_open_sheet_named_worksheet(self, mock_gspread, tmp_path):
        """Should call worksheet() when a name is provided."""
        key_file = tmp_path / "key.json"
        key_file.write_text("{}")

        mock_spreadsheet = MagicMock()
        mock_gspread.service_account.return_value.open_by_key.return_value = mock_spreadsheet

        client = GoogleSheetsClient(str(key_file))
        client.connect()
        client.open_sheet("SHEET123", worksheet_name="Form Responses 1")

        mock_spreadsheet.worksheet.assert_called_once_with("Form Responses 1")

    @patch("hpde_analytics_cli.integrations.google_sheets.gspread")
    def test_open_sheet_raises_on_spreadsheet_not_found(self, mock_gspread, tmp_path):
        """Should raise GoogleSheetsError with sharing hint when sheet is not found."""
        key_file = tmp_path / "key.json"
        key_file.write_text("{}")

        mock_gspread.SpreadsheetNotFound = Exception
        mock_gspread.service_account.return_value.open_by_key.side_effect = (
            mock_gspread.SpreadsheetNotFound("not found")
        )

        client = GoogleSheetsClient(str(key_file))
        client.connect()
        with pytest.raises(GoogleSheetsError, match="shared with the service account"):
            client.open_sheet("BADID")

    @patch("hpde_analytics_cli.integrations.google_sheets.gspread")
    def test_open_sheet_raises_on_worksheet_not_found(self, mock_gspread, tmp_path):
        """Should raise GoogleSheetsError when the named worksheet does not exist."""
        key_file = tmp_path / "key.json"
        key_file.write_text("{}")

        mock_spreadsheet = MagicMock()
        mock_gspread.SpreadsheetNotFound = type("SpreadsheetNotFound", (Exception,), {})
        mock_gspread.WorksheetNotFound = type("WorksheetNotFound", (Exception,), {})
        mock_gspread.service_account.return_value.open_by_key.return_value = mock_spreadsheet
        mock_spreadsheet.worksheet.side_effect = mock_gspread.WorksheetNotFound("bad tab")

        client = GoogleSheetsClient(str(key_file))
        client.connect()
        with pytest.raises(GoogleSheetsError, match="Worksheet not found"):
            client.open_sheet("SHEET123", worksheet_name="Bad Tab")


class TestColLetterToIndex:
    """Tests for the _col_letter_to_index static method."""

    def test_single_letter_a(self):
        assert GoogleSheetsClient._col_letter_to_index("A") == 1

    def test_single_letter_c(self):
        assert GoogleSheetsClient._col_letter_to_index("C") == 3

    def test_single_letter_z(self):
        assert GoogleSheetsClient._col_letter_to_index("Z") == 26

    def test_double_letter_aa(self):
        assert GoogleSheetsClient._col_letter_to_index("AA") == 27

    def test_double_letter_lowercase(self):
        """_col_letter_to_index is case-insensitive internally."""
        assert GoogleSheetsClient._col_letter_to_index("b") == 2


class TestFindColumnIndex:
    """Tests for the find_column_index() method."""

    def test_find_by_column_letter(self):
        """An all-uppercase alphabetic identifier should be treated as a column letter."""
        client = GoogleSheetsClient.__new__(GoogleSheetsClient)
        mock_worksheet = MagicMock()
        assert client.find_column_index(mock_worksheet, "C") == 3
        mock_worksheet.row_values.assert_not_called()

    def test_find_by_header_text(self):
        """A non-letter identifier should be matched against header row values."""
        client = GoogleSheetsClient.__new__(GoogleSheetsClient)
        mock_worksheet = MagicMock()
        mock_worksheet.row_values.return_value = [
            "Timestamp",
            "Instructor",
            "Student Name",
            "Email",
        ]

        assert client.find_column_index(mock_worksheet, "Student Name") == 3

    def test_find_by_header_case_insensitive(self):
        """Header matching should be case insensitive."""
        client = GoogleSheetsClient.__new__(GoogleSheetsClient)
        mock_worksheet = MagicMock()
        mock_worksheet.row_values.return_value = ["name", "email"]

        assert client.find_column_index(mock_worksheet, "Name") == 1

    def test_find_by_header_not_found_raises(self):
        """Should raise GoogleSheetsError listing available headers."""
        client = GoogleSheetsClient.__new__(GoogleSheetsClient)
        mock_worksheet = MagicMock()
        mock_worksheet.row_values.return_value = ["name", "email"]

        with pytest.raises(GoogleSheetsError, match="Column not found"):
            client.find_column_index(mock_worksheet, "phone")


class TestBatchUpdateCells:
    """Tests for the batch_update_cells() method."""

    @patch("hpde_analytics_cli.integrations.google_sheets.gspread")
    def test_batch_update_writes_cells(self, mock_gspread):
        """Should create Cell objects and call update_cells once."""
        mock_cell_class = MagicMock()
        mock_gspread.Cell = mock_cell_class

        client = GoogleSheetsClient.__new__(GoogleSheetsClient)
        mock_worksheet = MagicMock()

        updates = [(2, 3, "alice@example.com"), (3, 3, "bob@example.com")]
        count = client.batch_update_cells(mock_worksheet, updates)

        assert count == 2
        assert mock_cell_class.call_count == 2
        mock_worksheet.update_cells.assert_called_once()

    def test_batch_update_empty_list_returns_zero(self):
        """Should return 0 and not call the API when there are no updates."""
        client = GoogleSheetsClient.__new__(GoogleSheetsClient)
        mock_worksheet = MagicMock()

        count = client.batch_update_cells(mock_worksheet, [])

        assert count == 0
        mock_worksheet.update_cells.assert_not_called()
