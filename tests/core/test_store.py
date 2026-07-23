"""Testes de store.py (Fase 1), incluindo simulação de crash na escrita atômica."""

import json
import os

import pytest

from src.core.schema.geometry import Point3D
from src.core.schema.orientation import (
    BoxFace,
    BoxOrientationConfig,
    BoxVertex,
    Calibration,
    CameraOrientation,
    CameraRole,
)
from src.core.schema.profile import Profile
from src.core.schema.result import AnalysisResult
from src.core.store import (
    CorruptStoreError,
    ProfileNotFoundError,
    ProfileStore,
    ResultNotFoundError,
    ResultStore,
    SchemaVersionError,
    StoreWriteError,
    atomic_write_json,
)


def _calibration() -> Calibration:
    top = CameraOrientation(
        role=CameraRole.TOP,
        face_viewed=BoxFace.TOP,
        corner_vertices=[
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
            BoxVertex.TOP_BACK_RIGHT,
            BoxVertex.TOP_BACK_LEFT,
        ],
    )
    side = CameraOrientation(
        role=CameraRole.SIDE,
        face_viewed=BoxFace.FRONT,
        corner_vertices=[
            BoxVertex.TOP_FRONT_RIGHT,
            BoxVertex.TOP_FRONT_LEFT,
            BoxVertex.BOTTOM_FRONT_RIGHT,
            BoxVertex.BOTTOM_FRONT_LEFT,
        ],
    )
    return Calibration(
        box_cm=Point3D(x=10.0, y=20.0, z=30.0),
        px_per_cm=Point3D(x=5.0, y=5.0, z=5.0),
        fps=30.0,
        orientation=BoxOrientationConfig(top_camera=top, side_camera=side),
    )


# ---- ProfileStore ------------------------------------------------------------

def test_profile_save_get_round_trip_via_disk(tmp_workspace):
    store = ProfileStore(tmp_workspace)
    p = Profile(name="bee", top_video_path="t.mp4", box_cm=Point3D(x=1.0, y=2.0, z=3.0))
    store.save(p)
    # nova instância lê do disco, não da memória
    assert ProfileStore(tmp_workspace).get("bee") == p


def test_profile_list_sorted(tmp_workspace):
    store = ProfileStore(tmp_workspace)
    store.save(Profile(name="zeta"))
    store.save(Profile(name="alpha"))
    assert store.list() == ["alpha", "zeta"]


def test_profile_get_missing_raises(tmp_workspace):
    with pytest.raises(ProfileNotFoundError):
        ProfileStore(tmp_workspace).get("nope")


def test_profile_delete_missing_raises(tmp_workspace):
    with pytest.raises(ProfileNotFoundError):
        ProfileStore(tmp_workspace).delete("nope")


def test_profile_delete_removes(tmp_workspace):
    store = ProfileStore(tmp_workspace)
    store.save(Profile(name="bee"))
    store.delete("bee")
    with pytest.raises(ProfileNotFoundError):
        store.get("bee")


def test_profile_store_corrupt_json(tmp_workspace):
    tmp_workspace.ensure_dirs()
    tmp_workspace.profiles_file().write_text("{not json", encoding="utf-8")
    with pytest.raises(CorruptStoreError):
        ProfileStore(tmp_workspace).list()


# ---- ResultStore -------------------------------------------------------------

def test_result_save_load_round_trip(tmp_workspace):
    store = ResultStore(tmp_workspace)
    result = AnalysisResult(profile="bee", calibration=_calibration())
    store.save(result)
    assert store.exists("bee")
    assert ResultStore(tmp_workspace).load("bee") == result


def test_result_load_missing_raises(tmp_workspace):
    with pytest.raises(ResultNotFoundError):
        ResultStore(tmp_workspace).load("nope")


def test_result_load_corrupt_json_chains_cause(tmp_workspace):
    tmp_workspace.ensure_dirs()
    tmp_workspace.result_file("bad").write_text("{not json", encoding="utf-8")
    with pytest.raises(CorruptStoreError) as excinfo:
        ResultStore(tmp_workspace).load("bad")
    assert excinfo.value.__cause__ is not None


def test_result_load_schema_version_mismatch(tmp_workspace):
    store = ResultStore(tmp_workspace)
    result = AnalysisResult(profile="bee", calibration=_calibration())
    store.save(result)
    # reescreve com schema_version diferente
    path = tmp_workspace.result_file("bee")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["schema_version"] = "0.1"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SchemaVersionError):
        store.load("bee")


def test_result_exists_false_when_absent(tmp_workspace):
    assert ResultStore(tmp_workspace).exists("nope") is False


# ---- Escrita atômica ---------------------------------------------------------

def _tmp_orphans(directory):
    return [p for p in directory.iterdir() if p.name.startswith(".") and ".tmp-" in p.name]


def test_atomic_write_crash_simulation(tmp_workspace, monkeypatch):
    tmp_workspace.ensure_dirs()
    target = tmp_workspace.result_file("bee")
    target.write_text("CONTEUDO ANTERIOR", encoding="utf-8")

    def _boom(src, dst):
        raise OSError("simulated crash during replace")

    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(StoreWriteError) as excinfo:
        atomic_write_json(target, "CONTEUDO NOVO")

    # (a) destino intacto
    assert target.read_text(encoding="utf-8") == "CONTEUDO ANTERIOR"
    # (b) exatamente 1 tmp órfão
    orphans = _tmp_orphans(target.parent)
    assert len(orphans) == 1
    # (c) StoreWriteError com __cause__ sendo o OSError simulado
    assert isinstance(excinfo.value.__cause__, OSError)


def test_atomic_write_success_leaves_no_tmp(tmp_workspace):
    tmp_workspace.ensure_dirs()
    target = tmp_workspace.result_file("bee")
    atomic_write_json(target, "conteudo final")
    assert target.read_text(encoding="utf-8") == "conteudo final"
    assert _tmp_orphans(target.parent) == []
