"""Write the API's OpenAPI schema to packages/contracts/openapi.json.

The web app generates its TypeScript types from this file (Phase 3: `openapi-typescript`).
CI fails if the committed file is out of date.

    uv run python scripts/export_openapi.py [--check]
"""

import json
import sys
from pathlib import Path

from pydantic import SecretStr

from app.config import Settings
from app.main import create_app

OUT = Path(__file__).resolve().parents[3] / "packages" / "contracts" / "openapi.json"


def main() -> int:
    # Placeholder secret: building the schema never verifies a token or touches the network.
    app = create_app(Settings(env="dev", supabase_jwt_secret=SecretStr("schema-export-only")))
    rendered = json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != rendered:
            print(f"{OUT} is out of date. Run: uv run python scripts/export_openapi.py", file=sys.stderr)
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(rendered, encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
