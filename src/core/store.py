"""Persistência atômica com schema (Fase 1, Wave 3 / T9).

Substitui `ExportModule/jsonUtils.py` (que criava arquivo vazio silenciosamente
quando ausente, não tratava JSON corrompido e escrevia direto no destino sem
atomicidade). Aqui: escrita atômica (tmp + `os.replace`), erros tipados, e nunca
criar arquivo vazio automaticamente.

Duas stores separadas:
- `ProfileStore` — perfis/config (era `cache/configs.json`), arquivo único.
- `ResultStore` — `AnalysisResult` por run (era `cache/outputs/<perfil>.json`),
  com checagem de `schema_version`.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from src.core.schema.profile import Profile
from src.core.schema.result import SCHEMA_VERSION, AnalysisResult
from src.core.workspace import Workspace


class StoreError(Exception):
    """Base de todo erro de persistência do core."""


class ProfileNotFoundError(StoreError):
    def __init__(self, name: str) -> None:
        super().__init__(f"perfil '{name}' não encontrado")
        self.name = name


class ResultNotFoundError(StoreError):
    def __init__(self, profile: str) -> None:
        super().__init__(f"resultado para o perfil '{profile}' não encontrado")
        self.profile = profile


class CorruptStoreError(StoreError):
    """JSON malformado ou falha de validação Pydantic ao carregar um arquivo do store."""


class SchemaVersionError(CorruptStoreError):
    """schema_version do arquivo carregado é diferente da SCHEMA_VERSION atual do core."""


class StoreWriteError(StoreError):
    """Falha ao escrever atomicamente (ex.: os.replace falhou)."""


def atomic_write_json(path: Path, content: str) -> None:
    """Escreve `content` em `path` de forma atômica.

    Sequência: cria arquivo temporário no MESMO diretório do destino (necessário
    para o os.replace final ser atômico em qualquer filesystem/SO),
    escreve+flush+fsync, depois os.replace(tmp, destino).

    Comportamento deliberado em caso de crash entre o fsync e o os.replace (ex.
    processo morto, queda de energia): o arquivo temporário FICA ÓRFÃO no
    diretório (não há bloco try/except/finally de limpeza ao redor do os.replace)
    — e o arquivo de destino permanece exatamente como estava antes (inteiro, se
    já existia; ausente, se não existia), porque os.replace() é atômico tanto em
    POSIX quanto no Windows. Essa é a garantia que importa (destino nunca fica
    parcialmente escrito); o arquivo .tmp-* órfão é um efeito colateral aceito,
    não um bug — uma rotina de limpeza de workspace (fora do escopo da Fase 1)
    pode varrer esses arquivos depois.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.parent / f".{path.name}.tmp-{uuid4().hex[:8]}"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        raise StoreWriteError(f"falha ao escrever arquivo temporário {tmp_path}: {exc}") from exc

    try:
        os.replace(tmp_path, path)
    except OSError as exc:
        raise StoreWriteError(f"falha ao substituir {path} atomicamente: {exc}") from exc


class ProfileStore:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def _load_all(self) -> dict[str, Profile]:
        path = self._workspace.profiles_file()
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CorruptStoreError(f"profiles.json corrompido: {exc}") from exc
        try:
            return {name: Profile.model_validate(data) for name, data in raw.items()}
        except ValidationError as exc:
            raise CorruptStoreError(f"profiles.json com dado inválido: {exc}") from exc

    def list(self) -> list[str]:
        return sorted(self._load_all().keys())

    def get(self, name: str) -> Profile:
        profiles = self._load_all()
        if name not in profiles:
            raise ProfileNotFoundError(name)
        return profiles[name]

    def save(self, profile: Profile) -> None:
        profiles = self._load_all()
        profiles[profile.name] = profile
        payload = {name: p.model_dump(mode="json") for name, p in profiles.items()}
        atomic_write_json(self._workspace.profiles_file(), json.dumps(payload, indent=2))

    def delete(self, name: str) -> None:
        profiles = self._load_all()
        if name not in profiles:
            raise ProfileNotFoundError(name)
        del profiles[name]
        payload = {n: p.model_dump(mode="json") for n, p in profiles.items()}
        atomic_write_json(self._workspace.profiles_file(), json.dumps(payload, indent=2))


class ResultStore:
    def __init__(self, workspace: Workspace) -> None:
        self._workspace = workspace

    def save(self, result: AnalysisResult) -> None:
        path = self._workspace.result_file(result.profile)
        atomic_write_json(path, result.model_dump_json(indent=2))

    def load(self, profile: str) -> AnalysisResult:
        path = self._workspace.result_file(profile)
        if not path.exists():
            raise ResultNotFoundError(profile)
        try:
            result = AnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise CorruptStoreError(f"resultado de '{profile}' corrompido: {exc}") from exc
        if result.schema_version != SCHEMA_VERSION:
            raise SchemaVersionError(
                f"resultado de '{profile}' tem schema_version={result.schema_version!r}, "
                f"esperado {SCHEMA_VERSION!r}"
            )
        return result

    def exists(self, profile: str) -> bool:
        return self._workspace.result_file(profile).exists()
