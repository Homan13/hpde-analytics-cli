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

- [x] **Fixed 2026-10-07**

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

**Fixed 2026-10-07.** All five call sites now go through a new `hpde_analytics_cli/paths.py`,
the single owner of user-facing path resolution. No path outside that module derives from
`__file__`, and the one use inside it is the deliberate lookup of the legacy token location.

| Path | Now resolves to |
| --- | --- |
| Exports, reports, field inventory | `Path.cwd() / "output"` |
| OAuth access token | `<user config dir>/access_token.json` |
| `.env` | `find_dotenv(usecwd=True)`, then `<user config dir>/.env` |

The user config directory comes from `platformdirs` (added as a runtime dependency), giving
the native location per platform, overridable with `HPDE_CONFIG_DIR`. A hand-rolled
`sys.platform` branch was considered and rejected: the project claims OS independence and
`keyring` already behaves natively per platform, so the macOS and Windows conventions are
worth getting from a maintained library rather than maintaining here.

`.env` files load project-first, then user. `load_dotenv` does not overwrite keys that are
already set, so that ordering gives a project-local file precedence while the user file
supplies whatever it omits — layered config for free, without a precedence flag.

**Notable:** this is a no-op for a source checkout, where `Path.cwd()` and
`Path(__file__).parent.parent` are the same directory. Only the broken cases change.

**Migration:** `paths.migrate_legacy_token()` runs on startup, but only when the default
location is in use — an explicitly supplied `token_file` (tests, or a caller managing its
own state) must never have a stray file moved into it. Verified end to end: a mode-0644
token at the legacy path is moved, re-moded to 0600, the original removed, and the token
loads normally.

**Verified against a real wheel install** in a clean venv, run from an unrelated directory:
config, token, output and `.env` paths all resolve outside `site-packages`, and a `.env` in
the working directory is read and applied.

**Still open:** `.env.example` is not included in the wheel, so `cp .env.example .env` only
works from a clone. The README no longer instructs that as the primary step — it now
describes creating the file directly — so this is cosmetic. Worth adding to the sdist via
`MANIFEST.in`, or having `--configure` offer to write a starter `.env`.

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

- [x] **Fixed 2026-10-07** (with item 2)

**Location:** `auth/oauth.py` `_save_tokens`

**Problem:** Plain `open(..., "w")` left the file at 0644 after umask. The file holds the
OAuth access token and token secret.

**Fixed** alongside item 2, since moving the token to a new location is exactly the moment
to set its mode — relocating a secret to a per-user directory while leaving it
world-readable would have been a strange place to stop. `_save_tokens` now calls
`paths.restrict_permissions()` on both the file (0600) and its directory (0700), and
`migrate_legacy_token()` applies the same mode to anything it moves. The helper swallows
`OSError` because POSIX modes do not map onto Windows ACLs and a failure there should not
break an otherwise working auth flow.

Covered by `tests/test_paths.py::TestRestrictPermissions` and
`TestMigrateLegacyToken::test_migrated_token_is_owner_only`, both skipped on Windows.

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

- [x] **Fixed 2026-10-06**

| Source | Was | Now |
| --- | --- | --- |
| `.release-please-manifest.json` | 6.0.4 (authoritative) | unchanged |
| `pyproject.toml:8` | 6.0.1 | 6.0.4, annotated for release-please |
| `hpde_analytics_cli/__init__.py:3` | 1.0.0 | read from installed metadata |
| `README.md` "Current Version" | 2.0.0 | removed; links to Releases |
| `sonar-project.properties` | 0.1.0 | removed |

**Root cause for `pyproject.toml`:** release-please's `generic` extra-file updater needs
an `# x-release-please-version` annotation comment on the line it should bump. Without it
the file was skipped — which is why `publish.yml` carried a `sed` workaround.

**Decision on the version line itself.** By strict semver this project is at roughly
2.1.x: v3.0.0 through v6.0.0 were artifacts of release automation, not real breaking
changes. Each hand-edit of `.release-please-manifest.json` back to 2.0.0 failed because
release-please derives the next version from Conventional Commit history since the last
release tag — the breaking-change commits stayed in range and were re-detected, issuing
another major each time.

The 6.x line was deliberately kept rather than renumbered downward. PyPI version numbers
are permanent and resolvers prefer the highest version, so publishing 2.1.0 would leave
`pip install hpde-analytics-cli` resolving to 6.0.4 and strand the new release. Yanking
6.0.0-6.0.4 was considered and rejected: yanking signals a broken release, and the cost
(rewriting 7 tags, 7 GitHub releases and the changelog, permanently burning those version
numbers) buys only a cosmetic improvement.

