# Code Review — Remediation Backlog

Review date: 2026-10-06
Reviewed at: commit `7dd9c5e` (v6.0.4, branch `main`)

Findings from a full read of the codebase plus a local run of every check CI runs
(`pytest`, `black`, `isort`, `flake8`, `mypy`, `bandit`) and a verification install
from a built wheel into a clean virtualenv.

**Baseline at review time:** 174 tests passing, 56% coverage, mypy clean, bandit clean,
`black --check` failing (now fixed — see item 1).

---

## Status legend

| Mark | Meaning |
| --- | --- |
| `[x]` | Done |
| `[ ]` | Open |

Priorities assume a single operator (the author) installing from PyPI, with a UI
version planned later. Items marked **UI-relevant** become more important once a
second consumer of this package exists.

---

## P0 — Blocking

### 1. `black --check` fails, CI lint job is red on `main`

- [x] **Fixed 2026-10-06**

**Location:** `hpde_analytics_cli/integrations/google_sheets.py:10-14`

**Problem:** Commit `30dc76e` ("resolve open CodeQL security alerts") removed the
`Credentials` import from the `try:` block and with it the blank line Black requires
after an import inside a compound statement. `ci.yml` installs unpinned `black`, so
the lint job fails on every push and PR.

**Fix applied:**

```python
try:
    import gspread

    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
```

**Follow-up:** `.pre-commit-config.yaml` pins `black` at `24.10.0` while CI installs
the latest release. Pinning both to the same version — or letting CI use the
pre-commit config — prevents this class of drift from recurring.

---

## P1 — Correctness

### 2. Installed-from-PyPI paths resolve into `site-packages`

- [ ] Open

**Locations:**

| File:line | Computes | Resolves to (wheel install) |
| --- | --- | --- |
| `main.py:292` | `.env` path | `site-packages/.env` |
| `main.py:169` | default output dir | `site-packages/output/` |
| `main.py:106`, `main.py:286` | field inventory output | `site-packages/output/field_inventory.json` |
| `oauth.py:150` | OAuth token file | `site-packages/tokens/access_token.json` |

**Problem:** All four derive paths from `__file__`, which assumes execution from a
source checkout. Verified empirically against a non-editable install in a clean venv.
Consequences on the `pip install hpde-analytics-cli` path the README recommends first:

- The user's `.env` is never loaded. `MSR_BASE_URL`, `MSR_CALLBACK_PORT`, and
  `GOOGLE_SERVICE_ACCOUNT_KEY` silently fall back to defaults. Masked today because
  `--configure`/keyring is the primary credential path.
- OAuth access tokens are written into `site-packages`, so they are destroyed on every
  upgrade or reinstall, and land in a shared system directory if installed outside a venv.
- Exports land in `site-packages/output/`, where they will not be found.

**Fix:**

- `.env` → `Path.cwd() / ".env"`, or `dotenv.find_dotenv()` to walk up from cwd.
- Output defaults → `Path.cwd() / "output"`.
- Token file → a per-user config dir, e.g. `~/.config/hpde-analytics-cli/` via
  `platformdirs.user_config_dir()`, or hand-rolled to avoid the extra dependency.
  Migrate an existing token file on first run if one is found at the old location.

**Also:** `.env.example` is not included in the wheel, so the README's
`cp .env.example .env` step only works from a clone. Either add it to the sdist/wheel
via `MANIFEST.in` / `package-data`, or have `--configure` offer to write a starter `.env`.

**UI-relevant.** A UI build will be a separate install and will hit all four of these.

### 3. `--report` requires MSR credentials it never uses

- [ ] Open

**Location:** `main.py:458-472`

**Problem:** `create_oauth_from_env()` runs before command dispatch, so
`hpde-analytics-cli --report --export-dir X` — which only reads local CSV files — exits 1
with `Configuration error: No credentials found` on any machine without credentials.
Verified. The same applies to `--populate-emails --export-dir`, which was explicitly
designed to work without an API call.

**Fix:** Construct the OAuth handler inside the branches that need it
(`--auth`, `--discover`, `--export`, full flow, and `--populate-emails` only on the
`--event-id` path), not ahead of the dispatch chain.

### 4. Drivers are merged on name alone

- [ ] Open

**Locations:** `report_generator.py:53-57` (`_get_driver_key`),
`email_populator.py:41-71` (`build_email_lookup`)

