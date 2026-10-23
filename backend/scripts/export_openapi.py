"""Выгружает OpenAPI-спецификацию в docs/openapi.json и docs/openapi.yml."""

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from app.main import app

    out_dir = ROOT / "docs"
    out_dir.mkdir(exist_ok=True)
    schema = app.openapi()
    (out_dir / "openapi.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "openapi.yml").write_text(yaml.safe_dump(schema, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"OpenAPI сохранена в {out_dir}")


if __name__ == "__main__":
    main()
