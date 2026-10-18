"""Where the project lives on disk, and its settings from config.toml."""

import tomllib
from pathlib import Path

# This file is src/plantagent/config.py, so the project folder is two levels above its folder.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.toml"


def load_config() -> dict:
    """Read config.toml and return its contents as a dictionary."""
    with CONFIG_PATH.open("rb") as file:  # tomllib wants the file opened in binary mode ("rb")
        return tomllib.load(file)
