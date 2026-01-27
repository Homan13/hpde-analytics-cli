"""
Data Export Module

Exports raw API data to various formats for review.
"""

import csv
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Set


class DataExporter:
    """Exports MSR API data to files for review."""

    def __init__(self, output_dir: str = "output", name: Optional[str] = None):
        """
        Initialize the data exporter.

        Args:
            output_dir: Base directory for output files
            name: Optional custom name for the export folder
        """
        self.output_dir = output_dir
        self.export_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.custom_name = name

    def _ensure_dir(self, path: str) -> None:
        """Ensure directory exists."""
        os.makedirs(path, exist_ok=True)

    def _flatten_dict(self, d: Dict, parent_key: str = "", sep: str = ".") -> Dict:
        """
        Flatten a nested dictionary.

        Args:
            d: Dictionary to flatten
            parent_key: Key prefix for nested items
            sep: Separator between keys

        Returns:
            Flattened dictionary
        """
        items: List[tuple] = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                # For lists, store as JSON string to preserve data
                items.append((new_key, json.dumps(v) if v else ""))
            else:
                items.append((new_key, v))
        return dict(items)

    def export_json(self, data: Any, filename: str, include_timestamp: bool = True) -> str:
        """
        Export data to JSON file.

        Args:
            data: Data to export
            filename: Base filename (without extension)
            include_timestamp: Whether to include timestamp in filename

        Returns:
            Path to exported file
        """
        self._ensure_dir(self.output_dir)

        if include_timestamp:
            filepath = os.path.join(self.output_dir, f"{filename}_{self.export_timestamp}.json")
        else:
            filepath = os.path.join(self.output_dir, f"{filename}.json")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        return filepath

    def export_csv(self, data: List[Dict], filename: str, include_timestamp: bool = True) -> str:
        """
        Export list of dictionaries to CSV file.

        Args:
            data: List of dictionaries to export
            filename: Base filename (without extension)
            include_timestamp: Whether to include timestamp in filename

        Returns:
            Path to exported file
        """
        self._ensure_dir(self.output_dir)

        if include_timestamp:
            filepath = os.path.join(self.output_dir, f"{filename}_{self.export_timestamp}.csv")
        else:
            filepath = os.path.join(self.output_dir, f"{filename}.csv")

        if not data:
            # Create empty file with note
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("# No data available\n")
            return filepath

        # Flatten all records
        flat_data = [self._flatten_dict(record) for record in data]

        # Collect all unique keys
        all_keys: Set[str] = set()
        for record in flat_data:
            all_keys.update(record.keys())
        fieldnames = sorted(all_keys)

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(flat_data)

        return filepath

    def _export_endpoint_data(
        self,
        endpoint_name: str,
        fetch_func,
        base_filename: str,
        exported_files: Dict[str, str],
        verbose: bool,
        extract_list_key: Optional[str] = None,
    ) -> Any:
        """
        Export data from a single endpoint (JSON and optionally CSV).

        Args:
            endpoint_name: Name for the exported file key
            fetch_func: Function to call to fetch the data
            base_filename: Base name for output files
            exported_files: Dict to store file paths
            verbose: Print progress messages
            extract_list_key: Optional key to extract list data for CSV export

        Returns:
            The fetched data, or None if error occurred
        """
        if verbose:
            print(f"  Exporting {endpoint_name}...")
        try:
            data = fetch_func()
            json_key = f"{endpoint_name}"
            exported_files[json_key] = self.export_json(
                data, base_filename, include_timestamp=False
            )

            # Export CSV if list data is available
            if extract_list_key:
                items = data.get(extract_list_key, [])
                if items:
                    csv_key = f"{endpoint_name}_csv"
                    exported_files[csv_key] = self.export_csv(
                        items, base_filename, include_timestamp=False
                    )
                    if verbose:
                        print(f"    [OK] {exported_files[json_key]} ({len(items)} items)")
                else:
                    if verbose:
                        print(f"    [OK] {exported_files[json_key]}")
            else:
                if verbose:
                    print(f"    [OK] {exported_files[json_key]}")

            return data
        except Exception as e:
            if verbose:
                print(f"    [ERROR] {e}")
            return None

    def _fetch_raw_data(
        self, client, event_id: str, exported_files: Dict[str, str], verbose: bool
    ) -> Dict[str, Any]:
        """Fetch and export raw data from all endpoints."""
        raw_data = {}

        # 1. Export user profile
        data = self._export_endpoint_data(
            "raw_profile",
            client.get_me,
            "profile_full",
            exported_files,
            verbose,
        )
        if data:
            raw_data["me"] = data

        # 2. Export organization calendar
        data = self._export_endpoint_data(
            "raw_calendar",
            client.get_organization_calendar,
            "calendar_full",
            exported_files,
            verbose,
            extract_list_key="events",
        )
        if data:
            raw_data["calendar"] = data

        # 3. Export entry list
        data = self._export_endpoint_data(
            "raw_entrylist",
            lambda: client.get_event_entrylist(event_id),
            "entrylist_full",
            exported_files,
            verbose,
            extract_list_key="assignments",
        )
        if data:
            raw_data["entrylist"] = data

        # 4. Export attendees
        data = self._export_endpoint_data(
            "raw_attendees",
            lambda: client.get_event_attendees(event_id),
            "attendees_full",
            exported_files,
            verbose,
            extract_list_key="attendees",
        )
        if data:
            raw_data["attendees"] = data

        # 5. Export assignments
        data = self._export_endpoint_data(
            "raw_assignments",
            lambda: client.get_event_assignments(event_id),
            "assignments_full",
            exported_files,
            verbose,
            extract_list_key="assignments",
        )
        if data:
            raw_data["assignments"] = data

        return raw_data

    def _export_single_filtered_endpoint(
        self,
        raw_data: Dict[str, Any],
        raw_key: str,
        export_key: str,
        base_filename: str,
        list_key: Optional[str],
        exported_files: Dict[str, str],
        verbose: bool,
    ) -> None:
        """Export a single filtered endpoint."""
        if raw_key not in raw_data:
            return

        if verbose:
            print(f"  Exporting {export_key}...")

        exported_files[export_key] = self.export_json(
            raw_data[raw_key], base_filename, include_timestamp=False
        )

        if list_key:
            items = raw_data[raw_key].get(list_key, [])
            if items:
                exported_files[f"{export_key}_csv"] = self.export_csv(
                    items, base_filename, include_timestamp=False
                )
                if verbose:
                    print(f"    [OK] {exported_files[export_key]} ({len(items)} items)")
            else:
                if verbose:
                    print(f"    [OK] {exported_files[export_key]}")
        else:
            if verbose:
                print(f"    [OK] {exported_files[export_key]}")

    def _export_filtered_data(
        self, raw_data: Dict[str, Any], exported_files: Dict[str, str], verbose: bool
    ) -> None:
        """Export filtered/curated data for Time Trials use."""
        endpoints = [
            ("me", "profile", "profile", None),
            ("calendar", "calendar", "calendar_events", "events"),
            ("entrylist", "entrylist", "entrylist", "assignments"),
            ("attendees", "attendees", "attendees", "attendees"),
            ("assignments", "assignments", "assignments", "assignments"),
        ]

        for raw_key, export_key, base_filename, list_key in endpoints:
            self._export_single_filtered_endpoint(
                raw_data, raw_key, export_key, base_filename, list_key, exported_files, verbose
            )

    def export_all_data(self, client, event_id: str, verbose: bool = False) -> Dict[str, str]:
        """
        Export all available data for an event.

        Creates two sets of exports:
        1. Full raw data (raw_data/ subfolder) - complete API responses for reference
        2. Filtered data (main folder) - curated exports for Time Trials use

        Args:
            client: MSRClient instance
            event_id: Event ID to export data for
            verbose: Print progress messages

        Returns:
            Dictionary mapping endpoint names to exported file paths
        """
        exported_files: Dict[str, str] = {}

        # Setup directories
        if self.custom_name:
            folder_name = f"{self.custom_name}_{self.export_timestamp}"
        else:
            folder_name = f"export_{self.export_timestamp}"
        export_subdir = os.path.join(self.output_dir, folder_name)
        raw_data_subdir = os.path.join(export_subdir, "raw_data")
        self._ensure_dir(export_subdir)
        self._ensure_dir(raw_data_subdir)

        original_output_dir = self.output_dir

        try:
            # Phase 1: Fetch and export raw data
            if verbose:
                print("\n  --- Exporting Full Raw Data (raw_data/) ---")
            self.output_dir = raw_data_subdir
            raw_data = self._fetch_raw_data(client, event_id, exported_files, verbose)

            # Phase 2: Export filtered data
            if verbose:
                print("\n  --- Exporting Filtered Data (Time Trials) ---")
            self.output_dir = export_subdir
            self._export_filtered_data(raw_data, exported_files, verbose)

            # Create summary file
            if verbose:
                print("  Creating export summary...")
            summary = {
                "export_timestamp": self.export_timestamp,
                "event_id": event_id,
                "organization_id": client.organization_id,
                "files_exported": list(exported_files.keys()),
                "export_directory": export_subdir,
                "raw_data_directory": raw_data_subdir,
            }
            exported_files["summary"] = self.export_json(
                summary, "export_summary", include_timestamp=False
            )
            if verbose:
                print(f"    [OK] {exported_files['summary']}")

        finally:
            self.output_dir = original_output_dir

        return exported_files
