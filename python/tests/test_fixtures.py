from pathlib import Path

import pytest

from mdm_processing.conformance import run_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "fixtures"
CONFIG_DIR = REPO_ROOT / "config"

FIXTURE_FILES = sorted(FIXTURES_DIR.rglob("*.yaml"))


@pytest.mark.parametrize("fixture_path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_fixture(fixture_path):
    run_fixture(fixture_path, CONFIG_DIR)
