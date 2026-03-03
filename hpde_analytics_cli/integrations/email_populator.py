"""
Email Populator Module

Matches student names from Google Form responses to MSR event data
and populates email addresses in the Google Sheet.
"""

import csv
import os
from typing import Any, Dict, List, Optional, Tuple


class NameMatcher:
    """Handles name normalization and matching between MSR and Sheet data."""

    @staticmethod
    def normalize(name: str) -> str:
        """Normalize a name for comparison: lowercase, strip, collapse spaces."""
        return " ".join(name.lower().split())

    @staticmethod
    def build_email_lookup(
        entrylist: List[Dict],
        attendees: List[Dict],
        group_filter: str,
    ) -> Dict[str, str]:
        """
        Build a lookup dict: normalized full name -> email.

        Filters entrylist by group substring, then enriches with email from attendees.

        Args:
            entrylist: List of entrylist records (with firstName, lastName, group)
            attendees: List of attendee records (with firstName, lastName, email)
            group_filter: Case-insensitive substring to match against group field

        Returns:
            Dict mapping normalized "firstname lastname" -> email
        """
        # Build attendee email lookup by driver key (first|last)
        attendee_emails: Dict[str, str] = {}
        for att in attendees:
            first = (att.get("firstName") or "").strip()
            last = (att.get("lastName") or "").strip()
            email = (att.get("email") or "").strip()
            if first and last and email:
                key = f"{first.lower()}|{last.lower()}"
                attendee_emails[key] = email

        # Filter entrylist by group and build name -> email lookup
        email_lookup: Dict[str, str] = {}
        group_filter_lower = group_filter.lower()

        for entry in entrylist:
            group = (entry.get("group") or "").lower()
            if group_filter_lower not in group:
                continue

            first = (entry.get("firstName") or "").strip()
            last = (entry.get("lastName") or "").strip()
            if not first or not last:
                continue

            driver_key = f"{first.lower()}|{last.lower()}"
            email = attendee_emails.get(driver_key, "")

            if email:
                full_name = NameMatcher.normalize(f"{first} {last}")
                email_lookup[full_name] = email

        return email_lookup

    @staticmethod
    def match_name(sheet_name: str, email_lookup: Dict[str, str]) -> Optional[str]:
        """
        Match a name from the Sheet against the MSR email lookup.

        Args:
            sheet_name: Name string from the Google Sheet
            email_lookup: Dict of normalized name -> email

        Returns:
            Email address if matched, None otherwise
        """
        normalized = NameMatcher.normalize(sheet_name)
        return email_lookup.get(normalized)


class EmailPopulator:
    """Orchestrates the email population workflow."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def _log(self, message: str) -> None:
        """Print message if verbose mode is on."""
        if self.verbose:
            print(message)

    def _read_csv(self, filepath: str) -> List[Dict]:
        """Read a CSV file into a list of dictionaries."""
        rows = []
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
        return rows

    def load_msr_data_from_export(self, export_dir: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Load entrylist and attendees from export CSV files.

        Args:
            export_dir: Directory containing entrylist.csv and attendees.csv

        Returns:
            Tuple of (entrylist records, attendee records)
        """
        entrylist_path = os.path.join(export_dir, "entrylist.csv")
        attendees_path = os.path.join(export_dir, "attendees.csv")

        if not os.path.exists(entrylist_path):
            raise FileNotFoundError(f"entrylist.csv not found in {export_dir}")
        if not os.path.exists(attendees_path):
            raise FileNotFoundError(f"attendees.csv not found in {export_dir}")

        entrylist = self._read_csv(entrylist_path)
        attendees = self._read_csv(attendees_path)

        self._log(
            f"  Loaded {len(entrylist)} entrylist records " f"and {len(attendees)} attendee records"
        )

        return entrylist, attendees

    def load_msr_data_from_api(self, client: Any, event_id: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Fetch entrylist and attendees from MSR API.

        Args:
            client: Authenticated MSRClient instance
            event_id: MSR event ID

        Returns:
            Tuple of (entrylist records, attendee records)
        """
        self._log("  Fetching entrylist from MSR API...")
        entrylist_data = client.get_event_entrylist(event_id)
        entrylist = entrylist_data.get("assignments", [])

        self._log("  Fetching attendees from MSR API...")
        attendees_data = client.get_event_attendees(event_id)
        attendees = attendees_data.get("attendees", [])

        self._log(
            f"  Fetched {len(entrylist)} entrylist records "
            f"and {len(attendees)} attendee records"
        )

        return entrylist, attendees

    def populate_emails(
        self,
        sheets_client: Any,
        sheet_id: str,
        worksheet_name: Optional[str],
        name_column: str,
        email_column: str,
        email_lookup: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Read names from Sheet, match to emails, write results.

        Skips rows where the email column is already populated.

        Args:
            sheets_client: Authenticated GoogleSheetsClient instance
            sheet_id: Google Sheet ID
            worksheet_name: Optional worksheet/tab name (default: first sheet)
            name_column: Column letter or header text for student names
            email_column: Column letter or header text for email addresses
            email_lookup: Dict of normalized name -> email from MSR data

        Returns:
            Dict with keys: matched, unmatched, skipped, already_filled, total_rows
        """
        self._log("\n  Connecting to Google Sheets...")
        sheets_client.connect()

        worksheet = sheets_client.open_sheet(sheet_id, worksheet_name)
        self._log(f"  Opened worksheet: {worksheet.title}")

        name_col_idx = sheets_client.find_column_index(worksheet, name_column)
        email_col_idx = sheets_client.find_column_index(worksheet, email_column)
        self._log(f"  Name column index: {name_col_idx}, Email column index: {email_col_idx}")

        # Read all data at once to minimize API calls
        all_records = worksheet.get_all_values()
        if len(all_records) <= 1:
            self._log("  Sheet has no data rows (only header or empty).")
            return {
                "matched": 0,
                "unmatched": [],
                "skipped": 0,
                "already_filled": 0,
                "total_rows": 0,
            }

        # Process rows (skip header row at index 0; Sheet rows start at 2)
        updates = []
        matched = 0
        unmatched = []
        skipped = 0
        already_filled = 0

        for row_idx, row in enumerate(all_records[1:], start=2):
            name_value = row[name_col_idx - 1].strip() if len(row) >= name_col_idx else ""
            email_value = row[email_col_idx - 1].strip() if len(row) >= email_col_idx else ""

            if not name_value:
                skipped += 1
                continue

            if email_value:
                already_filled += 1
                continue

            email = NameMatcher.match_name(name_value, email_lookup)
            if email:
                updates.append((row_idx, email_col_idx, email))
                matched += 1
                self._log(f"    [MATCH] Row {row_idx}: {name_value} -> {email}")
            else:
                unmatched.append({"row": row_idx, "name": name_value})
                self._log(f"    [NO MATCH] Row {row_idx}: {name_value}")

        if updates:
            self._log(f"\n  Writing {len(updates)} email addresses to Sheet...")
            sheets_client.batch_update_cells(worksheet, updates)

        return {
            "matched": matched,
            "unmatched": unmatched,
            "skipped": skipped,
            "already_filled": already_filled,
            "total_rows": len(all_records) - 1,
        }
