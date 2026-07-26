"""Camada de serviço da GUI (Fase 4.0).

Toda tela da GUI fala com o mundo através disto — nunca lê/escreve arquivo direto,
nunca chama a orquestração da pipeline diretamente. Substitui o estado hoje
pendurado em `root.top_video_path`/`root.side_video_path` (StringVar no root Tk) e
o acesso espalhado a `cache/configs.json` via `jsonUtils`.

Nota de nomenclatura: o plano fala em `ProfileConfig`; o modelo real da Fase 1 se
chama `Profile` (`src/core/schema/profile.py`) e já tem o campo
`orientation: BoxOrientationConfig | None` que o plano pedia para adicionar na 4.0
— nada a adicionar no schema, só consumir.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.app.runner import execute_analysis, run_exporter
from src.core.pipeline import Pipeline, RunRequest, RunResult
from src.core.plugin import PluginKind, PluginManifest
from src.core.plugin_registry import PluginRegistry
from src.core.schema.geometry import Point2D, Point3D
from src.core.schema.orientation import BoxOrientationConfig, CameraOrientation
from src.core.schema.profile import Profile
from src.core.schema.result import AnalysisResult
from src.core.store import ProfileNotFoundError, ProfileStore, ResultStore
from src.core.workspace import Workspace

NEW_PROFILE_PLACEHOLDER = "Novo perfil de analise"


@dataclass
class ProgressEvent:
    stage: str
    fraction: float | None = None
    message: str = ""


@dataclass
class SessionState:
    """Estado de configuração em andamento, compartilhado por todas as telas da GUI.

    Substitui os StringVar pendurados no root Tk (`root.top_video_path`, etc.) e o
    espalhamento de estado entre as telas irmãs do legado — agora há um único objeto
    mutável, acessível via `service.session`, que a hub lê para montar o `Profile`."""

    profile_name: str = ""
    top_video_path: str = ""
    side_video_path: str = ""
    width_cm: str = ""
    height_cm: str = ""
    depth_cm: str = ""
    perspective_points_top: list[list[int]] = field(default_factory=list)
    perspective_points_side: list[list[int]] = field(default_factory=list)
    border_points_top: list[list[int]] | None = None
    border_points_side: list[list[int]] | None = None
    orientation_top: CameraOrientation | None = None
    orientation_side: CameraOrientation | None = None

    def reset(self) -> None:
        self.top_video_path = ""
        self.side_video_path = ""
        self.width_cm = ""
        self.height_cm = ""
        self.depth_cm = ""
        self.perspective_points_top = []
        self.perspective_points_side = []
        self.border_points_top = None
        self.border_points_side = None
        self.orientation_top = None
        self.orientation_side = None

    def build_orientation(self) -> BoxOrientationConfig | None:
        """Compõe o `BoxOrientationConfig` quando as duas câmeras estão configuradas."""
        if self.orientation_top is None or self.orientation_side is None:
            return None
        return BoxOrientationConfig(
            top_camera=self.orientation_top, side_camera=self.orientation_side
        )

    def load_from_profile(self, profile: Profile) -> None:
        self.profile_name = profile.name
        self.top_video_path = profile.top_video_path
        self.side_video_path = profile.side_video_path
        self.width_cm = str(profile.box_cm.x) if profile.box_cm.x else ""
        self.height_cm = str(profile.box_cm.y) if profile.box_cm.y else ""
        self.depth_cm = str(profile.box_cm.z) if profile.box_cm.z else ""
        self.perspective_points_top = [[int(p.x), int(p.y)] for p in profile.perspective_points_top]
        self.perspective_points_side = [[int(p.x), int(p.y)] for p in profile.perspective_points_side]
        self.border_points_top = (
            [[int(p.x), int(p.y)] for p in profile.border_points_top]
            if profile.border_points_top else None
        )
        self.border_points_side = (
            [[int(p.x), int(p.y)] for p in profile.border_points_side]
            if profile.border_points_side else None
        )
        if profile.orientation is not None:
            self.orientation_top = profile.orientation.top_camera
            self.orientation_side = profile.orientation.side_camera
        else:
            self.orientation_top = None
            self.orientation_side = None

    def to_profile(self) -> Profile:
        def _points(raw: list[list[int]] | None) -> list[Point2D]:
            return [Point2D(x=float(x), y=float(y)) for x, y in raw] if raw else []

        def _cm(value: str) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        return Profile(
            name=self.profile_name,
            top_video_path=self.top_video_path,
            side_video_path=self.side_video_path,
            box_cm=Point3D(x=_cm(self.width_cm), y=_cm(self.height_cm), z=_cm(self.depth_cm)),
            perspective_points_top=_points(self.perspective_points_top),
            perspective_points_side=_points(self.perspective_points_side),
            border_points_top=_points(self.border_points_top),
            border_points_side=_points(self.border_points_side),
            orientation=self.build_orientation(),
        )


class AppService:
    """Fachada fina sobre `ProfileStore`/`ResultStore`/runner/registry."""

    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace
        self._profiles = ProfileStore(workspace)
        self._results = ResultStore(workspace)
        self.session = SessionState()

    @property
    def workspace(self) -> Workspace:
        return self._workspace

    # --- perfis (ProfileStore) ---
    def list_profiles(self) -> list[str]:
        return self._profiles.list()

    def load_profile(self, name: str) -> Profile:
        return self._profiles.get(name)

    def save_profile(self, name: str, config: Profile) -> None:
        # `name` é a fonte de verdade do nome persistido; garante consistência
        # mesmo que o caller monte o Profile com outro `.name`.
        if config.name != name:
            config = config.model_copy(update={"name": name})
        self._profiles.save(config)

    def new_profile_placeholder_name(self) -> str:
        return NEW_PROFILE_PLACEHOLDER

    def save_orientation(self, name: str, orientation: BoxOrientationConfig) -> None:
        """Persiste a orientação dentro do perfil nomeado, preservando o resto."""
        try:
            profile = self._profiles.get(name)
        except ProfileNotFoundError:
            profile = Profile(name=name)
        updated = profile.model_copy(update={"orientation": orientation})
        self._profiles.save(updated)

    # --- execução (delega 100% ao runner; caminho idêntico ao da CLI) ---
    def run_pipeline(
        self,
        profile: str,
        on_progress: Callable[[ProgressEvent], None] | None = None,
        *,
        require_gpu: bool = False,
    ) -> AnalysisResult:
        if on_progress is not None:
            on_progress(ProgressEvent(stage="start", message=f"Processando '{profile}'..."))
        result = execute_analysis(self._workspace, profile, require_gpu=require_gpu)
        if on_progress is not None:
            on_progress(ProgressEvent(stage="done", fraction=1.0, message="Concluído"))
        return result

    def run_metadata(self, profile: str) -> RunResult:
        """Reexecuta SÓ os plugins de metadata sobre o `AnalysisResult` já persistido.

        É o botão "Executar módulos de metadados" do hub (o mesmo papel do antigo
        `execute_metadata_module_calls`): permite testar um módulo de metadata novo
        sem refazer Capture→Fuse, no mesmo espírito do fluxo "reprocessar sem refazer
        etapas anteriores" (ux-design-detalhado.md seção 5). Delega ao
        `Pipeline.run`, que é exatamente o estágio de metadata isolado (Fase 2).
        """
        from src.app.plugins import metadata_search_paths

        registry = PluginRegistry()
        registry.discover(metadata_search_paths(self._workspace))
        request = RunRequest(profile=profile, workspace=str(self._workspace.root))
        return Pipeline(registry).run(request)

    # --- plugins (delega ao PluginRegistry) ---
    def list_plugins(self, kind: PluginKind | None = None) -> list[PluginManifest]:
        from src.app.plugins import default_search_paths

        registry = PluginRegistry()
        registry.discover(default_search_paths(self._workspace))
        return registry.manifests(kind)

    # --- resultados/export (delega ao ResultStore + plugins exporter) ---
    def load_result(self, profile: str) -> AnalysisResult | None:
        if not self._results.exists(profile):
            return None
        return self._results.load(profile)

    def export(self, profile: str, exporter_name: str, **kwargs: object) -> Path:
        result = self._results.load(profile)
        return run_exporter(self._workspace, result, exporter_name, **kwargs)
