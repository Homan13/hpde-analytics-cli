"""
Tests for the email populator module.
"""

import csv
import os
import tempfile
from unittest.mock import MagicMock

import pytest

from hpde_analytics_cli.integrations.email_populator import EmailPopulator, NameMatcher


class TestNameMatcher:
    """Tests for NameMatcher static methods."""

    def test_normalize_basic(self):
        """Test basic normalization."""
        assert NameMatcher.normalize("John Doe") == "john doe"

    def test_normalize_extra_whitespace(self):
        """Test that extra whitespace is collapsed."""
        assert NameMatcher.normalize("  John   Doe  ") == "john doe"

    def test_normalize_mixed_case(self):
        """Test that uppercase is lowercased."""
        assert NameMatcher.normalize("JOHN DOE") == "john doe"

    def test_normalize_empty_string(self):
        """Test normalization of empty string."""
        assert NameMatcher.normalize("") == ""

    def test_build_email_lookup_filters_by_group(self):
        """Only entries whose group contains the filter substring should be included."""
        entrylist = [
            {"firstName": "Alice", "lastName": "Novice", "group": "Novice HPDE"},
            {"firstName": "Bob", "lastName": "Advanced", "group": "Advanced HPDE"},
        ]
        attendees = [
            {"firstName": "Alice", "lastName": "Novice", "email": "alice@example.com"},
            {"firstName": "Bob", "lastName": "Advanced", "email": "bob@example.com"},
        ]
        lookup = NameMatcher.build_email_lookup(entrylist, attendees, "novice")
        assert "alice novice" in lookup
        assert "bob advanced" not in lookup

    def test_build_email_lookup_case_insensitive_group(self):
        """Group filter matching should be case insensitive."""
        entrylist = [
            {"firstName": "Alice", "lastName": "Smith", "group": "NOVICE HPDE"},
        ]
        attendees = [
            {"firstName": "Alice", "lastName": "Smith", "email": "alice@example.com"},
        ]
        lookup = NameMatcher.build_email_lookup(entrylist, attendees, "novice")
        assert "alice smith" in lookup

    def test_build_email_lookup_combines_first_last(self):
        """The lookup key should be 'firstname lastname' normalized."""
        entrylist = [
            {"firstName": "Nathan", "lastName": "Bushey", "group": "Novice HPDE"},
        ]
        attendees = [
            {"firstName": "Nathan", "lastName": "Bushey", "email": "nathan@example.com"},
        ]
        lookup = NameMatcher.build_email_lookup(entrylist, attendees, "novice")
        assert lookup.get("nathan bushey") == "nathan@example.com"

    def test_build_email_lookup_excludes_missing_email(self):
        """Attendees without an email address should not appear in the lookup."""
        entrylist = [
            {"firstName": "Alice", "lastName": "Smith", "group": "Novice HPDE"},
        ]
        attendees = [
            {"firstName": "Alice", "lastName": "Smith", "email": ""},
        ]
        lookup = NameMatcher.build_email_lookup(entrylist, attendees, "novice")
        assert "alice smith" not in lookup

    def test_build_email_lookup_excludes_missing_name(self):
        """Entrylist entries with missing first or last name should be skipped."""
        entrylist = [
            {"firstName": "", "lastName": "Smith", "group": "Novice HPDE"},
            {"firstName": "Alice", "lastName": "", "group": "Novice HPDE"},
        ]
        attendees = [
            {"firstName": "Alice", "lastName": "Smith", "email": "alice@example.com"},
        ]
        lookup = NameMatcher.build_email_lookup(entrylist, attendees, "novice")
        assert len(lookup) == 0

    def test_build_email_lookup_no_matching_group(self):
        """Empty lookup when no entries match the group filter."""
        entrylist = [
            {"firstName": "Alice", "lastName": "Smith", "group": "Advanced HPDE"},
        ]
        attendees = [
            {"firstName": "Alice", "lastName": "Smith", "email": "alice@example.com"},
        ]
        lookup = NameMatcher.build_email_lookup(entrylist, attendees, "novice")
        assert lookup == {}

    def test_match_name_exact(self):
        """Exact match after normalization should return the email."""
        lookup = {"john doe": "john@example.com"}
        assert NameMatcher.match_name("John Doe", lookup) == "john@example.com"

    def test_match_name_case_insensitive(self):
        """Match should work regardless of case."""
        lookup = {"john doe": "john@example.com"}
        assert NameMatcher.match_name("JOHN DOE", lookup) == "john@example.com"

    def test_match_name_extra_whitespace(self):
        """Match should work with extra whitespace in the Sheet name."""
        lookup = {"john doe": "john@example.com"}
        assert NameMatcher.match_name("  John   Doe  ", lookup) == "john@example.com"

    def test_match_name_no_match(self):
        """Returns None when the name is not in the lookup."""
        lookup = {"john doe": "john@example.com"}
        assert NameMatcher.match_name("Jane Smith", lookup) is None

    def test_match_name_empty_string(self):
        """Returns None for an empty name."""
        lookup = {"john doe": "john@example.com"}
        assert NameMatcher.match_name("", lookup) is None


