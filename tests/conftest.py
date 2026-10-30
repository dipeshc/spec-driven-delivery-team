from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
SDT_PATH = ROOT / "bin" / "sdt"


def load_sdt() -> ModuleType:
    """Import bin/sdt (no .py suffix) as a module named `sdt`."""
    if "sdt" in sys.modules:
        return sys.modules["sdt"]
    loader = importlib.machinery.SourceFileLoader("sdt", str(SDT_PATH))
    spec = importlib.util.spec_from_loader("sdt", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["sdt"] = module
    loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def sdt() -> ModuleType:
    return load_sdt()
