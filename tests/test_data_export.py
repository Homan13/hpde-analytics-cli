"""
Tests for the data export module.
"""

import csv
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from hpde_analytics_cli.utils.data_export import DataExporter


class TestDataExporter:
    """Tests for DataExporter class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def exporter(self, temp_dir):
        """Create a DataExporter instance."""
        return DataExporter(output_dir=temp_dir)

    def test_init_default(self):
        """Test default initialization."""
        exporter = DataExporter()
        assert exporter.output_dir == "output"
        assert exporter.custom_name is None
        assert exporter.export_timestamp is not None

    def test_init_custom_output_dir(self, temp_dir):
        """Test initialization with custom output directory."""
        exporter = DataExporter(output_dir=temp_dir)
        assert exporter.output_dir == temp_dir

    def test_init_custom_name(self, temp_dir):
        """Test initialization with custom name."""
        exporter = DataExporter(output_dir=temp_dir, name="custom_export")
        assert exporter.custom_name == "custom_export"

    def test_ensure_dir_creates_directory(self, temp_dir):
        """Test that _ensure_dir creates directories."""
        exporter = DataExporter(output_dir=temp_dir)
        new_dir = os.path.join(temp_dir, "subdir", "nested")

        exporter._ensure_dir(new_dir)

        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)

    def test_ensure_dir_existing_directory(self, temp_dir):
        """Test that _ensure_dir handles existing directories."""
        exporter = DataExporter(output_dir=temp_dir)

        # Should not raise an error
        exporter._ensure_dir(temp_dir)

        assert os.path.exists(temp_dir)

    def test_flatten_dict_simple(self, exporter):
        """Test flattening a simple dictionary."""
        data = {"key1": "value1", "key2": "value2"}
        result = exporter._flatten_dict(data)

        assert result == {"key1": "value1", "key2": "value2"}

    def test_flatten_dict_nested(self, exporter):
        """Test flattening a nested dictionary."""
        data = {"level1": {"level2": "value"}}
        result = exporter._flatten_dict(data)

        assert result == {"level1.level2": "value"}

    def test_flatten_dict_deeply_nested(self, exporter):
        """Test flattening a deeply nested dictionary."""
        data = {"a": {"b": {"c": "deep_value"}}}
        result = exporter._flatten_dict(data)

        assert result == {"a.b.c": "deep_value"}

    def test_flatten_dict_with_list(self, exporter):
        """Test flattening dictionary with list values."""
        data = {"items": [1, 2, 3]}
        result = exporter._flatten_dict(data)

        assert result["items"] == "[1, 2, 3]"

    def test_flatten_dict_empty_list(self, exporter):
        """Test flattening dictionary with empty list."""
        data = {"items": []}
        result = exporter._flatten_dict(data)

        assert result["items"] == ""

    def test_export_json_with_timestamp(self, exporter, temp_dir):
        """Test JSON export with timestamp."""
        data = {"test": "data"}

        filepath = exporter.export_json(data, "test_file", include_timestamp=True)

        assert os.path.exists(filepath)
        assert exporter.export_timestamp in filepath
        assert filepath.endswith(".json")

        with open(filepath, "r") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_export_json_without_timestamp(self, exporter, temp_dir):
        """Test JSON export without timestamp."""
        data = {"test": "data"}

        filepath = exporter.export_json(data, "test_file", include_timestamp=False)

        assert os.path.exists(filepath)
        assert filepath.endswith("test_file.json")
        assert exporter.export_timestamp not in filepath

    def test_export_json_complex_data(self, exporter, temp_dir):
        """Test JSON export with complex data."""
        data = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null": None,
            "nested": {"inner": "value"},
            "array": [1, 2, 3],
        }

        filepath = exporter.export_json(data, "complex", include_timestamp=False)

        with open(filepath, "r") as f:
            loaded = json.load(f)
        assert loaded == data

    def test_export_csv_basic(self, exporter, temp_dir):
        """Test basic CSV export."""
        data = [{"name": "John", "age": "30"}, {"name": "Jane", "age": "25"}]

        filepath = exporter.export_csv(data, "test_csv", include_timestamp=False)

        assert os.path.exists(filepath)
        assert filepath.endswith(".csv")

        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["name"] == "John"
        assert rows[1]["name"] == "Jane"

    def test_export_csv_with_timestamp(self, exporter, temp_dir):
        """Test CSV export with timestamp."""
        data = [{"col": "value"}]

        filepath = exporter.export_csv(data, "test_csv", include_timestamp=True)

        assert exporter.export_timestamp in filepath

    def test_export_csv_empty_data(self, exporter, temp_dir):
        """Test CSV export with empty data."""
        data = []

        filepath = exporter.export_csv(data, "empty", include_timestamp=False)

        assert os.path.exists(filepath)
        with open(filepath, "r") as f:
            content = f.read()
        assert "No data available" in content

    def test_export_csv_flattens_nested(self, exporter, temp_dir):
        """Test that CSV export flattens nested dictionaries."""
        data = [{"name": "Test", "details": {"color": "red"}}]

        filepath = exporter.export_csv(data, "nested", include_timestamp=False)

        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert "details.color" in rows[0]
        assert rows[0]["details.color"] == "red"

    def test_export_csv_varying_fields(self, exporter, temp_dir):
        """Test CSV export with records having different fields."""
        data = [{"name": "John", "age": "30"}, {"name": "Jane", "city": "NYC"}]

        filepath = exporter.export_csv(data, "varying", include_timestamp=False)

        with open(filepath, "r") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames

        # All fields should be present
        assert "name" in fieldnames
        assert "age" in fieldnames
        assert "city" in fieldnames


class TestDataExporterExportAllData:
    """Tests for export_all_data method."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def mock_client(self):
        """Create a mock MSRClient."""
        client = MagicMock()
        client.organization_id = "test-org-id"

        client.get_me.return_value = {"firstName": "Test", "lastName": "User"}
        client.get_organization_calendar.return_value = {
            "events": [{"id": "event-1", "name": "Test Event"}]
        }
        client.get_event_entrylist.return_value = {
            "assignments": [{"firstName": "Driver", "lastName": "One"}]
        }
        client.get_event_attendees.return_value = {
            "attendees": [{"firstName": "Driver", "lastName": "One", "email": "driver@example.com"}]
        }
        client.get_event_assignments.return_value = {
            "assignments": [{"firstName": "Driver", "lastName": "One", "vehicle": "Test Car"}]
        }

        return client

    def test_export_all_data_creates_structure(self, temp_dir, mock_client):
        """Test that export_all_data creates proper directory structure."""
        exporter = DataExporter(output_dir=temp_dir)

        exported_files = exporter.export_all_data(mock_client, "event-123")

        # Check that export directory was created
        export_dirs = [d for d in os.listdir(temp_dir) if d.startswith("export_")]
        assert len(export_dirs) == 1

        export_dir = os.path.join(temp_dir, export_dirs[0])
        assert os.path.exists(export_dir)

        # Check raw_data subdirectory
        raw_data_dir = os.path.join(export_dir, "raw_data")
        assert os.path.exists(raw_data_dir)

    def test_export_all_data_with_custom_name(self, temp_dir, mock_client):
        """Test export with custom name."""
        exporter = DataExporter(output_dir=temp_dir, name="HPDE_TT_1")

        exporter.export_all_data(mock_client, "event-123")

        # Should use custom name in folder
        dirs = os.listdir(temp_dir)
        assert any(d.startswith("HPDE_TT_1_") for d in dirs)

    def test_export_all_data_creates_files(self, temp_dir, mock_client):
        """Test that export_all_data creates expected files."""
        exporter = DataExporter(output_dir=temp_dir)

        exported_files = exporter.export_all_data(mock_client, "event-123")

        # Check that files were exported
        assert "profile" in exported_files
        assert "calendar" in exported_files
        assert "entrylist" in exported_files
        assert "attendees" in exported_files
        assert "assignments" in exported_files
        assert "summary" in exported_files

    def test_export_all_data_creates_raw_files(self, temp_dir, mock_client):
        """Test that raw data files are created."""
        exporter = DataExporter(output_dir=temp_dir)

        exported_files = exporter.export_all_data(mock_client, "event-123")

        # Check raw files
        assert "raw_profile" in exported_files
        assert "raw_calendar" in exported_files
        assert "raw_entrylist" in exported_files
        assert "raw_attendees" in exported_files
        assert "raw_assignments" in exported_files

    def test_export_all_data_verbose_output(self, temp_dir, mock_client, capsys):
        """Test verbose output during export."""
        exporter = DataExporter(output_dir=temp_dir)

        exporter.export_all_data(mock_client, "event-123", verbose=True)

        captured = capsys.readouterr()
        assert "Exporting" in captured.out
        assert "[OK]" in captured.out

    def test_export_all_data_handles_api_errors(self, temp_dir, mock_client, capsys):
        """Test that API errors are handled gracefully."""
        from hpde_analytics_cli.api.client import APIError

        mock_client.get_me.side_effect = APIError("API Error")

        exporter = DataExporter(output_dir=temp_dir)
        exported_files = exporter.export_all_data(mock_client, "event-123", verbose=True)

        captured = capsys.readouterr()
        assert "[ERROR]" in captured.out

    def test_export_all_data_summary_content(self, temp_dir, mock_client):
        """Test that summary file contains expected information."""
        exporter = DataExporter(output_dir=temp_dir)

        exported_files = exporter.export_all_data(mock_client, "event-123")

        # Read summary file
        with open(exported_files["summary"], "r") as f:
            summary = json.load(f)

        assert summary["event_id"] == "event-123"
        assert summary["organization_id"] == "test-org-id"
        assert "export_timestamp" in summary
        assert "files_exported" in summary
