# HPDE Analytics CLI

[![CI](https://github.com/Homan13/hpde-analytics-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Homan13/hpde-analytics-cli/actions/workflows/ci.yml)
[![Python Version](https://img.shields.io/pypi/pyversions/hpde-analytics-cli)](https://pypi.org/project/hpde-analytics-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Data analysis and reporting tool that allows a user to connect to the MotorsportsReg (MSR) API to export data and create reports. This tool automates the extraction of event registration data from MSR and generates Excel reports for High Performance Drivers Education (HPDE) and Time Trials program analytics.

## Getting Started

These instructions will help you set up the project on your local machine for development and usage.

### Prerequisites

- Python 3.8 or higher
- MotorsportsReg OAuth consumer credentials
- pip (Python package installer)

### Installation

#### Option 1: Install from PyPI (Recommended)

```bash
pip install hpde-analytics-cli
```

#### Option 2: Install from source

1. Clone the repository:
   ```bash
   git clone https://github.com/Homan13/hpde-analytics-cli.git
   cd hpde-analytics-cli
   ```

2. Install the package:
   ```bash
   pip install -e .
   ```

### Configuration

1. Configure your credentials (choose one method):

   **Option A: Secure storage (Recommended)**
   ```bash
   hpde-analytics-cli --configure
   ```
   This stores your credentials securely in your system's keyring (macOS Keychain, Windows Credential Locker, or Linux Secret Service).

   **Option B: Environment file (Fallback)**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your MotorsportsReg OAuth credentials:
   ```
   MSR_CONSUMER_KEY=your_consumer_key_here
   MSR_CONSUMER_SECRET=your_consumer_secret_here
   MSR_BASE_URL=https://api.motorsportreg.com
   MSR_CALLBACK_PORT=8089
   ```

2. Check credential status (optional):
   ```bash
   hpde-analytics-cli --credential-status
   ```

3. Run initial authentication:
   ```bash
   hpde-analytics-cli --auth
   ```
   Follow the browser prompts to authorize the application.

## Usage

### Export Event Data

Export all event registration data (both raw and filtered formats):

```bash
hpde-analytics-cli --export \
  --org-id 11A1AAAA-2B2B-C333-4D4444444D4DD44D \
  --event-id <EVENT_ID> \
  --name HPDE_TT_1_2025
```

**Parameters:**
- `--org-id`: MSR organization ID (required)
- `--event-id`: MSR event ID (required)
- `--name`: Custom name for export folder (optional)
- `--output-dir`: Custom output directory (optional, defaults to `output/`)

### Generate Time Trials Report

Generate an Excel report from exported data:

```bash
hpde-analytics-cli --report \
  --export-dir output/HPDE_TT_1_2025_20260110_123456 \
  --name HPDE_TT_1_2025
```

**Parameters:**
- `--export-dir`: Path to exported data folder (required)
- `--name`: Custom name for report file (optional)
- `--report-file`: Specific output path for report (optional)

### Other Commands

```bash
# Configure or update API credentials (secure keyring storage)
hpde-analytics-cli --configure

# Check credential configuration status
hpde-analytics-cli --credential-status

# Re-authenticate if tokens expire
hpde-analytics-cli --auth

# Run field discovery to explore available data
hpde-analytics-cli --discover \
  --org-id <ORG_ID> \
  --event-id <EVENT_ID>

# Show all available options
hpde-analytics-cli --help
```

## Report Features

The generated Time Trials report includes:

- **Driver Information**: Name, email, member ID
- **Vehicle Details**: Year/make/model (combined), color, tire brand, vehicle number
- **Classification**: TT class and class grouping (Max, Sport, Tuner, Unlimited)
- **Participation Tracking**:
  - Days attended (Friday/Saturday/Sunday/combinations)
  - Day count (1 Day, 2 Days, 3 Days)
  - Instructor status (Yes/No)
  - AYCE participation (Time Trials + Advanced HPDE)
  - Participation type (TT Only, TT + Instructor, TT + AYCE, TT + Instructor + AYCE)

**Pivot-Ready Columns**: Class Group, Day Count, and Participation Type columns are optimized for Excel pivot table analysis to track registration trends.

## Project Structure

```
hpde-analytics-cli/
├── .env.example                  # Credential template
├── .gitignore                    # Git exclusions
├── pyproject.toml                # Package configuration
├── README.md                     # This file
├── hpde_analytics_cli/
│   ├── __init__.py
│   ├── main.py                   # CLI entry point
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── credentials.py        # Secure credential management
│   │   └── oauth.py              # OAuth 1.0a authentication
│   ├── api/
│   │   ├── __init__.py
│   │   └── client.py             # MSR API client
│   └── utils/
│       ├── __init__.py
│       ├── data_export.py        # Data export to JSON/CSV
│       ├── field_discovery.py    # API field enumeration
│       └── report_generator.py   # Excel report generation
├── output/                       # Export and report output (not in version control)
├── tokens/                       # OAuth access tokens (not in version control)
└── tests/                        # Unit tests
```

## Export Structure

Each export creates two data sets:

```
HPDE_TT_1_2025_20260110_123456/
├── raw_data/                     # Complete API responses (for reference)
│   ├── profile_full.json
│   ├── calendar_full.json
│   ├── calendar_full.csv
│   ├── entrylist_full.json
│   ├── entrylist_full.csv
│   ├── attendees_full.json
│   ├── attendees_full.csv
│   ├── assignments_full.json
│   └── assignments_full.csv
├── profile.json                  # Filtered data for Time Trials
├── calendar.json
├── entrylist.json
├── entrylist.csv
├── attendees.json
├── attendees.csv
├── assignments.json
├── assignments.csv
└── export_summary.json
```

## Running the tests

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest
```

## Deployment

This is a command-line tool designed to run locally. No deployment infrastructure is required.

**For scheduled/automated execution:**
- Consider setting up cron jobs (Linux/Mac) or Task Scheduler (Windows)
- Ensure OAuth tokens are refreshed as needed
- Store reports in a centralized location for team access

## Built With

* [Python 3](https://www.python.org/) - Programming language
* [requests](https://requests.readthedocs.io/) - HTTP library
* [requests-oauthlib](https://requests-oauthlib.readthedocs.io/) - OAuth 1.0a support
* [python-dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management
* [openpyxl](https://openpyxl.readthedocs.io/) - Excel file generation
* [keyring](https://pypi.org/project/keyring/) - Secure credential storage
* [MotorsportsReg API](https://www.motorsportreg.com/) - Event registration data source

## Contributing

_In Progress - Contribution guidelines to be developed_

## Versioning

This project uses [Semantic Versioning (SemVer)](https://semver.org/):
- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality in a backward compatible manner
- **PATCH** version for backward compatible bug fixes

**Current Version:** 2.0.0

## Authors

* **Kevin Homan**

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

* SCCA Washington DC Region for supporting the Time Trials program
* MotorsportsReg.com for providing API access
* WDCR HPDE program for combined event management

## Security Notes

**Important:**
- Never commit `.env` or `tokens/` directory to version control
- OAuth consumer secrets and access tokens must be kept confidential
- The `.gitignore` file is configured to exclude these sensitive files automatically
- Use `hpde-analytics-cli --configure` to store credentials securely in your system keyring

## Support

For issues or questions related to this tool, contact the WDCR Time Trials administration.

For MotorsportsReg API issues, refer to the [MotorsportsReg API documentation](https://www.motorsportreg.com/).
