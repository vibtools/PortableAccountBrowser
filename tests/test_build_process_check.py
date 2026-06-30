from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "assert_app_closed.py"
SPEC = importlib.util.spec_from_file_location("assert_app_closed", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_build_process_tree_includes_current_and_parents(monkeypatch) -> None:
    monkeypatch.setattr(MODULE.os, "getpid", lambda: 300)
    fake_current = SimpleNamespace(parents=lambda: [SimpleNamespace(pid=200), SimpleNamespace(pid=100)])
    monkeypatch.setattr(MODULE.psutil, "Process", lambda pid: fake_current)
    assert MODULE.current_build_process_tree_pids() == {100, 200, 300}


def test_build_process_tree_is_failure_tolerant(monkeypatch) -> None:
    monkeypatch.setattr(MODULE.os, "getpid", lambda: 500)
    def denied(pid):
        raise MODULE.psutil.AccessDenied(pid=pid)
    monkeypatch.setattr(MODULE.psutil, "Process", denied)
    assert MODULE.current_build_process_tree_pids() == {500}
