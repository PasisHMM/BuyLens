"""BUY / CONSIDER / SKIP, market averages and score-based decisions are gone from the code and the API."""

import importlib
import json
from pathlib import Path

import pytest

from app.pipeline import models

ROOT = Path(__file__).resolve().parents[3]
APP = ROOT / "services" / "api" / "app"
WEB = ROOT / "apps" / "web" / "src"
OBSOLETE = ("verdict", "market_avg", "delta_pct", "delta_cents", "comparable_count", "why_not")


@pytest.mark.parametrize("module", ["app.pipeline.rules", "app.pipeline.narrate", "app.pipeline.fitting"])
def test_the_old_decision_modules_are_deleted(module: str) -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


@pytest.mark.parametrize("name", ["Verdict", "Decision", "Narrative", "DecisionMemory", "FitMatch"])
def test_the_old_decision_models_are_deleted(name: str) -> None:
    assert not hasattr(models, name)


def test_the_api_contract_has_no_verdict_or_market_field() -> None:
    contract = (ROOT / "packages" / "contracts" / "openapi.json").read_text(encoding="utf-8").lower()
    for word in OBSOLETE:
        assert word not in contract, word


def test_the_api_contract_has_the_result_groups() -> None:
    schemas = json.loads((ROOT / "packages" / "contracts" / "openapi.json").read_text(encoding="utf-8"))[
        "components"
    ]["schemas"]
    assert {"matches", "uncertain", "hidden_mismatches", "fit_mode_used"} <= set(
        schemas["CheckResult"]["properties"]
    )


@pytest.mark.parametrize(
    ("folder", "patterns"),
    [(APP, ("*.py",)), (WEB, ("*.ts", "*.tsx", "*.json", "*.css"))],
    ids=["api", "web"],
)
def test_no_source_file_mentions_the_old_system(folder: Path, patterns: tuple[str, ...]) -> None:
    offenders = []
    for pattern in patterns:
        for path in folder.rglob(pattern):
            if path.name.endswith((".test.ts", ".test.tsx")):
                continue  # tests may assert that these words are absent
            text = path.read_text(encoding="utf-8")
            if any(
                word in text
                for word in ("BUY", "CONSIDER", "SKIP", "market_avg", "delta_pct", "VerdictBadge")
            ):
                offenders.append(path.name)
    assert offenders == []
