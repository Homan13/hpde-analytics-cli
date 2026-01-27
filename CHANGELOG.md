# Changelog

## [2.0.0](https://github.com/Homan13/hpde-analytics-cli/compare/v1.0.0...v2.0.0) (2026-01-27)


### ⚠ BREAKING CHANGES

* Python 3.8 reached end-of-life in 2024 and is no longer supported. Users must upgrade to Python 3.9 or later.

### Features

* Drop Python 3.8 support, add Python 3.13 and 3.14
* Add CodeQL and SonarCloud security scanning
* Add Release Please for automated releases
* Add pre-commit hooks configuration


### Bug Fixes

* Remove sensitive data from log output
* Fix Release Please configuration for proper version updates
* Trigger PyPI publish on both created and published releases

## [1.0.0](https://github.com/Homan13/hpde-analytics-cli/releases/tag/v1.0.0) (2026-01-19)

Initial stable release of HPDE Analytics CLI.

### Features

* Data retrieval from MotorsportReg API
* Event and registration analysis
* Comprehensive reporting capabilities
* OAuth 1.0a authentication
* Configuration management
* Multiple output formats (CSV, JSON)