**Problem:** The driver key is `firstname|lastname`, lowercased. Two registrants with
the same name silently merge into a single report row, under-counting participation.
Any spelling difference between the entrylist and attendees responses causes a lookup
miss, silently blanking email / memberId / status for that driver.

This is the finding with the most direct impact on the numbers the tool exists to produce.

**Fix:** Key on `memberId` where present, falling back to the normalized name.
Report drivers that fell back, so collisions become visible rather than silent.

**Prerequisite:** Confirm whether MSR returns a populated `memberId` on both the
entrylist and attendees responses. Run an export against a real event and check both
CSVs for column presence and fill rate before committing to the design.

### 5. Export failures are silent

- [ ] Open

**Location:** `data_export.py:206-209`, `data_export.py:331-394`

**Problem:** `_export_endpoint_data` catches every exception per endpoint and returns
`None`; `_fetch_raw_data` skips falsy results; `export_all_data` writes a summary and
returns normally regardless. If the API is unreachable, the CLI prints "Export Complete"
with an empty file list and exits 0. The failure only surfaces later as a
`FileNotFoundError` from `--report`.

**Fix:** Treat a missing `entrylist` or `attendees` as fatal, since the report cannot be
produced without them. Record per-endpoint failures in `export_summary.json` and exit
non-zero when a required endpoint failed.

### 6. All-caps column headers are misread as spreadsheet column letters

- [ ] Open

**Location:** `google_sheets.py:115`

**Problem:** `if column_identifier.isalpha() and column_identifier.isupper()` treats any
all-uppercase alphabetic string as a column letter. `--name-column NAME` is parsed as
column index 254,308 instead of searching for the header `NAME`.

**Fix:** Search the header row first and fall back to letter interpretation only on a
miss, or cap the letter heuristic at 1-3 characters. Document the precedence either way.

---

## P2 — Security hardening

All four are localhost-scoped and low severity in the current single-operator setup,
but they are cheap to fix and `codeql.yml` runs `security-extended`.

### 7. Unescaped interpolation into the OAuth callback HTML response

- [ ] Open

**Location:** `auth/oauth.py:85-105`

**Problem:** `oauth_error`, `error_description`, and the full `params` dict are
interpolated into the HTML response without escaping — reflected XSS on the local
callback page. Attacker-controlled only via a crafted link the operator clicks during
an active auth flow, so real-world risk is low, but this is exactly what CodeQL's
extended query set flags.

**Fix:** `html.escape()` every interpolated value.

### 8. Token file written with world-readable permissions

- [ ] Open

**Location:** `auth/oauth.py:192-206` (`_save_tokens`)

**Problem:** Plain `open(..., "w")` leaves the file at 0644 after umask. The file holds
the OAuth access token and token secret.

**Fix:** `os.chmod(self.token_file, 0o600)` after writing, and `0o700` on the containing
directory when it is created.

### 9. Callback wait can hang for ~50 minutes

- [ ] Open

**Location:** `auth/oauth.py:395-411` (`_wait_for_callback`)

**Problem:** Up to 10 iterations of `server.handle_request()` with `server.timeout = 300`
gives a worst case around 50 minutes with no output.

**Fix:** Use a single wall-clock deadline (e.g. 300s total) across the loop rather than a
per-request timeout, and print remaining time on each non-callback request.

### 10. Callback does not verify the returned `oauth_token`

- [ ] Open

**Location:** `auth/oauth.py:61-62`

**Problem:** `OAuthCallbackHandler.oauth_token` is captured but never compared against
`self.request_token`, so a callback carrying a different request token is accepted.

**Fix:** Compare the returned `oauth_token` to the stored request token and reject on
mismatch.

---

## P3 — Correctness of metadata and release plumbing

### 11. Version is declared in five places with five different values

- [ ] Open

| Source | Value at review time |
| --- | --- |
| `.release-please-manifest.json` | 6.0.4 (authoritative) |
| `pyproject.toml:8` | 6.0.1 |
| `hpde_analytics_cli/__init__.py:3` | 1.0.0 |
| `README.md` "Current Version" | 2.0.0 |
| `sonar-project.properties` | 0.1.0 |

**Root cause for `pyproject.toml`:** release-please's `generic` extra-file updater needs
an `# x-release-please-version` annotation comment on the line it should bump. Without it
the file is skipped — which is why `publish.yml` carries a `sed` workaround.

**Fix:**

