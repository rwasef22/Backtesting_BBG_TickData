"""Utilities to load strategy configuration from a JSON file."""
import json
from pathlib import Path
from typing import Dict


def load_strategy_config(config_path: str) -> Dict:
    """Load per-security strategy config from a JSON file.

    Args:
        config_path: Path to JSON config file.

    Returns:
        Dict mapping security -> config dict.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the file cannot be parsed or does not contain a dict.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with path.open('r', encoding='utf-8') as fh:
        try:
            data = json.load(fh)
        except Exception as exc:  # pragma: no cover - defensive
            raise ValueError(f"Failed to parse config file {config_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain an object/dict: {config_path}")

    return data
