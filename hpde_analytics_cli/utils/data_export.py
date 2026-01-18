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
        exported_files = {}
        # Use custom name if provided, otherwise use timestamp
        if self.custom_name:
            folder_name = f"{self.custom_name}_{self.export_timestamp}"
        else:
            folder_name = f"export_{self.export_timestamp}"
        export_subdir = os.path.join(self.output_dir, folder_name)
        raw_data_subdir = os.path.join(export_subdir, "raw_data")
        self._ensure_dir(export_subdir)
        self._ensure_dir(raw_data_subdir)

        # Store original output dir
        original_output_dir = self.output_dir

        # Store raw API responses for later use
        raw_data = {}

        try:
            # ============================================================
            # PHASE 1: Fetch all data and export full raw copies
            # ============================================================
            if verbose:
                print("\n  --- Exporting Full Raw Data (raw_data/) ---")

            self.output_dir = raw_data_subdir

            # 1. Export user profile (raw)
            if verbose:
                print("  Exporting user profile (raw)...")
            try:
                me_data = client.get_me()
                raw_data["me"] = me_data
                exported_files["raw_profile"] = self.export_json(
                    me_data, "profile_full", include_timestamp=False
                )
                if verbose:
                    print(f"    [OK] {exported_files['raw_profile']}")
            except Exception as e:
                if verbose:
                    print(f"    [ERROR] {e}")

            # 2. Export organization calendar (raw)
            if verbose:
                print("  Exporting organization calendar (raw)...")
            try:
                calendar_data = client.get_organization_calendar()
                raw_data["calendar"] = calendar_data
                exported_files["raw_calendar"] = self.export_json(
                    calendar_data, "calendar_full", include_timestamp=False
                )
                events = calendar_data.get("events", [])
                if events:
                    exported_files["raw_calendar_csv"] = self.export_csv(
                        events, "calendar_full", include_timestamp=False
                    )
                if verbose:
                    print(f"    [OK] {exported_files['raw_calendar']} ({len(events)} events)")
            except Exception as e:
                if verbose:
                    print(f"    [ERROR] {e}")

            # 3. Export entry list (raw)
            if verbose:
                print("  Exporting entry list (raw)...")
            try:
                entrylist_data = client.get_event_entrylist(event_id)
                raw_data["entrylist"] = entrylist_data
                exported_files["raw_entrylist"] = self.export_json(
                    entrylist_data, "entrylist_full", include_timestamp=False
                )
                assignments = entrylist_data.get("assignments", [])
                if assignments:
                    exported_files["raw_entrylist_csv"] = self.export_csv(
                        assignments, "entrylist_full", include_timestamp=False
                    )
                if verbose:
                    print(
                        f"    [OK] {exported_files['raw_entrylist']} ({len(assignments)} entries)"
                    )
            except Exception as e:
                if verbose:
                    print(f"    [ERROR] {e}")

            # 4. Export attendees (raw)
            if verbose:
                print("  Exporting attendees (raw)...")
            try:
                attendees_data = client.get_event_attendees(event_id)
                raw_data["attendees"] = attendees_data
                exported_files["raw_attendees"] = self.export_json(
                    attendees_data, "attendees_full", include_timestamp=False
                )
                attendees = attendees_data.get("attendees", [])
                if attendees:
                    exported_files["raw_attendees_csv"] = self.export_csv(
                        attendees, "attendees_full", include_timestamp=False
                    )
                if verbose:
                    print(
                        f"    [OK] {exported_files['raw_attendees']} ({len(attendees)} attendees)"
                    )
            except Exception as e:
                if verbose:
                    print(f"    [ERROR] {e}")

            # 5. Export assignments (raw)
            if verbose:
                print("  Exporting assignments (raw)...")
            try:
                assignments_data = client.get_event_assignments(event_id)
                raw_data["assignments"] = assignments_data
                exported_files["raw_assignments"] = self.export_json(
                    assignments_data, "assignments_full", include_timestamp=False
                )
                assignments = assignments_data.get("assignments", [])
                if assignments:
                    exported_files["raw_assignments_csv"] = self.export_csv(
                        assignments, "assignments_full", include_timestamp=False
                    )
                if verbose:
                    print(
                        f"    [OK] {exported_files['raw_assignments']} ({len(assignments)} assignments)"
                    )
            except Exception as e:
                if verbose:
                    print(f"    [ERROR] {e}")

            # ============================================================
            # PHASE 2: Export filtered data for Time Trials use
            # ============================================================
            if verbose:
                print("\n  --- Exporting Filtered Data (Time Trials) ---")

            self.output_dir = export_subdir

            # 1. Export user profile (filtered - same as raw for this endpoint)
            if verbose:
                print("  Exporting user profile...")
            if "me" in raw_data:
                exported_files["profile"] = self.export_json(
                    raw_data["me"], "profile", include_timestamp=False
                )
                if verbose:
                    print(f"    [OK] {exported_files['profile']}")

            # 2. Export organization calendar (filtered)
            if verbose:
                print("  Exporting organization calendar...")
            if "calendar" in raw_data:
                exported_files["calendar"] = self.export_json(
                    raw_data["calendar"], "calendar", include_timestamp=False
                )
                events = raw_data["calendar"].get("events", [])
                if events:
                    exported_files["calendar_csv"] = self.export_csv(
                        events, "calendar_events", include_timestamp=False
                    )
                if verbose:
                    print(f"    [OK] {exported_files['calendar']} ({len(events)} events)")

            # 3. Export entry list (filtered)
            if verbose:
                print("  Exporting entry list...")
            if "entrylist" in raw_data:
                exported_files["entrylist"] = self.export_json(
                    raw_data["entrylist"], "entrylist", include_timestamp=False
                )
                assignments = raw_data["entrylist"].get("assignments", [])
                if assignments:
                    exported_files["entrylist_csv"] = self.export_csv(
                        assignments, "entrylist", include_timestamp=False
                    )
                if verbose:
                    print(f"    [OK] {exported_files['entrylist']} ({len(assignments)} entries)")

            # 4. Export attendees (filtered)
            if verbose:
                print("  Exporting attendees...")
            if "attendees" in raw_data:
                exported_files["attendees"] = self.export_json(
                    raw_data["attendees"], "attendees", include_timestamp=False
                )
                attendees = raw_data["attendees"].get("attendees", [])
                if attendees:
                    exported_files["attendees_csv"] = self.export_csv(
                        attendees, "attendees", include_timestamp=False
                    )
                if verbose:
                    print(f"    [OK] {exported_files['attendees']} ({len(attendees)} attendees)")

            # 5. Export assignments (filtered)
            if verbose:
                print("  Exporting assignments...")
            if "assignments" in raw_data:
                exported_files["assignments"] = self.export_json(
                    raw_data["assignments"], "assignments", include_timestamp=False
                )
                assignments = raw_data["assignments"].get("assignments", [])
                if assignments:
                    exported_files["assignments_csv"] = self.export_csv(
                        assignments, "assignments", include_timestamp=False
                    )
                if verbose:
                    print(
                        f"    [OK] {exported_files['assignments']} ({len(assignments)} assignments)"
                    )

            # 6. Create summary file
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
            # Restore original output dir
            self.output_dir = original_output_dir

        return exported_files
