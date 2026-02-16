"""Application settings and config loading."""

import json
from pathlib import Path

from pydantic_settings import BaseSettings


class AppSettings(BaseSettings):
    """Main application settings loaded from .env."""

    project_code: str = "KG"
    input_dir: Path = Path("./input")
    output_dir: Path = Path("./output")
    config_dir: Path = Path("./config")
    default_contact_phone: str = ""
    default_manager_name: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def load_json_config(config_dir: Path, filename: str) -> dict:
    """Load a JSON config file from config directory."""
    path = config_dir / filename
    with open(path, encoding="utf-8") as f:
        return json.load(f)
