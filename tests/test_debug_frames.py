"""Export de frames de debug do Detect — Opção 2 da seção 6 do `ux-design-detalhado.md`.

Trava o que a decisão exige: amostragem (1 a cada N + toda falha de detecção),
gravação fora da thread do pipeline, descarte em vez de bloqueio quando a fila
enche, e o caminho `<workspace>/debug/<perfil>/` compartilhado por CLI e GUI.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import numpy as np
import pytest

from src.core.frames import RectifiedFrame
from src.core.schema.orientation import CameraRole
from src.core.workspace import Workspace
from src.stages.detect.debug import DebugFrameWriter
from src.stages.detect.plugin import BackgroundSubtractionDetector
from tests.gui_helpers import has_display
from tests.stages.test_stage_detect import FakeCapture, IdentityRectifier, _uniform


def _wait_for(predicate, timeout: float = 5.0) -> bool:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


# --- writer ---------------------------------------------------------------------
def test_writer_writes_png_per_view(tmp_path: Path) -> None:
    writer = DebugFrameWriter(tmp_path / "debug", every=2)
    writer.submit("top", 4, _uniform(255), detected=True)
    writer.submit("side", 7, _uniform(255), detected=False)
    writer.close()

    assert (tmp_path / "debug" / "top" / "frame_000004_det.png").is_file()
    assert (tmp_path / "debug" / "side" / "frame_000007_nodet.png").is_file()
    assert writer.written == 2
    assert writer.dropped == 0


def test_should_capture_samples_and_always_keeps_failures(tmp_path: Path) -> None:
    writer = DebugFrameWriter(tmp_path / "debug", every=10)
    try:
        assert writer.should_capture(0, detected=True)
        assert not writer.should_capture(3, detected=True)
        assert writer.should_capture(10, detected=True)
        # falha de detecção é sempre capturada (é o caso a inspeciona
        assert writer.should_capture(3, detected=False)
    finally:
        writer.close()


def test_writer_never_blocks_the_caller(tmp_path: Path) -> None:
    """Fila cheia => descarte contabilizado, nunca espera pelo consumidor."""
    writer = DebugFrameWriter(tmp_path / "debug", every=1, max_queue=1)
    try:
        image = _uniform(255)
        started = time.monotonic()
        for index in range(200):
            writer.submit("top", index, image, detected=True)
        elapsed = time.monotonic() - started
        assert elapsed < 2.0  # 200 submits sem bloquear
        assert writer.written + writer.dropped <= 200
    finally:
        writer.close()


def test_writer_runs_off_the_calling_thread(tmp_path: Path) -> None:
    writer = DebugFrameWriter(tmp_path / "debug", every=1)
    try:
        writer.submit("top", 0, _uniform(255), detected=True)
        assert _wait_for(lambda: writer.written == 1)
        # a gravação aconteceu numa thread própria, não na thread do teste
        names = {t.name for t in threading.enumerate()}
        assert "animaltrack-debug-writer" in names
    finally:
        writer.close()


def test_close_is_idempotent(tmp_path: Path) -> None:
    writer = DebugFrameWriter(tmp_path / "debug")
    writer.close()
    writer.close()
    assert writer.submit("top", 0, _uniform(255), detected=True) is False


def test_writer_rejects_invalid_sampling(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        DebugFrameWriter(tmp_path / "debug", every=0)


# --- integração com o Detect ----------------------------------------------------
def _detector(debug: DebugFrameWriter | None) -> BackgroundSubtractionDetector:
    frames = [_uniform(200) for _ in range(3)]
    det = BackgroundSubtractionDetector(
        FakeCapture(frames), IdentityRectifier(), CameraRole.TOP, 500, debug
    )
    det.setup()
    return det


def test_detector_exports_failed_detection_frames(tmp_path: Path) -> None:
    writer = DebugFrameWriter(tmp_path / "debug", every=1000)
    det = _detector(writer)
    # frame idêntico ao fundo -> nenhuma detecção -> sempre capturado
    out = det.detect(RectifiedFrame(image=_uniform(200), role=CameraRole.TOP, frame_index=7))
    writer.close()

    assert out.detections == []
    assert (tmp_path / "debug" / "top" / "frame_000007_nodet.png").is_file()


def test_detector_without_debug_writes_nothing(tmp_path: Path) -> None:
    det = _detector(None)
    out = det.detect(RectifiedFrame(image=_uniform(200), role=CameraRole.TOP, frame_index=0))
    assert out.detections == []
    assert not (tmp_path / "debug").exists()


def test_detection_result_is_identical_with_and_without_debug(tmp_path: Path) -> None:
    """O export de debug é observacional: não muda o resultado da detecção."""
    image = _uniform(200)
    image[10:20, 10:20] = 20
    frame = RectifiedFrame(image=image, role=CameraRole.TOP, frame_index=1)

    plain = _detector(None).detect(frame)
    writer = DebugFrameWriter(tmp_path / "debug", every=1)
    instrumented = _detector(writer).detect(frame)
    writer.close()

    assert plain.model_dump() == instrumented.model_dump()
    assert (tmp_path / "debug" / "top" / "frame_000001_det.png").is_file()


# --- caminho do workspace (CLI e GUI apontam para o mesmo lugar) -----------------
def test_workspace_debug_dir_is_per_profile() -> None:
    ws = Workspace(root=Path("/ws"))
    assert ws.debug == Path("/ws/debug")
    assert ws.debug_dir("fish01") == Path("/ws/debug/fish01")


def test_runner_passes_debug_dir_only_when_requested(tmp_path: Path, monkeypatch) -> None:
    from src.app import runner
    from src.core.schema.profile import Profile

    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    captured: list[Path | None] = []

    def fake_run(profile, **kwargs):  # type: ignore[no-untyped-def]
        captured.append(kwargs.get("debug_dir"))
        return "result"

    monkeypatch.setattr(runner, "run_cpu_analysis", fake_run)
    monkeypatch.setattr(runner.ProfileStore, "get", lambda self, name: Profile(name=name))
    monkeypatch.setattr(runner.ResultStore, "save", lambda self, result: None)

    runner.execute_analysis(ws, "fish01")
    runner.execute_analysis(ws, "fish01", debug_frames=True)

    assert captured == [None, ws.debug_dir("fish01")]


# --- orquestração fecha o writer mesmo em falha ---------------------------------
def test_orchestration_closes_writer_on_failure(tmp_path: Path, monkeypatch) -> None:
    from src.core.schema.geometry import Point2D, Point3D
    from src.core.schema.profile import Profile
    from src.stages import orchestration
    from tests.fixtures.golden_config import golden_orientation

    closed: list[bool] = []

    class SpyWriter(DebugFrameWriter):
        def close(self, timeout: float = 10.0) -> None:
            closed.append(True)
            super().close(timeout)

    class BoomCapture:
        def __init__(self, *_a: object, **_k: object) -> None:
            pass

        def dimensions(self, _role: CameraRole) -> tuple[int, int]:
            return (10, 10)

        def open_single(self, _role: CameraRole):  # type: ignore[no-untyped-def]
            raise RuntimeError("captura falhou")

    monkeypatch.setattr(orchestration, "DebugFrameWriter", SpyWriter)
    monkeypatch.setattr(orchestration, "DualVideoFileCapture", BoomCapture)

    points = [Point2D(x=0, y=0), Point2D(x=9, y=0), Point2D(x=0, y=9), Point2D(x=9, y=9)]
    profile = Profile(
        name="p",
        box_cm=Point3D(x=1, y=1, z=1),
        perspective_points_top=points,
        perspective_points_side=points,
        orientation=golden_orientation(),
    )
    with pytest.raises(RuntimeError):
        orchestration.run_cpu_analysis(profile, debug_dir=tmp_path / "debug")
    assert closed == [True]


def test_orchestration_writes_debug_frames_end_to_end(tmp_path: Path) -> None:
    """Pipeline real na fixture curta: com `debug_dir`, aparecem PNGs das 2 views."""
    from tests.fixtures.golden_config import golden_profile

    profile = golden_profile()
    debug_dir = tmp_path / "debug" / profile.name
    orchestration_result = _run_with_debug(profile, debug_dir)

    assert orchestration_result.routes
    top_pngs = sorted((debug_dir / "top").glob("*.png"))
    side_pngs = sorted((debug_dir / "side").glob("*.png"))
    assert top_pngs and side_pngs
    assert np.asarray([p.stat().st_size for p in top_pngs]).min() > 0


def _run_with_debug(profile, debug_dir: Path):  # type: ignore[no-untyped-def]
    from src.stages.orchestration import run_cpu_analysis

    return run_cpu_analysis(
        profile, run_metadata=False, frame_block=10, debug_dir=debug_dir
    )


# --- GUI: caixa "Exportar frames de debug" + botão "Abrir pasta de debug" --------
gui = pytest.mark.skipif(not has_display(), reason="precisa de display Tk")


def _hub_with_profile(tmp_path: Path, container, profile: str = "fish01"):  # type: ignore[no-untyped-def]
    from src.app.gui.screens.config_hub import ConfigHubScreen
    from src.app.service import AppService

    ws = Workspace(root=tmp_path)
    ws.ensure_dirs()
    service = AppService(ws)
    service.session.profile_name = profile
    hub = ConfigHubScreen(service, show=lambda *a, **k: None)
    hub.frame = hub.build(container)
    return hub, service


@gui
def test_open_debug_folder_button_targets_workspace_debug_dir(
    tmp_path: Path, tk_root, monkeypatch
) -> None:
    import tkinter as tk

    from src.app.gui.screens import config_hub

    container = tk.Frame(tk_root)
    try:
        hub, service = _hub_with_profile(tmp_path, container)
        opened: list[Path] = []
        monkeypatch.setattr(config_hub, "open_folder", opened.append)
        hub._on_open_debug_folder()
        assert opened == [service.debug_dir("fish01")]
    finally:
        container.destroy()


@gui
@pytest.mark.parametrize("checked", [False, True])
def test_process_video_forwards_debug_frames_flag(
    tmp_path: Path, tk_root, monkeypatch, checked: bool
) -> None:
    import tkinter as tk

    from src.app.gui.screens import config_hub
    from tests.fixtures.golden_config import golden_orientation
    from tests.test_gui_flow_guards import _fill_session

    container = tk.Frame(tk_root)
    try:
        hub, service = _hub_with_profile(tmp_path, container)
        _fill_session(service, orientation=True)
        assert golden_orientation() is not None
        seen: list[bool] = []

        def fake_run_pipeline(profile, on_progress=None, *, require_gpu=False, debug_frames=False):
            seen.append(debug_frames)
            return object()

        monkeypatch.setattr(service, "run_pipeline", fake_run_pipeline)
        monkeypatch.setattr(config_hub.messagebox, "showinfo", lambda *a, **k: tk_root.quit())
        monkeypatch.setattr(config_hub.messagebox, "showerror", lambda *a, **k: tk_root.quit())
        hub.debug_frames.set(checked)

        assert hub._on_process_video() is not None
        tk_root.after(3000, tk_root.quit)
        tk_root.mainloop()
        assert seen == [checked]
    finally:
        container.destroy()
