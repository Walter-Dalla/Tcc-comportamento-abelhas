"""Abstração de workspace (Fase 1, Wave 1 / T6).

Substitui todo caminho relativo a CWD do código legado por uma raiz explícita e
resolvível. `resolve()` é uma operação pura (só decide o caminho); a criação de
diretórios é o efeito colateral explícito `ensure_dirs()`, chamado pelo caller
quando realmente for escrever algo. Pydantic v2 tem suporte nativo a
`pathlib.Path` como tipo de campo — nenhum validador customizado é necessário.
"""

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class Workspace(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=False)
    root: Path

    @property
    def config_path(self) -> Path:
        return self.root / "config"

    @property
    def outputs(self) -> Path:
        return self.root / "outputs"

    @property
    def plugins(self) -> Path:
        return self.root / "plugins"

    def profiles_file(self) -> Path:
        return self.config_path / "profiles.json"

    def result_file(self, profile: str) -> Path:
        return self.outputs / f"{profile}.json"

    def ensure_dirs(self) -> None:
        for path in (self.config_path, self.outputs, self.plugins):
            path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def resolve(cls, cli_path: Path | None = None) -> "Workspace":
        """Precedência: --workspace (cli_path) -> env ANIMALTRACK_WORKSPACE -> ~/.animaltrack."""
        if cli_path is not None:
            return cls(root=cli_path)
        env_value = os.environ.get("ANIMALTRACK_WORKSPACE")
        if env_value:
            return cls(root=Path(env_value))
        return cls(root=Path.home() / ".animaltrack")