1. Annotate the version line in `pyproject.toml`:
   ```toml
   version = "6.0.4"  # x-release-please-version
   ```
   Then drop the `sed` step from `publish.yml`.
2. Derive `__version__` from installed metadata instead of hardcoding it:
   ```python
   from importlib.metadata import version

   __version__ = version("hpde-analytics-cli")
   ```
3. Remove the "Current Version" line from `README.md`; link to the Releases page instead.
4. Drop `sonar.projectVersion` from `sonar-project.properties` (SonarCloud does not
   require it) or wire it to the manifest.
5. Add a `--version` flag to the CLI, which it currently lacks.

### 12. `sonar-project.properties` Python versions are stale

- [ ] Open

**Problem:** Declares `sonar.python.version=3.8,3.9,3.10,3.11,3.12`. 3.8 was dropped in
v6.0.0; 3.13 and 3.14 are in the CI test matrix but missing here.

**Fix:** `sonar.python.version=3.9,3.10,3.11,3.12,3.13,3.14`

### 13. `.coverage` is tracked in git despite being gitignored

- [ ] Open

**Problem:** A SQLite database containing absolute paths from the development machine.
It appears in commit diffs (including `30dc76e`) as binary noise.

**Fix:** `git rm --cached .coverage` — the `.gitignore` rule already covers it going forward.

### 14. The dependency vulnerability gate can never fail

- [ ] Open

**Location:** `.github/workflows/ci.yml`, security job

**Problem:** `safety check --full-report || true` swallows every non-zero exit, so the
check is decorative. `safety check` is also deprecated in favor of `safety scan`.

**Fix:** Switch to `safety scan` and let it fail the job, or replace it with `pip-audit`,
which needs no account. If a soft signal is genuinely what you want, say so in a comment
so the `|| true` reads as intentional.

### 15. The `lgtm[...]` suppression comment is likely a no-op

- [ ] Open

**Location:** `auth/oauth.py:452`

**Problem:** `# lgtm[py/clear-text-logging-sensitive-data]` is LGTM.com syntax. GitHub
code scanning does not honor it; alerts are dismissed through the Security tab.

**Fix:** Dismiss the alert in the UI as "won't fix" with the WSL2 rationale, and either
remove the comment or reword it as a plain explanatory comment.

---

## P4 — Hygiene and coverage

### 16. Stale usage strings reference a module path that no longer exists

- [ ] Open

**Location:** `main.py:116`, `main.py:154`

Both print `Usage: python -m src.main ...`. The package is `hpde_analytics_cli` and the
console script is `hpde-analytics-cli`.

### 17. Bare invocation starts an OAuth browser flow

- [ ] Open

**Location:** `main.py:471-472`

Running `hpde-analytics-cli` with no arguments falls through to `handle_full_flow`, which
opens a browser. Printing `--help` is the less surprising default.

### 18. Unused imports

- [ ] Open

`socket` and `threading` at `auth/oauth.py:12-13`; several in the test modules
(`test_client.py:5`, `test_credentials.py:6`, `test_data_export.py:9`, `test_main.py:5`,
`test_report_generator.py:9`), plus two unused `exported_files` locals at
`test_data_export.py:243` and `:310`.

These never fail the build because the full flake8 pass runs `--exit-zero`. Worth either
cleaning them up and enabling `F401`/`F841` as hard failures, or accepting that the
second flake8 invocation is advisory only.

### 19. Test coverage gaps in the modules carrying the bugs above

- [ ] Open

| Module | Coverage | Note |
| --- | --- | --- |
| `utils/field_discovery.py` | 16% | No test file exists at all |
| `auth/oauth.py` | 16% | Token load/save and the callback handler are untested |
| `main.py` | 26% | Only the argument parser is tested; no handler is |

The `main.py` handlers are where items 2 and 3 live — handler-level tests would have
caught both. Highest value additions, in order: `handle_report` / `handle_export`
dispatch behavior, `_load_tokens` / `_save_tokens` round-trip, and a basic
`FieldDiscovery` test module.

---

## Feature opportunities

Not defects — items where the tool's stated purpose (program metrics) outruns what it
currently produces.

### 20. The timing feed is fetched and then discarded

- [ ] Open

`MSRClient.get_timing_feed` is called by `get_all_endpoint_data` (`client.py:399`) but
`DataExporter` never exports it. For a Time Trials program, lap and session times are the
richest available data and are currently dropped. Adding it to the export is a small
change; what to do with it in the report is a larger design question.