class TestEmailPopulator:
    """Tests for EmailPopulator class."""

    @pytest.fixture
    def temp_export_dir(self):
        """Create a temp directory with entrylist.csv and attendees.csv."""
        with tempfile.TemporaryDirectory() as tmpdir:
            entrylist_data = [
                {
                    "firstName": "Alice",
                    "lastName": "Novice",
                    "segment": "Saturday Novice HPDE",
                    "group": "Novice HPDE",
                    "class": "",
                },
                {
                    "firstName": "Bob",
                    "lastName": "Student",
                    "segment": "Saturday Novice HPDE",
                    "group": "Novice HPDE",
                    "class": "",
                },
                {
                    "firstName": "Carol",
                    "lastName": "Advanced",
                    "segment": "Saturday Advanced HPDE",
                    "group": "Advanced HPDE",
                    "class": "",
                },
            ]
            entrylist_path = os.path.join(tmpdir, "entrylist.csv")
            with open(entrylist_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=entrylist_data[0].keys())
                writer.writeheader()
                writer.writerows(entrylist_data)

            attendees_data = [
                {
                    "firstName": "Alice",
                    "lastName": "Novice",
                    "email": "alice@example.com",
                    "memberId": "M001",
                    "status": "Confirmed",
                },
                {
                    "firstName": "Bob",
                    "lastName": "Student",
                    "email": "bob@example.com",
                    "memberId": "M002",
                    "status": "Confirmed",
                },
                {
                    "firstName": "Carol",
                    "lastName": "Advanced",
                    "email": "carol@example.com",
                    "memberId": "M003",
                    "status": "Confirmed",
                },
            ]
            attendees_path = os.path.join(tmpdir, "attendees.csv")
            with open(attendees_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=attendees_data[0].keys())
                writer.writeheader()
                writer.writerows(attendees_data)

            yield tmpdir

    def test_load_msr_data_from_export(self, temp_export_dir):
        """Should load entrylist and attendees from CSV files."""
        populator = EmailPopulator()
        entrylist, attendees = populator.load_msr_data_from_export(temp_export_dir)
        assert len(entrylist) == 3
        assert len(attendees) == 3

    def test_load_msr_data_from_export_missing_entrylist(self):
        """Should raise FileNotFoundError when entrylist.csv is absent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            populator = EmailPopulator()
            with pytest.raises(FileNotFoundError, match="entrylist.csv"):
                populator.load_msr_data_from_export(tmpdir)

    def test_load_msr_data_from_export_missing_attendees(self, temp_export_dir):
        """Should raise FileNotFoundError when attendees.csv is absent."""
        os.remove(os.path.join(temp_export_dir, "attendees.csv"))
        populator = EmailPopulator()
        with pytest.raises(FileNotFoundError, match="attendees.csv"):
            populator.load_msr_data_from_export(temp_export_dir)

    def test_load_msr_data_from_api(self):
        """Should extract assignments and attendees from API response dicts."""
        mock_client = MagicMock()
        mock_client.get_event_entrylist.return_value = {
            "assignments": [{"firstName": "Alice", "lastName": "Novice", "group": "Novice HPDE"}]
        }
        mock_client.get_event_attendees.return_value = {
            "attendees": [
                {"firstName": "Alice", "lastName": "Novice", "email": "alice@example.com"}
            ]
        }
        populator = EmailPopulator()
        entrylist, attendees = populator.load_msr_data_from_api(mock_client, "EVENT123")
        assert len(entrylist) == 1
        assert len(attendees) == 1
        mock_client.get_event_entrylist.assert_called_once_with("EVENT123")
        mock_client.get_event_attendees.assert_called_once_with("EVENT123")

    def test_populate_emails_basic(self):
        """Should match names and collect batch updates."""
        email_lookup = {"alice novice": "alice@example.com", "bob student": "bob@example.com"}

        mock_worksheet = MagicMock()
        mock_worksheet.title = "Form Responses 1"
        # Header row + 2 data rows
        mock_worksheet.get_all_values.return_value = [
            ["instructor", "name", "email"],
            ["Faraz Ahsan", "Alice Novice", ""],
            ["Jed Prentice", "Bob Student", ""],
        ]

        mock_sheets_client = MagicMock()
        mock_sheets_client.open_sheet.return_value = mock_worksheet
        mock_sheets_client.find_column_index.side_effect = lambda ws, col: (
            2 if col == "name" else 3
        )

        populator = EmailPopulator()
        results = populator.populate_emails(
            sheets_client=mock_sheets_client,
            sheet_id="SHEET123",
            worksheet_name=None,
            name_column="name",
            email_column="email",
            email_lookup=email_lookup,
        )

        assert results["matched"] == 2
        assert results["unmatched"] == []
        assert results["skipped"] == 0
        assert results["already_filled"] == 0
        assert results["total_rows"] == 2
        mock_sheets_client.batch_update_cells.assert_called_once()

    def test_populate_emails_skips_already_filled(self):
        """Rows where the email column is already populated should not be overwritten."""
        email_lookup = {"alice novice": "alice@example.com"}

        mock_worksheet = MagicMock()
        mock_worksheet.title = "Sheet1"
        mock_worksheet.get_all_values.return_value = [
            ["name", "email"],
            ["Alice Novice", "existing@example.com"],
        ]

        mock_sheets_client = MagicMock()
        mock_sheets_client.open_sheet.return_value = mock_worksheet
        mock_sheets_client.find_column_index.side_effect = lambda ws, col: (
            1 if col == "name" else 2
        )

        populator = EmailPopulator()
        results = populator.populate_emails(
            sheets_client=mock_sheets_client,
            sheet_id="SHEET123",
            worksheet_name=None,
            name_column="name",
            email_column="email",
            email_lookup=email_lookup,
        )

        assert results["already_filled"] == 1
        assert results["matched"] == 0
        mock_sheets_client.batch_update_cells.assert_not_called()

    def test_populate_emails_skips_empty_name(self):
        """Rows with no name value should be counted as skipped."""
        email_lookup = {"alice novice": "alice@example.com"}

        mock_worksheet = MagicMock()
        mock_worksheet.title = "Sheet1"
        mock_worksheet.get_all_values.return_value = [
            ["name", "email"],
            ["", ""],
        ]

        mock_sheets_client = MagicMock()
        mock_sheets_client.open_sheet.return_value = mock_worksheet
        mock_sheets_client.find_column_index.side_effect = lambda ws, col: (
            1 if col == "name" else 2
        )

        populator = EmailPopulator()
        results = populator.populate_emails(
            sheets_client=mock_sheets_client,
            sheet_id="SHEET123",
            worksheet_name=None,
            name_column="name",
            email_column="email",
            email_lookup=email_lookup,
        )

        assert results["skipped"] == 1
        assert results["matched"] == 0

    def test_populate_emails_reports_unmatched(self):
        """Names not found in the MSR lookup should be reported as unmatched."""
        email_lookup = {}

        mock_worksheet = MagicMock()
        mock_worksheet.title = "Sheet1"
        mock_worksheet.get_all_values.return_value = [
            ["name", "email"],
            ["Unknown Person", ""],
        ]

        mock_sheets_client = MagicMock()
        mock_sheets_client.open_sheet.return_value = mock_worksheet
        mock_sheets_client.find_column_index.side_effect = lambda ws, col: (
            1 if col == "name" else 2
        )

        populator = EmailPopulator()
        results = populator.populate_emails(
            sheets_client=mock_sheets_client,
            sheet_id="SHEET123",
            worksheet_name=None,
            name_column="name",
            email_column="email",
            email_lookup=email_lookup,
        )

        assert results["matched"] == 0
        assert len(results["unmatched"]) == 1
        assert results["unmatched"][0]["name"] == "Unknown Person"
        assert results["unmatched"][0]["row"] == 2

    def test_populate_emails_empty_sheet(self):
        """A sheet with only a header row should return zeroed results."""
        mock_worksheet = MagicMock()
        mock_worksheet.title = "Sheet1"
        mock_worksheet.get_all_values.return_value = [["name", "email"]]

        mock_sheets_client = MagicMock()
        mock_sheets_client.open_sheet.return_value = mock_worksheet
        mock_sheets_client.find_column_index.side_effect = lambda ws, col: (
            1 if col == "name" else 2
        )

        populator = EmailPopulator()
        results = populator.populate_emails(
            sheets_client=mock_sheets_client,
            sheet_id="SHEET123",
            worksheet_name=None,
            name_column="name",
            email_column="email",
            email_lookup={"alice novice": "alice@example.com"},
        )

        assert results["total_rows"] == 0
        assert results["matched"] == 0
