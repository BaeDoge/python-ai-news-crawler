from __future__ import annotations

import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from src.config import env_value, load_environment
from src.pipeline import run_pipeline


def main() -> None:
    load_environment()
    result = run_pipeline(
        api_key=env_value("OPENROUTER_API_KEY"),
        model=env_value("OPENROUTER_MODEL", "openrouter/free"),
        use_sample_data=True,
        allow_ai_fallback=True,
    )
    print(f"PDF: {result.artifacts.pdf_path}")
    print(f"XLSX: {result.artifacts.xlsx_path}")
    print(f"LOG: {result.artifacts.json_path}")
    print(f"MODEL: {result.model_used}")


if __name__ == "__main__":
    main()