**Changes applied:**

1. `pyproject.toml` version annotated and synced to 6.0.4:
   ```toml
   version = "6.0.4"  # x-release-please-version
   ```
2. `publish.yml`'s `sed` step replaced with a guard that fails the build if the release
   tag and `pyproject.toml` disagree — so a future release-please misconfiguration
   surfaces as a failed publish instead of silently shipping a wrong version.
3. `__init__.py` reads `__version__` via `importlib.metadata.version()`, falling back to
   `0.0.0+unknown` when run from an uninstalled source tree.
4. `README.md` version line replaced with the release process and a Releases link.
5. `sonar.projectVersion` removed from `sonar-project.properties`.
6. `--version` flag added to the CLI (`main.py`).
7. `CHANGELOG.md` carries a note at the 2.0.0 / 6.0.0 boundary explaining the gap.

**Standing rule:** never hand-edit a version anywhere. release-please owns all of them.

**Postscript — root cause: CRLF line endings in `pyproject.toml` (2026-10-07).**

Both the v6.0.5 and v6.0.6 publishes failed the version guard, tag and `pyproject.toml`
disagreeing each time.

*A first diagnosis, recorded here because it was wrong and the correction matters.* The
v6.0.5 failure was initially attributed to release PR #53 having been generated seventeen
hours before the annotation reached `main` and merged three and a half minutes after it
landed. The timeline was accurate but coincidental. v6.0.6 failed identically with no such
timing overlap, which disproved it.

**The actual cause.** `pyproject.toml` is stored with CRLF line endings. release-please's
Python strategy parses it with a strict TOML parser, which rejects carriage returns inside
comments. Running release-please 17.11.2's updaters against the real file:

```
real file (CRLF + annotation)  THREW: Control characters (codes < 0x1f and 0x7f) are not
                                      allowed in comments ... at row 7, col 46
annotation comment removed     THREW: ... at row 99, col 50   (the bandit `skips` comment)
CRLF converted to LF           CHANGED -> version = "6.0.6"
```

Row 7 column 46 is the `\r` terminating the version line. The parse throws, release-please
logs a warning and skips the file, and the bump is silently lost. Removing the annotation
does not help — any CRLF-terminated comment anywhere in the file triggers it.

This explains the whole history: `pyproject.toml` was never bumped by *any* release, which
is why `publish.yml` carried a `sed` workaround from v6.0.3 onward. The
`x-release-please-version` annotation was never the missing piece; the file was simply
unparseable. Note that the `Generic` updater used by `extra-files` is line-based and
*does* handle CRLF, but the Python strategy registers its own `PyProjectToml` updater for
the same path, which takes precedence.

**Fixes applied:**

1. `pyproject.toml` converted to LF (99 CRLF pairs) and set to `6.0.6`. Verified
   afterwards that both the native `PyProjectToml` updater and the `extra-files` `Generic`
   updater now rewrite the version correctly.
2. `.gitattributes` added pinning `pyproject.toml text eol=lf`, with the reason inline so
   the constraint is not silently reverted by an editor.
3. `publish.yml` restructured. The hard gate is now **tag vs
   `.release-please-manifest.json`** — release-please writes both in the same commit, so
   disagreement means a malformed release and is worth blocking. A `pyproject.toml` lag is
   now a **warning** that pins the version for the build rather than a failure, because a
   mirror file lagging should never strand a published tag with no PyPI artifact. That is
   precisely what cost v6.0.5 and v6.0.6.

**Releases v6.0.5 and v6.0.6 have GitHub releases but no PyPI artifact.** The tags were
deliberately not moved; re-running their publish jobs would use the workflow file from
their own tagged trees, which still contains the blocking guard. v6.0.7 is the first
release expected to publish cleanly. Acceptable here because the author is the only PyPI
consumer and both changelogs contain documentation and CI changes only.

### 24. Mixed line endings across the repository

- [ ] Open — low priority, deliberately deferred

Twenty-five tracked files use CRLF while the rest use LF, with no `.gitattributes` to
normalize them: all five workflow YAMLs, `.pre-commit-config.yaml`, `.github/dependabot.yml`,
`release-please-config.json`, `sonar-project.properties`, `LICENSE`, six Python modules
under `hpde_analytics_cli/`, and seven test modules.

Only `pyproject.toml` caused an actual failure (item 11), and it is now pinned to LF.
The rest are latent: YAML and Python parsers tolerate CRLF, so nothing is broken today.

