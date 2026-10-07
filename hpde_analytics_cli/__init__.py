"""HPDE Analytics CLI: Event Registration API integration for HPDE and Time Trials programs."""

from importlib.metadata import PackageNotFoundError, version

__app_name__ = "hpde-analytics-cli"

try:
    __version__ = version(__app_name__)
except PackageNotFoundError:  # pragma: no cover - source tree without an install
    __version__ = "0.0.0+unknown"
