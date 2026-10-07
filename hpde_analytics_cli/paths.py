"""
Filesystem path resolution.

Single owner for every user-facing path the CLI reads or writes.

Paths must never be derived from ``__file__``. For an installed package that resolves to
``site-packages``, which previously meant the user's ``.env`` was never read, OAuth tokens
were written where the next upgrade destroys them, and exported registration data landed
in a library directory. See CODE_REVIEW.md #2.
"""

import os
from pathlib import Path
from typing import List, Optional

from dotenv import find_dotenv
from platformdirs import user_config_dir

APP_NAME = "hpde-analytics-cli"

#: Overrides the per-user config directory. Mainly for tests and sandboxed front-ends.
ENV_CONFIG_DIR = "HPDE_CONFIG_DIR"

ENV_FILENAME = ".env"
OUTPUT_DIRNAME = "output"
TOKEN_FILENAME = "access_token.json"
LEGACY_TOKEN_DIRNAME = "tokens"


def config_dir() -> Path:
    """
    Per-user configuration directory.

    Honours ``HPDE_CONFIG_DIR`` if set, otherwise the platform-native location:
    ``~/.config/hpde-analytics-cli`` on Linux, ``~/Library/Application Support/...`` on
    macOS, ``%LOCALAPPDATA%\\...`` on Windows.
    """
    override = os.environ.get(ENV_CONFIG_DIR)
    if override:
        return Path(override).expanduser()
    return Path(user_config_dir(APP_NAME))


def token_file() -> Path:
    """Path to the stored OAuth access token."""
    return config_dir() / TOKEN_FILENAME


def default_output_dir() -> Path:
    """Default directory for exports and reports, relative to where the user is."""
    return Path.cwd() / OUTPUT_DIRNAME


def find_env_files() -> List[Path]:
    """
    ``.env`` files to load, in precedence order.

    The project file comes first: ``load_dotenv`` does not overwrite keys that are already
    set, so loading in this order gives a project-local ``.env`` precedence over the
    per-user one, which then supplies anything the project file left out.
    """
    found: List[Path] = []

    project_env = find_dotenv(ENV_FILENAME, usecwd=True)
    if project_env:
        found.append(Path(project_env))

    user_env = config_dir() / ENV_FILENAME
    if user_env.exists() and user_env not in found:
        found.append(user_env)

    return found


def legacy_token_file() -> Path:
    """
    Where versions up to 6.0.7 stored the access token.

    Derived from ``__file__`` the way the old code did, so it resolves to the repository
    root for a source checkout and to ``site-packages`` for an installed package.
    """
    return Path(__file__).parent.parent / LEGACY_TOKEN_DIRNAME / TOKEN_FILENAME


def migrate_legacy_token(destination: Path) -> Optional[Path]:
    """
    Move a token left by an older version into ``destination``.

    Does nothing if the destination already exists or there is nothing to move, so it is
    safe to call on every startup.

    Returns:
        The path moved from, or None if nothing was migrated.
    """
    if destination.exists():
        return None

    legacy = legacy_token_file()
    if not legacy.is_file():
        return None

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(legacy.read_bytes())
        restrict_permissions(destination)
        legacy.unlink()
    except OSError:
        return None

    return legacy


def restrict_permissions(path: Path) -> None:
    """
    Restrict a file to the owner (0600), or a directory to 0700.

    Best effort: POSIX permissions do not map onto Windows ACLs, so failures are ignored
    rather than breaking an otherwise working auth flow.
    """
    try:
        os.chmod(path, 0o700 if path.is_dir() else 0o600)
    except OSError:
        pass
