"""
Tests for the report generator module.
"""

import csv
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from hpde_analytics_cli.utils.report_generator import (
    ReportGenerator,
    generate_report,
)


class TestReportGenerator:
    """Tests for ReportGenerator class."""

    @pytest.fixture
    def temp_export_dir(self):
        """Create a temporary export directory with test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test entrylist.csv
            entrylist_data = [
                {
                    "firstName": "John",
                    "lastName": "Doe",
                    "segment": "Saturday Time Trials",
                    "group": "Time Trials - Sport 1",
                    "class": "Sport 1",
                    "make": "Mazda",
                    "model": "MX-5",
                    "year": "2020",
                    "vehicleNumber": "42",
                    "color": "Red",
                    "sponsor": "ACME Racing",
                },
                {
                    "firstName": "John",
                    "lastName": "Doe",
                    "segment": "Sunday Time Trials",
                    "group": "Time Trials - Sport 1",
                    "class": "Sport 1",
                    "make": "Mazda",
                    "model": "MX-5",
                    "year": "2020",
                    "vehicleNumber": "42",
                    "color": "Red",
                    "sponsor": "ACME Racing",
                },
                {
                    "firstName": "Jane",
                    "lastName": "Smith",
                    "segment": "Saturday Time Trials",
                    "group": "Time Trials - Max 2",
                    "class": "Max 2",
                    "make": "Porsche",
                    "model": "911",
                    "year": "2019",
                    "vehicleNumber": "99",
                    "color": "White",
                    "sponsor": "",
                },
                {
                    "firstName": "Jane",
                    "lastName": "Smith",
                    "segment": "Saturday Advanced HPDE",
                    "group": "Advanced HPDE",
                    "class": "",
                    "make": "Porsche",
                    "model": "911",
                    "year": "2019",
                    "vehicleNumber": "99",
                    "color": "White",
                    "sponsor": "",
                },
                {
                    "firstName": "Bob",
                    "lastName": "Jones",
                    "segment": "Saturday Time Trials",
                    "group": "Time Trials - Tuner 3",
                    "class": "Tuner 3",
                    "make": "Honda",
                    "model": "Civic",
                    "year": "2018",
                    "vehicleNumber": "7",
                    "color": "Blue",
                    "sponsor": "",
                },
                {
                    "firstName": "Bob",
                    "lastName": "Jones",
                    "segment": "Saturday Instructing",
                    "group": "Instructing",
                    "class": "",
                    "make": "",
                    "model": "",
                    "year": "",
                    "vehicleNumber": "",
                    "color": "",
                    "sponsor": "",
                },
                {
                    "firstName": "Worker",
                    "lastName": "Only",
                    "segment": "Saturday Workers",
                    "group": "Workers",
                    "class": "",
                    "make": "",
                    "model": "",
                    "year": "",
                    "vehicleNumber": "",
                    "color": "",
                    "sponsor": "",
                },
            ]

            entrylist_path = os.path.join(tmpdir, "entrylist.csv")
            with open(entrylist_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=entrylist_data[0].keys())
                writer.writeheader()
                writer.writerows(entrylist_data)

            # Create test attendees.csv
            attendees_data = [
                {
                    "firstName": "John",
                    "lastName": "Doe",
                    "email": "john@example.com",
                    "memberId": "M001",
                    "status": "Confirmed",
                },
                {
                    "firstName": "Jane",
                    "lastName": "Smith",
                    "email": "jane@example.com",
                    "memberId": "M002",
                    "status": "Confirmed",
                },
                {
                    "firstName": "Bob",
                    "lastName": "Jones",
                    "email": "bob@example.com",
                    "memberId": "M003",
                    "status": "Pending",
                },
                {
                    "firstName": "Worker",
                    "lastName": "Only",
                    "email": "worker@example.com",
                    "memberId": "M004",
                    "status": "Confirmed",
                },
            ]

            attendees_path = os.path.join(tmpdir, "attendees.csv")
            with open(attendees_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=attendees_data[0].keys())
                writer.writeheader()
                writer.writerows(attendees_data)

            # Create test assignments.json
            assignments_data = {
                "assignments": [
                    {
                        "firstName": "John",
                        "lastName": "Doe",
                        "group": "Time Trials - Sport 1",
                        "tireBrand": "Hoosier",
                    },
                    {
                        "firstName": "Jane",
                        "lastName": "Smith",
                        "group": "Time Trials - Max 2",
                        "tireBrand": "Michelin",
                    },
                    {
                        "firstName": "Bob",
                        "lastName": "Jones",
                        "group": "Time Trials - Tuner 3",
                        "tireBrand": "BFGoodrich",
                    },
                ]
            }

            assignments_path = os.path.join(tmpdir, "assignments.json")
            with open(assignments_path, "w", encoding="utf-8") as f:
                json.dump(assignments_data, f)

            yield tmpdir

    def test_init(self, temp_export_dir):
        """Test ReportGenerator initialization."""
        generator = ReportGenerator(temp_export_dir)
        assert generator.export_dir == temp_export_dir
        assert generator.entrylist_file.endswith("entrylist.csv")
        assert generator.attendees_file.endswith("attendees.csv")

    def test_get_driver_key(self, temp_export_dir):
        """Test driver key generation."""
        generator = ReportGenerator(temp_export_dir)

        key = generator._get_driver_key({"firstName": "John", "lastName": "Doe"})
        assert key == "john|doe"

        # Test with missing values
        key = generator._get_driver_key({"firstName": "", "lastName": "Doe"})
        assert key == "|doe"

    def test_parse_segment_friday(self, temp_export_dir):
        """Test parsing Friday segment."""
        generator = ReportGenerator(temp_export_dir)
        assert generator._parse_segment("Friday Time Trials") == "Friday"

    def test_parse_segment_saturday(self, temp_export_dir):
        """Test parsing Saturday segment."""
        generator = ReportGenerator(temp_export_dir)
        assert generator._parse_segment("Saturday Time Trials") == "Saturday"

    def test_parse_segment_sunday(self, temp_export_dir):
        """Test parsing Sunday segment."""
        generator = ReportGenerator(temp_export_dir)
        assert generator._parse_segment("Sunday HPDE") == "Sunday"

    def test_parse_segment_empty(self, temp_export_dir):
        """Test parsing empty segment."""
        generator = ReportGenerator(temp_export_dir)
        assert generator._parse_segment("") is None
        assert generator._parse_segment(None) is None

    def test_is_time_trials(self, temp_export_dir):
        """Test Time Trials detection."""
        generator = ReportGenerator(temp_export_dir)
        assert generator._is_time_trials("Time Trials - Sport 1") is True
        assert generator._is_time_trials("HPDE") is False
        assert generator._is_time_trials("") is False
        assert generator._is_time_trials(None) is False

    def test_is_instructor(self, temp_export_dir):
        """Test Instructor detection."""
        generator = ReportGenerator(temp_export_dir)
        assert generator._is_instructor("Instructing") is True
        assert generator._is_instructor("Time Trials") is False
        assert generator._is_instructor("") is False

    def test_is_advanced_hpde(self, temp_export_dir):
        """Test Advanced HPDE detection."""
        generator = ReportGenerator(temp_export_dir)
        assert generator._is_advanced_hpde("Advanced HPDE") is True
        assert generator._is_advanced_hpde("Beginner HPDE") is False
        assert generator._is_advanced_hpde("") is False

    def test_is_worker_only(self, temp_export_dir):
        """Test worker-only detection."""
        generator = ReportGenerator(temp_export_dir)
        assert generator._is_worker_only("Saturday Workers") is True
        assert generator._is_worker_only("Saturday Time Trials") is False
        assert generator._is_worker_only("") is True
        assert generator._is_worker_only(None) is True

    def test_get_participation_type(self, temp_export_dir):
        """Test participation type categorization."""
        generator = ReportGenerator(temp_export_dir)

        assert generator._get_participation_type(True, True) == "TT + Instructor + AYCE"
        assert generator._get_participation_type(True, False) == "TT + Instructor"
        assert generator._get_participation_type(False, True) == "TT + AYCE"
        assert generator._get_participation_type(False, False) == "TT Only"

    def test_get_day_count(self, temp_export_dir):
        """Test day count categorization."""
        generator = ReportGenerator(temp_export_dir)

        assert generator._get_day_count(1) == "1 Day"
        assert generator._get_day_count(2) == "2 Days"
        assert generator._get_day_count(3) == "3 Days"
        assert generator._get_day_count(0) == ""

    def test_get_class_group(self, temp_export_dir):
        """Test class group categorization."""
        generator = ReportGenerator(temp_export_dir)

        assert generator._get_class_group("Max 1") == "Max"
        assert generator._get_class_group("Max 2") == "Max"
        assert generator._get_class_group("Sport 1") == "Sport"
        assert generator._get_class_group("Sport 4") == "Sport"
        assert generator._get_class_group("Tuner 1") == "Tuner"
        assert generator._get_class_group("Tuner 3") == "Tuner"
        assert generator._get_class_group("Unlimited 1") == "Unlimited"
        assert generator._get_class_group("Unknown Class") == "Other"
        assert generator._get_class_group("") == "Other"
        assert generator._get_class_group(None) == "Other"

    def test_generate_tt_report(self, temp_export_dir):
        """Test generating Time Trials report."""
        generator = ReportGenerator(temp_export_dir)
        output_path = os.path.join(temp_export_dir, "test_report.xlsx")

        report_path, driver_count = generator.generate_tt_report(output_path)

        # Verify file was created
        assert os.path.exists(report_path)
        assert report_path == output_path

        # Verify driver count (3 TT participants, worker excluded)
        assert driver_count == 3

    def test_generate_tt_report_excludes_workers(self, temp_export_dir):
        """Test that worker-only entries are excluded from report."""
        generator = ReportGenerator(temp_export_dir)
        output_path = os.path.join(temp_export_dir, "test_report.xlsx")

        report_path, driver_count = generator.generate_tt_report(output_path)

        # Worker Only should not be included
        assert driver_count == 3

    def test_generate_tt_report_deduplicates_drivers(self, temp_export_dir):
        """Test that drivers are deduplicated in report."""
        generator = ReportGenerator(temp_export_dir)
        output_path = os.path.join(temp_export_dir, "test_report.xlsx")

        report_path, driver_count = generator.generate_tt_report(output_path)

        # John Doe appears twice but should be counted once
        assert driver_count == 3

    def test_generate_tt_report_default_output_path(self, temp_export_dir):
        """Test report generation with default output path."""
        generator = ReportGenerator(temp_export_dir)

        report_path, driver_count = generator.generate_tt_report()

        # Should be in export dir with timestamp
        assert report_path.startswith(temp_export_dir)
        assert "tt_report_" in report_path
        assert report_path.endswith(".xlsx")

    @patch("hpde_analytics_cli.utils.report_generator.OPENPYXL_AVAILABLE", False)
    def test_generate_tt_report_without_openpyxl(self, temp_export_dir):
        """Test that ImportError is raised when openpyxl not available."""
        generator = ReportGenerator(temp_export_dir)

        with pytest.raises(ImportError) as exc_info:
            generator.generate_tt_report()

        assert "openpyxl" in str(exc_info.value)


class TestGenerateReport:
    """Tests for generate_report function."""

    @pytest.fixture
    def temp_export_dir(self):
        """Create a minimal export directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal test data
            entrylist_data = [
                {
                    "firstName": "Test",
                    "lastName": "Driver",
                    "segment": "Saturday Time Trials",
                    "group": "Time Trials - Sport 1",
                    "class": "Sport 1",
                    "make": "Test",
                    "model": "Car",
                    "year": "2020",
                    "vehicleNumber": "1",
                    "color": "Red",
                    "sponsor": "",
                },
            ]

            with open(os.path.join(tmpdir, "entrylist.csv"), "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=entrylist_data[0].keys())
                writer.writeheader()
                writer.writerows(entrylist_data)

            with open(os.path.join(tmpdir, "attendees.csv"), "w", newline="") as f:
                writer = csv.DictWriter(
                    f, fieldnames=["firstName", "lastName", "email", "memberId", "status"]
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "firstName": "Test",
                        "lastName": "Driver",
                        "email": "test@example.com",
                        "memberId": "M001",
                        "status": "Confirmed",
                    }
                )

            yield tmpdir

    def test_generate_report_basic(self, temp_export_dir):
        """Test basic report generation via function."""
        output_path = os.path.join(temp_export_dir, "output.xlsx")

        report_path = generate_report(temp_export_dir, output_path)

        assert os.path.exists(report_path)

    def test_generate_report_verbose(self, temp_export_dir, capsys):
        """Test report generation with verbose output."""
        output_path = os.path.join(temp_export_dir, "output.xlsx")

        generate_report(temp_export_dir, output_path, verbose=True)

        captured = capsys.readouterr()
        assert "Generating" in captured.out
        assert "Report generated" in captured.out