### 21. The report is a single flat sheet with no aggregation

- [ ] Open

Columns are pivot-ready, but there is no summary sheet and no cross-event rollup — every
report covers one event in isolation. Season-level questions (participation trends,
driver retention event over event, class mix over time) currently require manual Excel work.

Natural next steps: a summary worksheet with counts by class group / day count /
participation type, then a multi-event mode that accepts several export directories and
produces a season view.

### 22. WDCR Time Trials vocabulary is hardcoded — generalize toward any MSR-sanctioned program

- [ ] Open — **direction agreed, staged; no work started**

**Where the coupling lives, all in `report_generator.py`:**

| Concept | Lines | Hardcoded as |
| --- | --- | --- |
| Run groups | 72-88 | substring match on `"time trials"`, `"instructing"`, `"advanced hpde"` |
| Worker entries | 90 | substring match on `"workers"` |
| Event days | 59-70 | Friday / Saturday / Sunday |
| Class groups | 387-411 | prefix match on `Max` / `Sport` / `Tuner` / `Unlimited` |
| Derived categories | 96-128 | `TT Only` / `TT + Instructor` / `TT + AYCE` / `TT + Instructor + AYCE`; `1 Day` / `2 Days` / `3 Days` |
| Output schema | 335-353 | 17 fixed columns assuming a TT class, vehicle number, and tire brand |

**Target scope.** The tool is MSR-first by design — that is the integration boundary and it
is not changing. What varies is the sanctioning body and the program on top of MSR:

- **Other SCCA regions running Time Trials.** Closest to the current code. Expect the same
  national TT class structure, but different run group names and possibly two-day rather
  than three-day weekends.
- **Other MSR-sanctioning organizations — NASA, PCA, BMW CCA, and similar.** All use MSR
  for registration, so the API layer and the export tier work unchanged today. Their
  program structures differ more substantially: different class systems, different run
  group taxonomies, and in some cases a DE/HPDE-only event with no timed component at all.

The API client, OAuth layer, and `DataExporter` are already organization-agnostic. The
coupling is confined to report generation, which is the good news — nothing below
`utils/report_generator.py` needs to change.

**Staged plan.** Each stage is independently useful; stop after any of them.

*Stage 1 — externalize the matching strings.* Move the run group, worker, day, and class
group patterns into a profile file (YAML or JSON) shipped with a `wdcr-tt` default, selected
by a `--profile` flag with the current behavior as the fallback. Output columns stay fixed.
This covers other SCCA regions and is a contained change.

*Stage 2 — make the output schema part of the profile.* Promote the column list, the
derived category rules (participation type, day count), and the "which drivers belong in
this report" filter out of the code and into the profile. This is what NASA / PCA / BMW CCA
actually need, and it is a real refactor: the report generator becomes a small engine over
a declarative profile rather than a TT-specific script.

*Stage 3 — ship profiles for the other organizations.* One profile per org/program. Each
needs a real export from a real event to author against; do not write them speculatively.

**Prerequisites before Stage 2.**

- Confirm the actual field and run group vocabulary for at least one non-SCCA org by
  running `--discover` against a real event. Do not infer their class structures from
  general knowledge — verify against live data.
- Land item 4 (driver identity) first. A profile system built on top of name-only matching
  propagates that bug into every new program.

**Guard against premature generalization.** Stage 1 only pays off once a second real program
exists. A profile system with exactly one valid profile in it is worse than the hardcoded
version — it adds indirection without adding capability. Trigger Stage 1 on a concrete
second program, not on the idea of one.

---

## Open questions

1. **~~Deployment reality~~** — Answered: author is the only PyPI consumer today, with a
   UI version planned later. Item 2 is therefore not an emergency, but should be fixed
   before the UI work begins, since a UI build will be a separate install subject to all
   four path bugs.
2. **Does MSR populate `memberId` on both the entrylist and attendees responses?**
   Blocks the design of item 4. Resolve by running an export against a real event and
   checking column presence and fill rate in both CSVs.
3. **~~Which other programs are in scope?~~** — Answered: MSR-sanctioned events generally.
   WDCR SCCA centric today, other SCCA regions expected to be close, with NASA / PCA /
   BMW CCA as the broader target since they also register through MSR. Captured as the
   staged plan in item 22. Remaining sub-question: which specific organization is the
   first non-WDCR target, since that determines whether Stage 1 alone is sufficient.
