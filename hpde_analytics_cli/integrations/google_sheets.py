"""
Google Sheets Integration Client

Provides authenticated access to Google Sheets using a service account.
"""

import os
from typing import Any, List, Optional, Tuple

try:
    import gspread
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


class GoogleSheetsError(Exception):
    """Exception raised for Google Sheets errors."""

    pass


class GoogleSheetsClient:
    """Client for reading and writing Google Sheets data via a service account."""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.readonly",
    ]

    def __init__(self, service_account_key_path: str):
        """
        Initialize the client with a path to a service account JSON key file.

        Args:
            service_account_key_path: Filesystem path to the service account JSON file
        """
        if not GSPREAD_AVAILABLE:
            raise ImportError(
                "gspread is required for Google Sheets integration. "
                "Install with: pip install gspread google-auth"
            )
        self.key_path = service_account_key_path
        self._client: Any = None

    def connect(self) -> None:
        """Authenticate with Google and create the gspread client."""
        if not os.path.exists(self.key_path):
            raise GoogleSheetsError(f"Service account key file not found: {self.key_path}")
        try:
            self._client = gspread.service_account(
                filename=self.key_path,
                scopes=self.SCOPES,
            )
        except Exception as e:
            raise GoogleSheetsError(f"Failed to authenticate with Google: {e}")

    def open_sheet(self, sheet_id: str, worksheet_name: Optional[str] = None) -> Any:
        """
        Open a worksheet by spreadsheet ID and optional worksheet name.

        Args:
            sheet_id: The Google Sheet ID (from the URL)
            worksheet_name: Worksheet/tab name; defaults to the first sheet

        Returns:
            gspread Worksheet object
        """
        if not self._client:
            raise GoogleSheetsError("Not connected. Call connect() first.")
        try:
            spreadsheet = self._client.open_by_key(sheet_id)
            if worksheet_name:
                return spreadsheet.worksheet(worksheet_name)
            return spreadsheet.sheet1
        except gspread.SpreadsheetNotFound:
            raise GoogleSheetsError(
                f"Spreadsheet not found: {sheet_id}. "
                "Ensure the Sheet is shared with the service account email."
            )
        except gspread.WorksheetNotFound:
            raise GoogleSheetsError(f"Worksheet not found: {worksheet_name}")

    @staticmethod
    def _col_letter_to_index(letter: str) -> int:
        """
        Convert a column letter (A, B, ..., Z, AA, AB, ...) to a 1-based index.

        Args:
            letter: Column letter string (e.g., "A", "C", "AA")

        Returns:
            1-based column index
        """
        result = 0
        for char in letter.upper():
            result = result * 26 + (ord(char) - ord("A") + 1)
        return result

    def find_column_index(self, worksheet: Any, column_identifier: str) -> int:
        """
        Find a column's 1-based index by column letter or header text.

        Args:
            worksheet: gspread Worksheet object
            column_identifier: A column letter (e.g., "C") or header text (e.g., "email")

        Returns:
            1-based column index

        Raises:
            GoogleSheetsError: If the column cannot be found
        """
        # If the identifier is all-uppercase alpha (e.g., "A", "C", "AA"), treat as column letter
        if column_identifier.isalpha() and column_identifier.isupper():
            return self._col_letter_to_index(column_identifier)

        # Otherwise search row 1 for a matching header
        headers = worksheet.row_values(1)
        for i, header in enumerate(headers, 1):
            if header.strip().lower() == column_identifier.strip().lower():
                return i

        raise GoogleSheetsError(
            f"Column not found: '{column_identifier}'. " f"Available headers: {headers}"
        )

    def batch_update_cells(
        self,
        worksheet: Any,
        updates: List[Tuple[int, int, str]],
    ) -> int:
        """
        Write multiple cell values in a single API call.

        Args:
            worksheet: gspread Worksheet object
            updates: List of (row, col, value) tuples (1-based row/col)

        Returns:
            Number of cells updated
        """
        if not updates:
            return 0

        cells = [gspread.Cell(row, col, value) for row, col, value in updates]
        worksheet.update_cells(cells)
        return len(cells)
