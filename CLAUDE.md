# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A CLI that pulls event registration data from the MotorsportsReg (MSR) API and turns it
into Excel reports for the SCCA Washington DC Region HPDE / Time Trials program. It also
has a side workflow that back-fills student emails into a Google Sheet from MSR data.

`CODE_REVIEW.md` holds the current remediation backlog with file:line locations. Check it
before starting work — a bug you are about to hit may already be catalogued there.

## Commands

```bash
# Setup (there is no committed virtualenv)
pip install -e ".[dev]"

# Tests. pyproject sets addopts, so bare `pytest` already runs -v with coverage.
pytest
pytest tests/test_report_generator.py                                  # one module
pytest tests/test_report_generator.py::TestReportGenerator::test_get_class_group
pytest -k "driver_key" --no-cov                                        # by name, no coverage

# The exact checks CI runs, in CI's order
black --check --diff hpde_analytics_cli tests
isort --check-only --diff hpde_analytics_cli tests
flake8 hpde_analytics_cli tests --count --select=E9,F63,F7,F82 --show-source --statistics
mypy hpde_analytics_cli --ignore-missing-imports
bandit -r hpde_analytics_cli -ll

pre-commit run --all-files
```

Which CI checks are hard gates: `black`, `isort`, the `E9,F63,F7,F82` flake8 pass, `mypy`,
`bandit`, and `pytest` on Python 3.9-3.14. The second flake8 invocation runs `--exit-zero`
and `safety check` ends in `|| true`, so both are advisory only — unused imports and known
CVEs will not fail the build.

`ci.yml` installs **unpinned** `black`, while `.pre-commit-config.yaml` pins `24.10.0`.
A newer Black than your local one can turn CI red on formatting you never see. Run
`black --check` against a current Black before pushing.

## Running it

```bash
hpde-analytics-cli --configure          # store MSR consumer key/secret in the OS keyring
hpde-analytics-cli --auth               # three-legged OAuth 1.0a, opens a browser
hpde-analytics-cli --export --org-id <ORG> --event-id <EVENT> --name HPDE_TT_1_2025
hpde-analytics-cli --report --export-dir output/HPDE_TT_1_2025_<timestamp>
```

`--export` and `--report` are separate steps on purpose: export hits the network, report is
pure local file processing and can be re-run freely while iterating on report logic.

## Architecture

### Command dispatch

`main.py` is a flat argparse CLI — no subcommands, just boolean flags checked in an
if/elif chain in `main()`. Each flag maps to a `handle_*` function. Adding a command means
adding a flag, a handler, and a branch.

