"""Instalação de plugin estilo "git-tap curado" (Fase 6, workstream C).

Implementa o miolo de `animaltrack plugin install <path|git-url>`, separado do
`cli.py` para ser testável sem passar por Typer.

**Sem backend de marketplace**: não existe índice nem servidor que resolva nome →
pacote. `install` sempre recebe um path local ou uma URL git LITERAL dada pelo
usuário; "marketplace" aqui é só o formato de contrato (`plugin.toml`) + curadoria
manual. Ver `docs/PLUGIN_CONTRACT.md`.

Fluxo (plano seção 3.3):
  1. detecta origem (path local existente vs. URL git);
  2. copia/clona para um diretório de STAGING temporário — nunca valida no destino;
  3. valida o manifest inteiro no staging, acumulando TODAS as falhas;
  4. qualquer falha => aborta, descarta staging, nada é escrito no workspace;
  5. nome final vem do manifest (`[plugin].name`), não do path/URL;
  6. colisão de nome => recusa, a menos que `force=True`.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from packaging.specifiers import InvalidSpecifier, SpecifierSet

from src.core.plugin import Plugin, PluginKind, PluginManifest, PluginSpec
from src.core.plugin_registry import SUPPORTED_API_VERSIONS, PluginRegistry
from src.core.schema.result import SCHEMA_VERSION
from src.core.workspace import Workspace


class PluginInstallError(Exception):
    """Falha de instalação com uma ou mais mensagens de erro para o usuário."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass
class InstalledPlugin:
    name: str
    version: str
    kind: PluginKind
    path: Path


def install_plugin(
    source: str, workspace: Workspace, *, force: bool = False
) -> InstalledPlugin:
    """Instala um plugin em `<workspace>/plugins/<name>/`. Ver docstring do módulo."""
    with tempfile.TemporaryDirectory(prefix="animaltrack-plugin-") as tmp:
        staging = Path(tmp) / "staging"
        _fetch_to_staging(source, staging)

        manifest = _validate_staging(staging)

        destination = workspace.plugins / manifest.name
        if destination.exists() and not force:
            installed = _installed_version(destination)
            raise PluginInstallError(
                [
                    f"plugin '{manifest.name}' já instalado em {destination} "
                    f"(versão {installed}); a versão nova é {manifest.version}. "
                    f"Use --force para sobrescrever."
                ]
            )

        workspace.plugins.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(staging, destination)

    return InstalledPlugin(
        name=manifest.name,
        version=manifest.version,
        kind=manifest.kind,
        path=destination,
    )


def _fetch_to_staging(source: str, staging: Path) -> None:
    candidate = Path(source)
    if candidate.exists():
        if not candidate.is_dir():
            raise PluginInstallError([f"'{source}' não é um diretório de plugin"])
        # cópia (nunca symlink): a instalação é um snapshot pontual
        shutil.copytree(candidate, staging)
        _strip_git_metadata(staging)
        return

    # senão, trata como URL git
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", source, str(staging)],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:  # git não instalado
        raise PluginInstallError([f"git não encontrado no PATH: {exc}"]) from exc
    except subprocess.CalledProcessError as exc:
        raise PluginInstallError(
            [f"falha ao clonar '{source}': {(exc.stderr or '').strip() or exc}"]
        ) from exc
    # instalação não é "tracking" de upstream — sem responsabilidade de auto-update
    _strip_git_metadata(staging)


def _strip_git_metadata(staging: Path) -> None:
    git_dir = staging / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir, ignore_errors=True)


def _installed_version(destination: Path) -> str:
    try:
        return PluginManifest.from_toml(destination / "plugin.toml").version
    except Exception:
        return "desconhecida"


def _validate_staging(staging: Path) -> PluginManifest:
    """Valida o manifest ANTES de aceitar, acumulando TODAS as falhas."""
    manifest_path = staging / "plugin.toml"
    if not manifest_path.is_file():
        raise PluginInstallError([f"plugin.toml não encontrado em {staging}"])

    try:
        manifest = PluginManifest.from_toml(manifest_path)
    except Exception as exc:
        # campos obrigatórios ausentes / kind fora do enum / TOML malformado
        raise PluginInstallError([f"plugin.toml inválido: {exc}"]) from exc

    errors: list[str] = []

    if manifest.api_version not in SUPPORTED_API_VERSIONS:
        errors.append(
            f"api_version '{manifest.api_version}' não suportada "
            f"(suportadas: {sorted(SUPPORTED_API_VERSIONS)})"
        )

    try:
        if not SpecifierSet(manifest.schema).contains(SCHEMA_VERSION):
            errors.append(
                f"schema '{manifest.schema}' incompatível com o core "
                f"(SCHEMA_VERSION={SCHEMA_VERSION})"
            )
    except InvalidSpecifier:
        errors.append(f"schema '{manifest.schema}' não é um range PEP 440 válido")

    # `entry` deve resolver e a classe deve ser subclasse da base correta do kind.
    module_name, sep, class_name = manifest.entry.partition(":")
    if not sep or not module_name or not class_name:
        errors.append(f"entry '{manifest.entry}' não está no formato 'modulo:Classe'")
    elif not (staging / f"{module_name}.py").is_file():
        errors.append(f"entry aponta para '{module_name}.py', que não existe no plugin")
    else:
        errors.extend(_validate_entry_class(manifest, staging))

    if errors:
        raise PluginInstallError(errors)
    return manifest


def _validate_entry_class(manifest: PluginManifest, staging: Path) -> list[str]:
    """Importa o entry no staging e confere a classe-base exigida pelo kind."""
    registry = PluginRegistry()
    try:
        instance = registry.instantiate(PluginSpec(manifest=manifest, source_dir=staging))
    except Exception as exc:
        return [f"falha ao carregar entry '{manifest.entry}': {exc}"]
    if not isinstance(instance, Plugin):
        return [f"entry '{manifest.entry}' não é um Plugin"]
    return []


def list_installed(workspace: Workspace) -> list[PluginManifest]:
    """Manifests dos plugins instalados em `<workspace>/plugins/`."""
    registry = PluginRegistry()
    registry.discover([workspace.plugins])
    return registry.manifests()


def remove_plugin(name: str, workspace: Workspace) -> Path:
    """Remove `<workspace>/plugins/<name>/`. Levanta se não existir."""
    destination = workspace.plugins / name
    if not destination.is_dir():
        raise PluginInstallError([f"plugin '{name}' não está instalado em {workspace.plugins}"])
    shutil.rmtree(destination)
    return destination
