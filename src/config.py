from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT_DIR / "outputs"
SOURCE_CONFIG_PATH = ROOT_DIR / "config" / "sources.json"


def load_environment() -> None:
    load_dotenv(ROOT_DIR / ".env")


def load_sources() -> List[Dict[str, Any]]:
    with SOURCE_CONFIG_PATH.open("r", encoding="utf-8") as source_file:
        sources = json.load(source_file)
    return [source for source in sources if source.get("enabled", True)]


def env_value(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_int(name: str, default: int) -> int:
    try:
        return int(env_value(name, str(default)))
    except ValueError:
        return default
