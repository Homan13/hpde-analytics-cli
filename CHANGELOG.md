# Changelog

## [6.0.6](https://github.com/Homan13/hpde-analytics-cli/compare/v6.0.5...v6.0.6) (2026-10-07)


### Bug Fixes

* reconcile pyproject version with release tag after stale release PR ([d85c1dd](https://github.com/Homan13/hpde-analytics-cli/commit/d85c1dd792815a5807819d76ffc8c42b5bce1ff9))

## [6.0.5](https://github.com/Homan13/hpde-analytics-cli/compare/v6.0.4...v6.0.5) (2026-10-07)


### Documentation

* add code review backlog and Claude Code repository guidance ([4c24a3e](https://github.com/Homan13/hpde-analytics-cli/commit/4c24a3e8ee6fe5dba2fbc4b4c0a313099a4c0e1d))

## [6.0.4](https://github.com/Homan13/hpde-analytics-cli/compare/v6.0.3...v6.0.4) (2026-03-03)


### Bug Fixes

* resolve open CodeQL security alerts ([30dc76e](https://github.com/Homan13/hpde-analytics-cli/commit/30dc76e82039c47e66815f0efd27dd99c43bc7b5))

## [6.0.3](https://github.com/Homan13/hpde-analytics-cli/compare/v6.0.2...v6.0.3) (2026-03-03)


### Bug Fixes

* set package version from release tag at build time in publish workflow ([cb54be2](https://github.com/Homan13/hpde-analytics-cli/commit/cb54be2a38157082de5bd3e55c90a0124094380f))

## [6.0.2](https://github.com/Homan13/hpde-analytics-cli/compare/v6.0.1...v6.0.2) (2026-03-03)


### Bug Fixes

* correct release-please config to update pyproject.toml on release ([4442558](https://github.com/Homan13/hpde-analytics-cli/commit/4442558daee663fdee9dd23d3a790b748238f99b))

## [6.0.1](https://github.com/Homan13/hpde-analytics-cli/compare/v6.0.0...v6.0.1) (2026-03-03)


### Bug Fixes

* resolve CI failures and sync version to v6.0.0 ([789b016](https://github.com/Homan13/hpde-analytics-cli/commit/789b01683c8705901a26b4fadec57e33f6b8abb3))

## [6.0.0](https://github.com/Homan13/hpde-analytics-cli/compare/v5.0.0...v6.0.0) (2026-03-03)


### ⚠ BREAKING CHANGES

* Python 3.8 reached end-of-life in 2024 and is no longer supported. Users must upgrade to Python 3.9 or later.
* Python 3.8 reached end-of-life in 2024 and is no longer supported. Users must upgrade to Python 3.9 or later.

### Features

* add --populate-emails command for Google Sheets integration ([98a15b3](https://github.com/Homan13/hpde-analytics-cli/commit/98a15b3b4027dd95d82898a344538046271804eb))
* Drop Python 3.8 support, add Python 3.13 and 3.14 ([dd4fdad](https://github.com/Homan13/hpde-analytics-cli/commit/dd4fdad4915d2601130000f06562a8c766fe801c))
* Drop Python 3.8 support, add Python 3.13 and 3.14 ([8298f3f](https://github.com/Homan13/hpde-analytics-cli/commit/8298f3ff97566da1f0cb15fcefc0459aa11ea206))


### Bug Fixes

* Remove sensitive data from log output ([c4cd531](https://github.com/Homan13/hpde-analytics-cli/commit/c4cd531dc2f3b30182c74dc813e40e52adf63cbd))
* Reset to v2.0.0 and enable automated PyPI publishing ([47ed9ca](https://github.com/Homan13/hpde-analytics-cli/commit/47ed9ca2da44c3dafa3dbcaf4a71be9ef9f5ffe0))
* Reset version to 2.0.0 and fix Release Please config ([13a5833](https://github.com/Homan13/hpde-analytics-cli/commit/13a58333cff44a074971f0e9defa0a88dd453ad9))
* Reset version to 2.0.0 and fix Release Please config ([9f92259](https://github.com/Homan13/hpde-analytics-cli/commit/9f922593ca17830c8aa66abadce8f4899d62b7df))
* resolve linting and type check errors from SonarCloud refactoring ([1656bb5](https://github.com/Homan13/hpde-analytics-cli/commit/1656bb5d5f8c49f609e5d70e9cf16513a68c3170))
* Sync pyproject.toml version and fix Release Please config ([0f5eaac](https://github.com/Homan13/hpde-analytics-cli/commit/0f5eaac50829ebf99b7a7d73916220f3aed8e4c2))
* Trigger PyPI publish on both created and published releases ([da9fa52](https://github.com/Homan13/hpde-analytics-cli/commit/da9fa52467ea572bd05fd2707fe28258c56e8ac5))

---

> ### Note on versions 3.0.0 through 6.0.0
>
> There is no 3.x, 4.x, or 5.x entry below, and the jump from 2.0.0 to 6.0.0 does not
> reflect four rounds of breaking changes. Those major versions were artifacts of the
> release automation, not real releases.
>
> One genuine breaking change was made in this period — dropping Python 3.8 in v2.0.0.
> It was then committed a second time, producing v3.0.0. Each subsequent attempt to
> correct the version by hand-editing `.release-please-manifest.json` failed for the same
> reason: release-please derives the next version from the Conventional Commit history
> since the last release tag, and editing the manifest backwards does not remove the
> breaking-change commits from that range. Every reset attempt re-detected the same
> breaking change and issued another major bump, producing 4.0.0, 5.0.0 and finally
> 6.0.0. The duplicated "Python 3.8 reached end-of-life" line in the 6.0.0 entry above is
> the visible symptom.
>
> By strict semver this project would be at roughly 2.1.x. The 6.x line was kept because
> PyPI version numbers are permanent and resolvers always prefer the highest version, so
> renumbering downward would strand the published releases rather than tidy them.
>
> Versions are now owned entirely by release-please and must not be edited by hand.
> `pyproject.toml` carries an `x-release-please-version` annotation so the automation can
> update it, and `__version__` is read from installed package metadata rather than
> hardcoded.

## [2.0.0](https://github.com/Homan13/hpde-analytics-cli/compare/v1.0.0...v2.0.0) (2026-01-27)


### ⚠ BREAKING CHANGES

* Python 3.8 reached end-of-life in 2024 and is no longer supported. Users must upgrade to Python 3.9 or later.

### Features

* Drop Python 3.8 support, add Python 3.13 and 3.14 ([dd4fdad](https://github.com/Homan13/hpde-analytics-cli/commit/dd4fdad4915d2601130000f06562a8c766fe801c))
* Add CodeQL and SonarCloud security scanning
* Add Release Please for automated releases
* Add pre-commit hooks configuration


### Bug Fixes

* Remove sensitive data from log output ([c4cd531](https://github.com/Homan13/hpde-analytics-cli/commit/c4cd531dc2f3b30182c74dc813e40e52adf63cbd))
* Fix Release Please configuration for proper version updates
* Trigger PyPI publish on both created and published releases ([da9fa52](https://github.com/Homan13/hpde-analytics-cli/commit/da9fa52467ea572bd05fd2707fe28258c56e8ac5))

## [1.0.0](https://github.com/Homan13/hpde-analytics-cli/releases/tag/v1.0.0) (2026-01-19)

Initial stable release of HPDE Analytics CLI.

### Features

* Data retrieval from MotorsportReg API
* Event and registration analysis
* Comprehensive reporting capabilities
* OAuth 1.0a authentication
* Configuration management
* Multiple output formats (CSV, JSON)
