"""
HPDE Analytics CLI: MotorsportsReg API integration for HPDE and Time Trials programs.

Entry point for the application.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from hpde_analytics_cli.api.client import create_client_from_oauth
from hpde_analytics_cli.auth.credentials import CredentialManager
from hpde_analytics_cli.auth.oauth import MSROAuth, create_oauth_from_env
from hpde_analytics_cli.utils.data_export import DataExporter
from hpde_analytics_cli.utils.field_discovery import run_field_discovery
from hpde_analytics_cli.utils.report_generator import generate_report


def print_profile(profile: Dict[str, Any]) -> None:
    """Print user profile information in a formatted way."""
    print("\n" + "-" * 40)
    print("User Profile")
    print("-" * 40)

    if "firstName" in profile or "lastName" in profile:
        name = f"{profile.get('firstName', '')} {profile.get('lastName', '')}".strip()
        print(f"  Name: {name}")

    if "email" in profile:
        print(f"  Email: {profile['email']}")

    if "id" in profile:
        print(f"  Profile ID: {profile['id']}")

    orgs = profile.get("organizations", [])
    if orgs:
        print(f"\n  Organizations ({len(orgs)}):")
        for org in orgs:
            org_name = org.get("name", "Unknown")
            org_id = org.get("id", "N/A")
            print(f"    - {org_name} (ID: {org_id})")
    else:
        print("\n  No organizations found")

    print("-" * 40)


def run_authentication(oauth: MSROAuth, verbose: bool = False) -> Dict[str, Any]:
    """Run the authentication flow and return profile data."""
    profile = oauth.run_auth_flow()

    if verbose:
        print("\nFull profile response:")
        print(json.dumps(profile, indent=2))

    print_profile(profile)
    return profile


def fetch_api_data(
    client: Any, event_id: Optional[str] = None, verbose: bool = False
) -> Dict[str, Any]:
    """Fetch data from all API endpoints."""
    print("\n" + "=" * 60)
    print("Fetching API Data")
    print("=" * 60)

    results = client.get_all_endpoint_data(event_id=event_id)

    if verbose:
        print("\n" + "-" * 40)
        print("Raw API Responses")
        print("-" * 40)
        for endpoint, data in results.items():
            print(f"\n[{endpoint}]")
            print(json.dumps(data, indent=2, default=str)[:2000])
            if len(json.dumps(data, default=str)) > 2000:
                print("... (truncated)")

    return results


def handle_discover(oauth, args) -> None:
    """Handle field discovery command."""
    print("Running field discovery...")
    if not oauth.has_valid_tokens():
        print("Error: No valid tokens found. Run with --auth first.")
        sys.exit(1)

    profile = oauth.validate_connection()
    print_profile(profile)

    client = create_client_from_oauth(oauth, organization_id=args.org_id)
    api_data = fetch_api_data(client, event_id=args.event_id, verbose=args.verbose)

    output_path = Path(__file__).parent.parent / args.output
    run_field_discovery(api_data, output_path=str(output_path), verbose=args.verbose)


def handle_report(args) -> None:
    """Handle report generation command."""
    print("Generating Time Trials report...")

    if not args.export_dir:
        print("Error: --export-dir is required for report generation.")
        print("Usage: python -m src.main --report --export-dir <EXPORT_DIR>")
        sys.exit(1)

    export_dir = Path(args.export_dir)
    if not export_dir.exists():
        print(f"Error: Export directory not found: {export_dir}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("Generating Report")
    print("=" * 60)

    report_output = args.report_file
    if not report_output and args.name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_output = str(export_dir / f"{args.name}_{timestamp}.xlsx")

    report_path = generate_report(
        export_dir=str(export_dir),
        output_path=report_output,
        verbose=True,
    )

    print("\n" + "=" * 60)
    print("Report Complete")
    print("=" * 60)
    print(f"\nReport saved to: {report_path}")


def handle_export(oauth, args) -> None:
    """Handle data export command."""
    print("Exporting event data...")
    if not oauth.has_valid_tokens():
        print("Error: No valid tokens found. Run with --auth first.")
        sys.exit(1)

    if not args.event_id:
        print("Error: --event-id is required for export.")
        print("Usage: python -m src.main --export --event-id <EVENT_ID>")
        sys.exit(1)

    profile = oauth.validate_connection()
    print_profile(profile)

    client = create_client_from_oauth(oauth, organization_id=args.org_id)

    print("\n" + "=" * 60)
    print("Exporting Data")
    print("=" * 60)

    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = Path(__file__).parent.parent / "output"

    exporter = DataExporter(output_dir=str(output_dir), name=args.name)
    exported_files = exporter.export_all_data(
        client,
        event_id=args.event_id,
        verbose=True,
    )

    print("\n" + "=" * 60)
    print("Export Complete")
    print("=" * 60)
    if args.name:
        folder_name = f"{args.name}_{exporter.export_timestamp}"
    else:
        folder_name = f"export_{exporter.export_timestamp}"
    print(f"\nFiles exported to: {output_dir / folder_name}")
    print("\nExported files:")
    for file_name, path in exported_files.items():
        print(f"  - {file_name}: {path}")


def handle_auth(oauth, args) -> None:
    """Handle authentication-only command."""
    print("Running authentication flow...")
    run_authentication(oauth, verbose=args.verbose)


def handle_full_flow(oauth, args) -> None:
    """Handle full flow (auth + discovery)."""
    print("Running full flow (authentication + field discovery)...")
    run_authentication(oauth, verbose=args.verbose)

    client = create_client_from_oauth(oauth, organization_id=args.org_id)
    api_data = fetch_api_data(client, event_id=args.event_id, verbose=args.verbose)

    output_path = Path(__file__).parent.parent / args.output
    run_field_discovery(api_data, output_path=str(output_path), verbose=args.verbose)


def load_environment(verbose: bool = False) -> None:
    """Load environment variables from .env file if it exists."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        if verbose:
            print(f"Loaded environment from {env_path}")