Fixing it is mechanical but touches every affected file in full:

```bash
printf '* text=auto eol=lf\n' >> .gitattributes
git add --renormalize .
git commit -m "style: normalize line endings to LF"
```

Kept out of the release fix so that change stayed reviewable. Worth doing as its own
commit, ideally when no release PR is open.

### 12. `sonar-project.properties` Python versions are stale

- [x] **Fixed 2026-10-06**

Declared `sonar.python.version=3.8,3.9,3.10,3.11,3.12`. 3.8 was dropped in v2.0.0;
3.13 and 3.14 are in the CI test matrix but were missing here. Now
`3.9,3.10,3.11,3.12,3.13,3.14`, matching the `ci.yml` matrix and `requires-python`.

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

## Addendum — CI infrastructure

Added 2026-10-06 after investigating a reported Actions failure. Numbered 23 to keep the
existing item numbers stable; priority is **P1**.

### 23. SonarCloud has been failing since March 2026 — rejected API token

- [ ] Open — **root cause confirmed; fix requires rotating the token**

**Evidence.** Run history for the `SonarCloud` workflow:

| Runs | Dates | Result |
| --- | --- | --- |
| …#57 | through 2026-03-03 | success |
| #58-#64 | 2026-03-30 onward | failure, every run |

The failing step is `SonarCloud Scan` itself, not a quality gate — checkout, dependency
install, and the pytest coverage run all succeed first.

**This is not a code problem.** `main` sat unchanged at `7dd9c5e` from 2026-03-03 to
2026-10-06, so the last successful run and the first failing run analysed byte-identical
source. The pinned action is also unchanged: `sonarqube-scan-action@v6` resolves to
v6.0.0, released 2025-09-18, with no v6.x since — the floating tag never moved. Repository
unchanged plus action unchanged plus failure means the cause is SonarCloud-side state.

**Root cause, from the scan step's log:**

```
19:30:35.925 INFO  Communicating with SonarQube Cloud
19:30:36.432 ERROR Failed to query JRE metadata:
  GET https://api.sonarcloud.io/analysis/jres?os=linux&arch=x86_64 failed with HTTP 403.
  Please check the property sonar.token or the environment variable SONAR_TOKEN.
```

The scanner is rejected on its first authenticated call — before downloading its JRE, and
long before it reads any source. The credential is the whole problem. Nothing about code
quality, coverage, or the quality gate is involved.

A second cause compounds it: runs #58-#62 are all Dependabot PRs, which read from a
separate secret store and never receive repository secrets. Those would fail regardless of
the token's state.

**Changes applied** (neither fixes the root cause; both make the next failure legible):

1. Job-level `if` skips analysis for Dependabot-authored PRs and for PRs from forks rather
   than failing them. Resolves the #58-#62 class outright.
2. A `Verify SONAR_TOKEN is usable` preflight step that calls
   `https://sonarcloud.io/api/authentication/validate` and distinguishes *missing secret*
   from *rejected credential*, naming the rotation URL. It fails only on a definitive
   rejection; network errors and 5xx produce a warning and let the scan proceed, so the
   check cannot introduce flakiness of its own.

   Verified against the live endpoint: an invalid token returns HTTP **200** with
   `{"valid":false}`, not 401/403, which is why the check tests the body as well as the
   status code.

**Rejected change.** `SONAR_HOST_URL: https://sonarcloud.io` was added and then removed.
The log line `Communicating with SonarQube Cloud` comes from a run with no such variable
set, proving `sonarqube-scan-action@v6` already resolves SonarCloud on its own. Setting it
would have been untested configuration added on a disproven hypothesis.

**To finish this — requires SonarCloud and repository settings access:**

- Rotate the token at <https://sonarcloud.io/account/security> and update the `SONAR_TOKEN`
  secret under **Settings → Secrets and variables → Actions**. A 403 here means expired,
  revoked, or no longer permitted on the organization; tokens do not announce expiry.
- While there, confirm the project `Homan13_hpde-analytics-cli` still exists under
  organization `homan13`, and that **Administration → Analysis Method → Automatic Analysis**
  is **OFF** — it conflicts with CI-based analysis and fails the scan the same way.
- Re-run. The preflight now reports which of the two it is.

**Deferred:** Dependabot has an open PR bumping this action v6 → v8. Resolve the token
question first — upgrading the action while the credential is broken only adds a variable.
Note also that `@v6` is a floating major tag; pinning to a full version or a commit SHA
would remove a class of silent breakage.

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
