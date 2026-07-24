"""Descoberta, versionamento, ordenação e isolamento de erro de plugins (Fase 2).

Substitui `MetadataModule/modulesInvoker.py`. Fluxo:
- `discover()` varre `search_paths` por `<root>/<nome>/plugin.toml` (1 nível),
  valida o manifest, registra preguiçosamente (não importa `plugin.py` ainda).
  Manifest inválido é logado e pulado — nunca derruba a descoberta.
- `instantiate()` valida `api_version`/`schema`, importa o entry, valida a
  subclasse exigida pelo kind, injeta o manifest e instancia.
- `for_kind()` instancia todos os specs do kind com isolamento de erro, depois
  ordena topologicamente por `before`/`after`/`priority` (Kahn).

Ver `docs/plans/fase2-detalhado.md` seções 1.4 e 3.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from packaging.specifiers import SpecifierSet

from src.core.errors import (
    PluginApiVersionError,
    PluginContractError,
    PluginLoadError,
    PluginNotFoundError,
    PluginOrderingCycleError,
    PluginSchemaVersionError,
)
from src.core.plugin import Plugin, PluginKind, PluginManifest, PluginSpec
from src.core.schema.result import SCHEMA_VERSION
from src.core.stages import Detector, MetadataPlugin, Tracker

logger = logging.getLogger("animaltrack.plugin_registry")

SUPPORTED_API_VERSIONS = {"1.0"}

# Kinds sem classe-base própria ainda (capture/rectify/fusion/exporter/interface)
# só exigem `Plugin` até a base específica existir (Fase 3/4).
_KIND_BASE_CLASS: dict[PluginKind, type[Plugin]] = {
    PluginKind.DETECTOR: Detector,
    PluginKind.TRACKER: Tracker,
    PluginKind.METADATA: MetadataPlugin,
}


class PluginRegistry:
    def __init__(self) -> None:
        self._specs: dict[tuple[PluginKind, str], PluginSpec] = {}
        self._instances: dict[tuple[PluginKind, str], Plugin] = {}
        self.discovery_warnings: list[str] = []

    # ---- discovery ---------------------------------------------------------
    def discover(self, search_paths: list[Path]) -> None:
        """Varre cada diretório de `search_paths` por `<root>/<nome>/plugin.toml`
        (1 nível). Registro preguiçoso: só lê/valida o manifest. Manifest inválido
        é logado e pulado."""
        for root in search_paths:
            if not root.is_dir():
                continue
            for manifest_path in sorted(root.glob("*/plugin.toml")):
                try:
                    manifest = PluginManifest.from_toml(manifest_path)
                except Exception as exc:  # manifest malformado / inválido
                    msg = f"manifest inválido em {manifest_path}: {exc}"
                    logger.warning(msg)
                    self.discovery_warnings.append(msg)
                    continue

                key = (manifest.kind, manifest.name)
                if key in self._specs:
                    msg = (
                        f"plugin duplicado {key} encontrado em {manifest_path} "
                        f"(mantendo o primeiro descoberto: {self._specs[key].source_dir})"
                    )
                    logger.warning(msg)
                    self.discovery_warnings.append(msg)
                    continue

                self._specs[key] = PluginSpec(manifest=manifest, source_dir=manifest_path.parent)

    def manifests(self, kind: PluginKind | None = None) -> list[PluginManifest]:
        """Manifests descobertos (sem instanciar/importar `plugin.py`).

        Read-only, seguro para listagem (`animaltrack list-plugins`): não dispara
        o import do entry point, então um plugin com dependência de pacote ausente
        ainda aparece na lista em vez de derrubá-la. Ordenado por (kind, name)."""
        specs = self._specs.values()
        chosen = [s.manifest for s in specs if kind is None or s.manifest.kind == kind]
        return sorted(chosen, key=lambda m: (m.kind.value, m.name))

    def register_instance(self, instance: Plugin) -> None:
        """Registra uma instância já construída diretamente (sem passar por disco).

        Útil para testes e para composição programática. A instância precisa ter
        `manifest` atribuído (ClassVar) — usado como chave `(kind, name)`.
        """
        key = (instance.manifest.kind, instance.manifest.name)
        self._instances[key] = instance
        self._specs.setdefault(
            key, PluginSpec(manifest=instance.manifest, source_dir=Path("."))
        )

    # ---- instantiate -------------------------------------------------------
    def instantiate(self, spec: PluginSpec) -> Plugin:
        """1) valida api_version; 2) valida schema range; 3) importa entry;
        4) valida subclasse; 5) injeta manifest; 6) instancia."""
        if spec.manifest.api_version not in SUPPORTED_API_VERSIONS:
            raise PluginApiVersionError(
                f"{spec.manifest.name}: api_version {spec.manifest.api_version} não suportada "
                f"(suportadas: {sorted(SUPPORTED_API_VERSIONS)})"
            )

        if not SpecifierSet(spec.manifest.schema).contains(SCHEMA_VERSION):
            raise PluginSchemaVersionError(
                f"{spec.manifest.name}: schema {spec.manifest.schema} incompatível "
                f"com SCHEMA_VERSION={SCHEMA_VERSION}"
            )

        module_name, _, class_name = spec.manifest.entry.partition(":")
        module_path = spec.source_dir / f"{module_name}.py"
        try:
            mod_spec = importlib.util.spec_from_file_location(
                f"animaltrack_plugin_{spec.manifest.kind.value}_{spec.manifest.name}", module_path
            )
            if mod_spec is None or mod_spec.loader is None:
                raise ImportError(f"não foi possível criar spec de import para {module_path}")
            module = importlib.util.module_from_spec(mod_spec)
            mod_spec.loader.exec_module(module)
            plugin_cls = getattr(module, class_name)
        except Exception as exc:
            raise PluginLoadError(
                f"{spec.manifest.name}: falha ao importar {module_path}: {exc}"
            ) from exc

        required_base = _KIND_BASE_CLASS.get(spec.manifest.kind, Plugin)
        if not (isinstance(plugin_cls, type) and issubclass(plugin_cls, required_base)):
            raise PluginContractError(
                f"{spec.manifest.name}: {class_name} não é subclasse de {required_base.__name__}"
            )

        plugin_cls.manifest = spec.manifest  # injeção pós-import, ver Plugin docstring
        try:
            return plugin_cls()  # type: ignore[no-any-return]
        except Exception as exc:
            raise PluginLoadError(f"{spec.manifest.name}: falha ao instanciar: {exc}") from exc

    # ---- get / for_kind ----------------------------------------------------
    def get(self, kind: PluginKind, name: str) -> Plugin:
        key = (kind, name)
        if key in self._instances:
            return self._instances[key]
        if key not in self._specs:
            raise PluginNotFoundError(f"plugin não encontrado: kind={kind} name={name}")
        instance = self.instantiate(self._specs[key])
        self._instances[key] = instance
        return instance

    def for_kind(self, kind: PluginKind) -> list[Plugin]:
        """Instancia (com isolamento de erro) todos os specs do kind, depois
        ordena topologicamente por before/after/priority."""
        candidates: list[Plugin] = []
        for (k, name), _spec in self._specs.items():
            if k != kind:
                continue
            try:
                candidates.append(self.get(kind, name))
            except Exception as exc:
                # inclui type(exc).__name__ para que discovery_warnings mencione a
                # classe de erro (ex. PluginApiVersionError) — checado pelos testes.
                msg = (
                    f"plugin {kind.value}:{name} não pôde ser instanciado "
                    f"({type(exc).__name__}), pulado: {exc}"
                )
                logger.warning(msg)
                self.discovery_warnings.append(msg)
                continue
        return _topological_order(candidates)


def _topological_order(nodes: list[Plugin]) -> list[Plugin]:
    """Ordenação topológica (Kahn) com desempate por (-priority, nome).

    Passos:
      1. Nós = nomes dos plugins já instanciados com sucesso (falhas já isoladas
         em `for_kind`).
      2. Arestas A->B = "A roda antes de B": cada nome em `P.after` gera
         `outro -> P`; cada nome em `P.before` gera `P -> outro`. Referência a um
         nome não descoberto neste kind é ignorada com warning (não é fatal).
      3. `in_degree` calculado das arestas mantidas.
      4. Fila de prontos = `in_degree == 0`, ordenada por `(-priority, nome)`:
         maior priority primeiro, empate por ordem alfabética (determinístico).
      5. Laço de Kahn: remove o primeiro pronto, adiciona ao resultado, decrementa
         `in_degree` dos sucessores; refaz o sort da fila a cada iteração.
      6. Se `len(resultado) != len(nós)`: ciclo — levanta `PluginOrderingCycleError`
         nomeando os nós presos (NÃO isolado por plugin — propaga).
    """
    by_name = {n.manifest.name: n for n in nodes}
    names = set(by_name)

    edges: dict[str, set[str]] = {n: set() for n in names}
    in_degree: dict[str, int] = {n: 0 for n in names}

    def add_edge(a: str, b: str) -> None:
        if b not in edges[a]:
            edges[a].add(b)
            in_degree[b] += 1

    for name, node in by_name.items():
        ordering = node.manifest.ordering
        for other in ordering.after:
            if other not in names:
                logger.warning(
                    f"{name}: ordering.after referencia '{other}', não descoberto no "
                    f"kind atual — ignorado"
                )
                continue
            add_edge(other, name)  # other roda antes de name
        for other in ordering.before:
            if other not in names:
                logger.warning(
                    f"{name}: ordering.before referencia '{other}', não descoberto no "
                    f"kind atual — ignorado"
                )
                continue
            add_edge(name, other)  # name roda antes de other

    def sort_key(n: str) -> tuple[int, str]:
        return (-by_name[n].manifest.ordering.priority, n)

    ready = sorted((n for n in names if in_degree[n] == 0), key=sort_key)
    result: list[Plugin] = []
    while ready:
        current = ready.pop(0)
        result.append(by_name[current])
        for successor in sorted(edges[current]):
            in_degree[successor] -= 1
            if in_degree[successor] == 0:
                ready.append(successor)
        ready.sort(key=sort_key)

    if len(result) != len(names):
        stuck = names - {n.manifest.name for n in result}
        raise PluginOrderingCycleError(f"ciclo de ordenação detectado entre: {sorted(stuck)}")

    return result