def handle_credential_commands(args) -> bool:
    """Handle credential management commands. Returns True if handled."""
    credential_manager = CredentialManager()

    if args.configure:
        success = credential_manager.configure_interactive()
        sys.exit(0 if success else 1)

    if args.credential_status:
        credential_manager.show_status()
        sys.exit(0)

    return False


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="hpde-analytics-cli",
        description="HPDE Analytics - MotorsportsReg API integration for HPDE and Time Trials programs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hpde-analytics-cli --configure      # Set up API credentials securely
  hpde-analytics-cli --auth           # Authentication only
  hpde-analytics-cli --export         # Export all data (JSON + CSV)
  hpde-analytics-cli --report         # Generate TT report from exported data
  hpde-analytics-cli --verbose        # Enable verbose output
        """,
    )

    parser.add_argument(
        "--configure",
        action="store_true",
        help="Configure API credentials (stores securely in system keyring)",
    )
    parser.add_argument(
        "--credential-status",
        action="store_true",
        help="Show current credential configuration status",
    )
    parser.add_argument(
        "--auth",
        action="store_true",
        help="Run authentication flow only",
    )
    parser.add_argument(
        "--discover",
        action="store_true",
        help="Run field discovery only (requires existing auth)",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Export all event data to JSON and CSV files",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate Time Trials report from exported data (requires --export-dir)",
    )
    parser.add_argument(
        "--export-dir",
        type=str,
        help="Directory containing exported CSV files (for --report)",
    )
    parser.add_argument(
        "--report-file",
        type=str,
        help="Output path for the report file (for --report, default: saves to export-dir)",
    )
    parser.add_argument(
        "--event-id",
        type=str,
        help="Specific event ID to query for field discovery",
    )
    parser.add_argument(
        "--org-id",
        type=str,
        help="Organization ID to use for API requests (overrides default)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output/field_inventory.json",
        help="Output file for field inventory (default: output/field_inventory.json)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory for export output files (default: output/ in project dir)",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Custom name for export folder or report file (e.g., 'HPDE_TT_1_2025')",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    return parser


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    load_environment(verbose=args.verbose)
    handle_credential_commands(args)

    try:
        oauth = create_oauth_from_env()

        if args.auth:
            handle_auth(oauth, args)
        elif args.discover:
            handle_discover(oauth, args)
        elif args.report:
            handle_report(args)
        elif args.export:
            handle_export(oauth, args)
        else:
            handle_full_flow(oauth, args)

        print("\nDone!")

    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
