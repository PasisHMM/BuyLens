"""Write the browser prototype's data files, generated from Python so TypeScript holds no rules.

    apps/web/src/lib/api/mock/catalog.json         what GET /v1/measurements returns
    apps/web/src/lib/api/mock/merchandizable.json  the demo shop's chart, products and fit outcomes

CI fails if the committed files are out of date.

    uv run python scripts/export_catalog.py [--check]
"""

import json
import sys
from pathlib import Path
from typing import Any

from app.pipeline.demo_shop import prototype_fixture
from app.schemas.measurements import build_catalog

MOCK_DIR = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "lib" / "api" / "mock"


def _files() -> dict[Path, Any]:
    return {
        MOCK_DIR / "catalog.json": build_catalog().model_dump(mode="json"),
        MOCK_DIR / "merchandizable.json": prototype_fixture(),
    }


def main() -> int:
    stale = 0
    for path, data in _files().items():
        rendered = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if "--check" not in sys.argv:
            path.write_text(rendered, encoding="utf-8", newline="\n")
            print(f"Wrote {path}")
        elif not path.exists() or path.read_text(encoding="utf-8") != rendered:
            print(f"{path} is out of date. Run: uv run python scripts/export_catalog.py", file=sys.stderr)
            stale = 1
    return stale


if __name__ == "__main__":
    raise SystemExit(main())
