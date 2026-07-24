"""Testes do AppService (Fase 4.0)."""

from __future__ import annotations

from pathlib import Path

from src.app import service as service_module
from src.app.service import AppService
from src.core.schema.geometry import Point3D
from src.core.schema.profile import Profile
from src.core.workspace import Workspace


def _workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    return ws


def test_save_and_load_profile_roundtrip(tmp_path: Path) -> None:
    svc = AppService(_workspace(tmp_path))
    profile = Profile(
        name="p1",
        top_video_path="top.avi",
        side_video_path="side.avi",
        box_cm=Point3D(x=16.0, y=12.0, z=12.0),
    )
    svc.save_profile("p1", profile)

    assert svc.list_profiles() == ["p1"]
    loaded = svc.load_profile("p1")
    assert loaded.top_video_path == "top.avi"
    assert loaded.box_cm.x == 16.0


def test_save_profile_forces_name_consistency(tmp_path: Path) -> None:
    svc = AppService(_workspace(tmp_path))
    profile = Profile(name="wrong")
    svc.save_profile("right", profile)
    assert svc.list_profiles() == ["right"]


def test_run_pipeline_delegates_to_runner(tmp_path: Path, monkeypatch) -> None:
    svc = AppService(_workspace(tmp_path))
    calls: list[tuple[str, bool]] = []
    sentinel = object()

    def fake_execute(workspace, profile_name, *, require_gpu=False):
        calls.append((profile_name, require_gpu))
        return sentinel

    monkeypatch.setattr(service_module, "execute_analysis", fake_execute)

    result = svc.run_pipeline("fixture01")
    assert result is sentinel
    assert calls == [("fixture01", False)]


def test_list_plugins_returns_manifests(tmp_path: Path) -> None:
    svc = AppService(_workspace(tmp_path))
    names = {m.name for m in svc.list_plugins()}
    # descobre os plugins built-in (metadata + exporter).
    assert {"speed", "border", "route-plot", "pdf-report"} <= names
