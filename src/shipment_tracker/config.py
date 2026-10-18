"""Settings, read from environment variables (and a `.env` file, if present).

Everything that might differ between your laptop, a scheduled job, and the
tests lives here instead of being hard-coded: tab names, file locations,
which tracking provider to use. Secrets (API keys) will come in the same way
in later milestones, so they never appear in source code.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULTS = {
    "SHEET_TABS": "Form Responses 1,Manual Entries",
    "SHEET_BACKEND": "mock",
    "MOCK_SHEET_TEMPLATE": str(PROJECT_ROOT / "data" / "mock_sheet.json"),
    "MOCK_SHEET_FILE": str(PROJECT_ROOT / "work" / "mock_sheet.json"),
    "TRACKING_PROVIDER": "mock",
    "MOCK_TRACKING_FILE": str(PROJECT_ROOT / "data" / "mock_shipments.json"),
    "LOG_DIR": str(PROJECT_ROOT / "logs"),
    "OUTPUT_DIR": str(PROJECT_ROOT / "output"),
    "ANTHROPIC_MODEL": "claude-opus-5-5",
}


class ConfigError(ValueError):
    """A setting is missing or invalid. The message says which one and how to fix it."""


@dataclass(frozen=True)
class Settings:
    tabs: tuple[str, ...]
    sheet_backend: str
    mock_sheet_template: Path
    mock_sheet_file: Path  # a working copy the runs edit, so data/ stays pristine
    tracking_provider: str
    mock_tracking_file: Path
    log_dir: Path
    output_dir: Path  # updated Excel copies (git-ignored: they contain real data)
    anthropic_model: str
    # Whether a key is set. The key itself is never stored here: the
    # Anthropic SDK reads ANTHROPIC_API_KEY from the environment on its own.
    has_anthropic_key: bool


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build Settings from `env`, falling back to DEFAULTS.

    Tests pass their own `env` dictionary. Real runs pass nothing, which
    reads the process environment after loading `.env`.
    """
    if env is None:
        load_dotenv(PROJECT_ROOT / ".env")
        env = os.environ

    def get(name: str) -> str:
        return env.get(name) or DEFAULTS[name]

    tabs = tuple(t.strip() for t in get("SHEET_TABS").split(",") if t.strip())
    if not tabs:
        raise ConfigError("SHEET_TABS is empty. List tab names separated by commas.")

    return Settings(
        tabs=tabs,
        sheet_backend=get("SHEET_BACKEND").lower(),
        mock_sheet_template=Path(get("MOCK_SHEET_TEMPLATE")),
        mock_sheet_file=Path(get("MOCK_SHEET_FILE")),
        tracking_provider=get("TRACKING_PROVIDER").lower(),
        mock_tracking_file=Path(get("MOCK_TRACKING_FILE")),
        log_dir=Path(get("LOG_DIR")),
        output_dir=Path(get("OUTPUT_DIR")),
        anthropic_model=get("ANTHROPIC_MODEL"),
        has_anthropic_key=bool(env.get("ANTHROPIC_API_KEY", "").strip()),
    )