`main()` constructs the OAuth handler *before* dispatching, so every command currently
requires MSR credentials even when it never touches the network (see `CODE_REVIEW.md` #3).

### MSR API conventions, implemented in `api/client.py`

Two behaviors are applied centrally in `MSRClient._request` and must not be duplicated in
callers:

- Endpoints get a `.json` suffix appended automatically. Pass `/rest/me`, not `/rest/me.json`.
- MSR wraps every response in `{"response": {...}}`. `_request` unwraps one level.

`auth/oauth.py:validate_connection` re-implements that unwrapping independently because it
predates the client and does not use it. If you change the envelope handling, change both.

Retries cover 5xx and transport exceptions with linear backoff. 4xx raises `APIError`
immediately and is never retried.

### The export → report contract

This is the most important thing to understand, and it is implicit — there is no schema,
no shared model, and nothing validates it.

`--export` (`utils/data_export.py`) writes a timestamped folder containing two tiers:
complete API responses under `raw_data/`, and filtered copies at the top level.
`--report` (`utils/report_generator.py`) then reads three files from that folder **by
hardcoded filename**: `entrylist.csv`, `attendees.csv`, `assignments.json`.

Renaming an export file, or changing which response key becomes which CSV, silently breaks
report generation with a `FileNotFoundError` at a distance.

Which source supplies which field is also load-bearing and non-obvious:

| Data | Source file | Why |
| --- | --- | --- |
| Run group, segment, class, vehicle year/make/model, color, vehicle number, sponsor | `entrylist.csv` | Per-registration rows |
| Email, memberId, status | `attendees.csv` | Not present on entrylist rows |
| Tire brand | `assignments.json` | Only the assignments endpoint returns it |

Note that both the `entrylist` and `assignments` endpoints return their rows under a
JSON key named `assignments`. That is MSR's naming, not a bug.

`DataExporter` reassigns `self.output_dir` mid-run to switch between the `raw_data/`
subfolder and the filtered folder, restoring it in a `finally`. Methods called during
export write relative to whatever that field currently holds.

### Driver identity

Every join across the three data sources uses the same key, built by
`ReportGenerator._get_driver_key`: `firstname|lastname`, lowercased and stripped. The same
construction is duplicated in `integrations/email_populator.py`.

There is no ID-based matching. Two registrants sharing a name merge into one row, and any
spelling drift between endpoints silently blanks that driver's email and member ID.
`CODE_REVIEW.md` #4 covers this; `memberId` is the intended fix but its availability on
both endpoints is unconfirmed.

### Report generation pipeline

`generate_tt_report` runs a fixed sequence: skip worker-only entries → group remaining
entries by driver key, accumulating per-day participation into sets → filter to drivers
with `is_tt` → enrich from the attendee and tire lookups → sort by last name → write one
styled worksheet.

A driver appears in multiple entrylist rows (one per day, per run group). The grouping step
is what collapses those into a single row with a `days_tt` set.

### Program vocabulary is hardcoded, and only in the report layer

`report_generator.py` matches WDCR's domain language as lowercase substrings: run groups
(`"time trials"`, `"instructing"`, `"advanced hpde"`), worker entries (`"workers"`), days
(Friday/Saturday/Sunday), and class group prefixes (Max / Sport / Tuner / Unlimited). The
17 output columns assume this structure.

Everything below the report layer — OAuth, `MSRClient`, `DataExporter` — is already
organization-agnostic, because MSR is the integration boundary and every sanctioning body
registers through the same API. The intended direction is to generalize report generation
to any MSR-sanctioned program: other SCCA regions first, then NASA / PCA / BMW CCA.

That work is staged in `CODE_REVIEW.md` #22 and intentionally not started. Two rules when
touching this area: keep new program-specific logic confined to the report layer rather
than pushing it down into the client or exporter, and do not build the profile/config
system until a concrete second program exists to validate it against.

### Credentials and tokens are two separate things

Consumer key/secret resolve through `auth/credentials.py`: system keyring first, then
environment variables, then an error. Keyring is the documented path and `--configure`
writes to it.

OAuth *access* tokens are separate, stored as JSON on disk by `auth/oauth.py`, and loaded
automatically in `MSROAuth.__init__`. A 401 during `validate_connection` deletes the token
file and forces re-auth.

Several paths — the `.env` file, the default output directory, and the token file — are
derived from `__file__` and so resolve into `site-packages` when the package is installed
rather than run from a checkout. This is a known bug, catalogued as `CODE_REVIEW.md` #2.
Keep it in mind before concluding that a config file "is not being read."

### Optional imports

`openpyxl` (report generation) and `gspread` (Sheets) are imported in `try`/`except
ImportError` blocks guarded by `OPENPYXL_AVAILABLE` / `GSPREAD_AVAILABLE` flags, even
though both are hard dependencies in `pyproject.toml`. The tests exercise the unavailable
branch, so keep the pattern when touching those modules.

## Releases

Versioning is driven by `release-please` from **conventional commit messages** on `main`
(`fix:` → patch, `feat:` → minor, `!` or `BREAKING CHANGE:` → major). Non-conforming
commit subjects are skipped in the changelog and will not trigger a release.

**Never hand-edit a version string anywhere in this repo.** `.release-please-manifest.json`
is authoritative; `pyproject.toml` carries an `# x-release-please-version` annotation so
the automation updates it; `__init__.py` reads `__version__` from installed package
metadata. Nothing else states a version.

This rule is not stylistic. Editing the manifest backwards does *not* remove
breaking-change commits from the range release-please computes over, so it re-detects them
and issues another major bump. Repeated attempts to do this are what took the project from
2.0.0 to 6.0.0 with no real breaking changes in between — see the note in `CHANGELOG.md` at
the 2.0.0 boundary and `CODE_REVIEW.md` #11. By strict semver this is about a 2.1.x
codebase; 6.x was kept because PyPI numbers are permanent and resolvers prefer the highest.

`publish.yml` fails the build if the release tag and `pyproject.toml` disagree. If that
guard trips, the fix is in the release-please configuration, not in `pyproject.toml`.

Publishing to PyPI uses trusted publishing and fires on GitHub release `published`.
`release-please-config.json` sets `bump-minor-pre-major` and `bump-patch-for-minor-pre-major`,
both of which are **inert** above 1.0.0 and have no effect on this project.
