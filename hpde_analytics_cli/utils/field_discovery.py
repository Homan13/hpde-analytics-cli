"""
Field discovery module for analyzing API responses.

Recursively parses JSON responses to enumerate all available fields,
detect data types, and generate a comprehensive field inventory.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


class FieldInfo:
    """Information about a discovered field."""

    def __init__(self, path: str, field_type: str, sample_value: Any = None):
        self.path = path
        self.field_type = field_type
        self.sample_value = sample_value
        self.occurrences = 1
        self.nullable = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "path": self.path,
            "type": self.field_type,
            "occurrences": self.occurrences,
            "nullable": self.nullable,
        }

        # Include sanitized sample value
        if self.sample_value is not None:
            result["sample"] = self._sanitize_sample(self.sample_value)

        return result

    def _sanitize_sample(self, value: Any) -> Any:
        """Sanitize sample value to avoid exposing PII."""
        if isinstance(value, str):
            # Mask email addresses
            if "@" in value and "." in value:
                parts = value.split("@")
                return f"{parts[0][:2]}***@{parts[1]}"
            # Mask phone numbers (basic pattern)
            if re.match(r"^[\d\-\(\)\s\+]+$", value) and len(value) >= 10:
                return "***-***-" + value[-4:]
            # Truncate long strings
            if len(value) > 50:
                return value[:47] + "..."
        return value


class FieldDiscovery:
    """Discovers and catalogs fields from API responses."""

    # Patterns for detecting special string types
    DATE_PATTERNS = [
        r"^\d{4}-\d{2}-\d{2}$",  # ISO date
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # ISO datetime
        r"^\d{2}/\d{2}/\d{4}$",  # US date
    ]

    UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    URL_PATTERN = r"^https?://"
    EMAIL_PATTERN = r"^[^@]+@[^@]+\.[^@]+$"

    def __init__(self):
        self.fields: dict[str, FieldInfo] = {}
        self.endpoint_fields: dict[str, list[str]] = {}

    def _detect_type(self, value: Any) -> str:
        """
        Detect the type of a value, including special string subtypes.

        Args:
            value: The value to analyze

        Returns:
            Type string (e.g., "string", "integer", "date", "url", etc.)
        """
        if value is None:
            return "null"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, str):
            # Check for special string types
            for pattern in self.DATE_PATTERNS:
                if re.match(pattern, value):
                    return "datetime" if "T" in value else "date"

            if re.match(self.UUID_PATTERN, value):
                return "uuid"
            if re.match(self.URL_PATTERN, value):
                return "url"
            if re.match(self.EMAIL_PATTERN, value):
                return "email"

            return "string"
        elif isinstance(value, list):
            return "array"
        elif isinstance(value, dict):
            return "object"
        else:
            return "unknown"

    def _parse_value(self, value: Any, path: str, endpoint: str) -> None:
        """
        Recursively parse a value and discover fields.

        Args:
            value: The value to parse
            path: Current JSON path (e.g., "event.venue.name")
            endpoint: Name of the endpoint this data came from
        """
        value_type = self._detect_type(value)

        if value_type == "object" and isinstance(value, dict):
            # Recurse into object properties
            for key, val in value.items():
                child_path = f"{path}.{key}" if path else key
                self._parse_value(val, child_path, endpoint)

        elif value_type == "array" and isinstance(value, list):
            # Record the array field itself
            self._record_field(path, "array", value, endpoint)

            # Parse array items (use first few items for type detection)
            for i, item in enumerate(value[:3]):  # Sample first 3 items
                item_path = f"{path}[]"
                self._parse_value(item, item_path, endpoint)

        else:
            # Leaf value - record it
            self._record_field(path, value_type, value, endpoint)

    def _record_field(self, path: str, field_type: str, value: Any, endpoint: str) -> None:
        """
        Record a discovered field.

        Args:
            path: JSON path to the field
            field_type: Detected type
            value: Sample value
            endpoint: Source endpoint
        """
        if not path:
            return

        if path in self.fields:
            # Update existing field
            field = self.fields[path]
            field.occurrences += 1
            if field_type == "null":
                field.nullable = True
            elif field.field_type == "null" and field_type != "null":
                # Update type if we now have a non-null value
                field.field_type = field_type
                field.sample_value = value
        else:
            # New field
            field = FieldInfo(path, field_type, value if field_type != "null" else None)
            if field_type == "null":
                field.nullable = True
            self.fields[path] = field

        # Track which endpoints have this field
        if endpoint not in self.endpoint_fields:
            self.endpoint_fields[endpoint] = []
        if path not in self.endpoint_fields[endpoint]:
            self.endpoint_fields[endpoint].append(path)

    def analyze_response(self, data: Any, endpoint: str) -> int:
        """
        Analyze an API response and discover fields.

        Args:
            data: API response data (dict or list)
            endpoint: Name of the endpoint

        Returns:
            Number of fields discovered
        """
        if isinstance(data, dict) and "error" in data:
            # Skip error responses
            return 0

        initial_count = len(self.fields)
        self._parse_value(data, "", endpoint)
        return len(self.fields) - initial_count

    def analyze_all_responses(self, responses: dict[str, Any]) -> dict[str, int]:
        """
        Analyze multiple API responses.

        Args:
            responses: Dict mapping endpoint names to response data

        Returns:
            Dict mapping endpoint names to field counts
        """
        results = {}
        for endpoint, data in responses.items():
            count = self.analyze_response(data, endpoint)
            results[endpoint] = count
        return results

    def get_inventory(self) -> dict:
        """
        Get the complete field inventory.

        Returns:
            Dict with metadata and field information
        """
        # Group fields by endpoint
        endpoints_data = {}
        for endpoint, field_paths in self.endpoint_fields.items():
            endpoints_data[endpoint] = {
                "field_count": len(field_paths),
                "fields": [
                    self.fields[path].to_dict()
                    for path in sorted(field_paths)
                    if path in self.fields
                ],
            }

        return {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "version": "1.0.0",
                "total_fields": len(self.fields),
                "endpoints_analyzed": len(self.endpoint_fields),
            },
            "summary": {
                "endpoints": list(self.endpoint_fields.keys()),
                "field_counts": {
                    endpoint: len(paths) for endpoint, paths in self.endpoint_fields.items()
                },
            },
            "endpoints": endpoints_data,
            "all_fields": [self.fields[path].to_dict() for path in sorted(self.fields.keys())],
        }

    def get_fields_by_type(self) -> dict[str, list[str]]:
        """
        Group fields by their detected type.

        Returns:
            Dict mapping types to lists of field paths
        """
        by_type: dict[str, list[str]] = {}
        for path, field in self.fields.items():
            if field.field_type not in by_type:
                by_type[field.field_type] = []
            by_type[field.field_type].append(path)
        return by_type

    def print_summary(self) -> None:
        """Print a formatted summary of discovered fields."""
        print("\n" + "=" * 60)
        print("Field Discovery Summary")
        print("=" * 60)

        print(f"\nTotal unique fields discovered: {len(self.fields)}")
        print(f"Endpoints analyzed: {len(self.endpoint_fields)}")

        # Fields by type
        by_type = self.get_fields_by_type()
        print("\nFields by type:")
        for field_type, paths in sorted(by_type.items()):
            print(f"  {field_type}: {len(paths)}")

        # Fields per endpoint
        print("\nFields per endpoint:")
        for endpoint, paths in sorted(self.endpoint_fields.items()):
            print(f"  {endpoint}: {len(paths)} fields")

        print("\n" + "-" * 60)
        print("Detailed Field List")
        print("-" * 60)

        for endpoint, paths in sorted(self.endpoint_fields.items()):
            print(f"\n[{endpoint}]")
            for path in sorted(paths)[:20]:  # Show first 20 per endpoint
                field = self.fields.get(path)
                if field:
                    nullable = " (nullable)" if field.nullable else ""
                    print(f"  {path}: {field.field_type}{nullable}")
            if len(paths) > 20:
                print(f"  ... and {len(paths) - 20} more fields")


def save_inventory(inventory: dict, output_path: str) -> None:
    """
    Save field inventory to a JSON file.

    Args:
        inventory: Field inventory dict
        output_path: Path to output file
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w") as f:
        json.dump(inventory, f, indent=2, default=str)

    print(f"\nField inventory saved to: {path}")


def run_field_discovery(
    api_data: dict[str, Any],
    output_path: str = None,
    verbose: bool = False,
) -> dict:
    """
    Run field discovery on API response data.

    Args:
        api_data: Dict of API responses keyed by endpoint name
        output_path: Optional path to save JSON inventory
        verbose: Print detailed output

    Returns:
        Field inventory dict
    """
    discovery = FieldDiscovery()

    print("\nAnalyzing API responses...")
    results = discovery.analyze_all_responses(api_data)

    for endpoint, count in results.items():
        status = "[OK]" if count > 0 else "[SKIP]"
        print(f"  {status} {endpoint}: {count} new fields")

    # Print summary
    discovery.print_summary()

    # Get inventory
    inventory = discovery.get_inventory()

    # Save to file if path provided
    if output_path:
        save_inventory(inventory, output_path)

    return inventory
