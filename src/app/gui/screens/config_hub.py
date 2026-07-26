"""Hub de configuração (Fase 4, workstream C) — porta `MainConfigurationInterface`.

Diferenças-chave vs. legado:
- Estado de vídeo/pontos/dimensões vive em `service.session` (SessionState), não em
  StringVar pendurados no root Tk.
- Persistência via `service.save_profile`/`load_profile` (ProfileStore), não
  `jsonUtils.import_data_from_file`/`export_data_to_file`.
- "Processar vídeo" chama `service.run_pipeline(profile)` (mesmo caminho da CLI →
  `run_cpu_analysis`), marshalled para fora do main thread via `run_async`. Nenhuma
  chamada direta a estágios/plugins a partir da tela.
- Botões "Configurar orientação (topo)/(lado)" novos, com guarda de pré-condição.
- "Processar vídeo" tem as guardas do legado (`is_video_valid`) MAIS a guarda de
  orientação das duas câmeras (ux-design-detalhado.md seção 1.2).
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, simpledialog, ttk

from src.app.gui.screen import ScreenBase
from src.app.open_folder import OpenFolderError, open_folder
from src.app.orientation_util import validate_orientation
from src.app.service import AppService, ProgressEvent


class ConfigHubScreen(ScreenBase):
    def __init__(self, service: AppService, show: Callable[..., None]) -> None:
        self.service = service
        self.show = show
        self.frame: tk.Frame

    # --- construção ------------------------------------------------------------
    def build(self, parent: tk.Misc) -> tk.Frame:
        self.frame = tk.Frame(parent)
        frame = self.frame

        tk.Button(frame, text="Capturar videos", command=lambda: self.show("record_webcam")).pack(
            pady=5, anchor="center"
        )

        tk.Label(frame, text="Selecione o perfil de analise").pack(pady=5, anchor="center")
        self.selected_profile = tk.StringVar(value=self.service.new_profile_placeholder_name())
        self.profile_combobox = ttk.Combobox(frame, textvariable=self.selected_profile)
        self.profile_combobox.pack(pady=5, anchor="center")
        self.profile_combobox.bind("<<ComboboxSelected>>", self._on_profile_selected)

        tk.Button(
            frame, text="Selecione o local do arquivo de video topo", command=self._select_top_video
        ).pack(pady=5, anchor="center")
        tk.Button(
            frame, text="Configurar perspectiva (topo)",
            command=lambda: self._open_perspective("top"),
        ).pack(pady=5, anchor="center")
        tk.Button(
            frame, text="Configurar orientação (topo)",
            command=lambda: self._open_orientation("top"),
        ).pack(pady=5, anchor="center")
        tk.Button(
            frame, text="Configurar bordas (topo)", command=lambda: self._open_border("top")
        ).pack(pady=5, anchor="center")

        tk.Button(
            frame, text="Selecione o local do arquivo de video lado", command=self._select_side_video
        ).pack(pady=5, anchor="center")
        tk.Button(
            frame, text="Configurar perspectiva (lado)",
            command=lambda: self._open_perspective("side"),
        ).pack(pady=5, anchor="center")
        tk.Button(
            frame, text="Configurar orientação (lado)",
            command=lambda: self._open_orientation("side"),
        ).pack(pady=5, anchor="center")
        tk.Button(
            frame, text="Configurar bordas (lado)", command=lambda: self._open_border("side")
        ).pack(pady=5, anchor="center")

        tk.Label(frame, text="Largura (cm)").pack(pady=5, anchor="center")
        self.width_entry = tk.Entry(frame)
        self.width_entry.pack(pady=5, anchor="center")
        tk.Label(frame, text="Altura (cm)").pack(pady=5, anchor="center")
        self.height_entry = tk.Entry(frame)
        self.height_entry.pack(pady=5, anchor="center")
        tk.Label(frame, text="Profundidade (cm)").pack(pady=5, anchor="center")
        self.depth_entry = tk.Entry(frame)
        self.depth_entry.pack(pady=5, anchor="center")

        tk.Button(frame, text="Salvar configurações", command=self._save_config).pack(pady=20)
        # UX seção 6, Opção 2: sem preview ao vivo bloqueante; o Detect grava frames
        # amostrados em <workspace>/debug/<perfil>/ e o usuário inspeciona depois.
        self.debug_frames = tk.BooleanVar(value=False)
        tk.Checkbutton(
            frame, text="Exportar frames de debug", variable=self.debug_frames
        ).pack(pady=5, anchor="center")
        tk.Button(frame, text="Processar video (Módulos Basicos)", command=self._on_process_video).pack(
            pady=5, anchor="center"
        )
        tk.Button(frame, text="Abrir pasta de debug", command=self._on_open_debug_folder).pack(
            pady=5, anchor="center"
        )
        tk.Button(
            frame, text="Executar módulos de metadados", command=self._on_process_metadata
        ).pack(pady=5, anchor="center")
        tk.Button(frame, text="Exibir grafico de rota", command=self._on_show_route_graph).pack(
            pady=5, anchor="center"
        )
        tk.Button(frame, text="Exportar para PDF", command=self._on_export_pdf).pack(
            pady=5, anchor="center"
        )
        return frame

    # --- ciclo de vida ---------------------------------------------------------
    def on_show(self, **kwargs: object) -> None:
        self._refresh_profile_list()
        self._sync_ui_from_session()

    # --- helpers de estado -----------------------------------------------------
    def _refresh_profile_list(self) -> None:
        placeholder = self.service.new_profile_placeholder_name()
        self.profile_combobox.config(values=[placeholder, *self.service.list_profiles()])

    def _sync_ui_from_session(self) -> None:
        session = self.service.session
        for entry, value in (
            (self.width_entry, session.width_cm),
            (self.height_entry, session.height_cm),
            (self.depth_entry, session.depth_cm),
        ):
            entry.delete(0, tk.END)
            entry.insert(0, value)

    def _sync_session_from_ui(self) -> None:
        session = self.service.session
        session.width_cm = self.width_entry.get()
        session.height_cm = self.height_entry.get()
        session.depth_cm = self.depth_entry.get()

    def _on_profile_selected(self, _event: object) -> None:
        name = self.selected_profile.get()
        if name == self.service.new_profile_placeholder_name():
            self.service.session.reset()
            self.service.session.profile_name = ""
        else:
            self.service.session.load_from_profile(self.service.load_profile(name))
        self._sync_ui_from_session()

    def _select_top_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecione o arquivo de vídeo topo",
            filetypes=[("Video Files", "*.mp4;*.avi;*.mov")],
        )
        if path:
            self.service.session.top_video_path = path

    def _select_side_video(self) -> None:
        path = filedialog.askopenfilename(
            title="Selecione o arquivo de vídeo lado",
            filetypes=[("Video Files", "*.mp4;*.avi;*.mov")],
        )
        if path:
            self.service.session.side_video_path = path

    # --- navegação -------------------------------------------------------------
    def _video_for(self, role: str) -> str:
        session = self.service.session
        return session.top_video_path if role == "top" else session.side_video_path

    def _open_perspective(self, role: str) -> None:
        self.show(f"perspective_{role}", role=role, video_path=self._video_for(role))

    def _open_border(self, role: str) -> None:
        self.show(f"border_{role}", role=role, video_path=self._video_for(role))

    def _open_orientation(self, role: str) -> None:
        session = self.service.session
        points = (
            session.perspective_points_top if role == "top" else session.perspective_points_side
        )
        if not points or len(points) != 4:
            messagebox.showerror(
                "Erro!", "Configure a perspectiva desta câmera antes de configurar a orientação."
            )
            return
        self.show("orientation", role=role, video_path=self._video_for(role))

    # --- persistência ----------------------------------------------------------
    def _save_config(self) -> None:
        self._sync_session_from_ui()
        session = self.service.session
        if not session.top_video_path or not session.side_video_path:
            messagebox.showerror("Erro!", "Video não configurado.")
            return

        name = self.selected_profile.get()
        if name == self.service.new_profile_placeholder_name():
            entered = simpledialog.askstring(
                "Salvar o perfil de analise", "Digite o nome para o novo perfil de analise:"
            )
            if not entered:
                return
            name = entered
        session.profile_name = name
        self.service.save_profile(name, session.to_profile())
        self._refresh_profile_list()
        self.selected_profile.set(name)
        messagebox.showinfo("Configurações salvas", f"Configuração '{name}' salva com sucesso.")

    # --- guardas de pré-condição -----------------------------------------------
    def _processing_error(self) -> str | None:
        """Pré-condições de "Processar vídeo", na ordem em que o legado as checava.

        Espelha `MainConfigurationInterface.is_video_valid()` (vídeo + 4 pontos de
        perspectiva por câmera, mensagens telegráficas preservadas verbatim — o
        texto "Bordas não configuradas." para pontos de perspectiva é do legado e a
        seção 5 do UX manda não retrabalhar copy existente) e ACRESCENTA a guarda
        de orientação exigida pela seção 1.2: processar exige orientação válida das
        duas câmeras. A validação de orientação vem de `orientation_util`, a mesma
        fonte usada pela `OrientationScreen` e pelo `animaltrack validate-config`.
        """
        session = self.service.session
        if not session.top_video_path or not session.side_video_path:
            return "Video não configurado."
        if len(session.perspective_points_top) != 4 or len(session.perspective_points_side) != 4:
            return "Bordas não configuradas."
        errors = validate_orientation(session.build_orientation())
        if errors:
            return errors[0]
        return None

    # --- execução (mesmo caminho da CLI) ---------------------------------------
    def _on_process_video(self) -> object:
        self._sync_session_from_ui()
        profile = self.service.session.profile_name or self.selected_profile.get()
        if not profile or profile == self.service.new_profile_placeholder_name():
            messagebox.showerror("Erro!", "Salve o perfil antes de processar.")
            return None
        error = self._processing_error()
        if error is not None:
            messagebox.showerror("Erro!", error)
            return None
        debug_frames = bool(self.debug_frames.get())
        return self.run_async(
            work=lambda: self.service.run_pipeline(
                profile, on_progress=self._log_progress, debug_frames=debug_frames
            ),
            on_done=lambda _result: messagebox.showinfo(
                "Sucesso!", "Processamento concluído!"
            ),
            on_error=lambda exc: messagebox.showerror("Erro!", f"Falha no processamento: {exc}"),
        )

    def _log_progress(self, event: ProgressEvent) -> None:  # roda na thread de trabalho
        # Só logging (sem Tk) — seguro fora do main thread.
        import logging

        logging.getLogger("animaltrack.gui").info("progresso: %s %s", event.stage, event.message)

    def _on_process_metadata(self) -> object:
        """Reexecuta só os módulos de metadata sobre o resultado já persistido."""
        profile = self.service.session.profile_name or self.selected_profile.get()
        if not profile or profile == self.service.new_profile_placeholder_name():
            messagebox.showerror("Erro!", "Salve e processe o perfil antes de executar metadata.")
            return None
        return self.run_async(
            work=lambda: self.service.run_metadata(profile),
            on_done=lambda _result: messagebox.showinfo(
                "Sucesso!", "Modulos de metadata executados!"
            ),
            on_error=lambda exc: messagebox.showerror("Erro!", f"Falha na metadata: {exc}"),
        )

    def _on_open_debug_folder(self) -> None:
        """Abre `<workspace>/debug/<perfil>/` no explorador do SO (UX seção 6).

        `open_folder` só dispara o processo do SO (`startfile`/`Popen`) e volta na
        hora — a main thread do Tk não fica esperando o explorador.
        """
        profile = self.service.session.profile_name or self.selected_profile.get()
        if not profile or profile == self.service.new_profile_placeholder_name():
            messagebox.showerror("Erro!", "Selecione um perfil para abrir a pasta de debug.")
            return
        try:
            open_folder(self.service.debug_dir(profile))
        except (OpenFolderError, OSError) as exc:
            messagebox.showerror("Erro!", f"Não foi possível abrir a pasta de debug: {exc}")

    def _on_show_route_graph(self) -> object:
        return self._export_async("route-plot", "Gráfico de rota gerado")

    def _on_export_pdf(self) -> object:
        return self._export_async("pdf-report", "Exportação concluida")

    def _export_async(self, exporter_name: str, success_msg: str) -> object:
        profile = self.service.session.profile_name or self.selected_profile.get()
        if not profile or profile == self.service.new_profile_placeholder_name():
            messagebox.showerror("Erro!", "Salve e processe o perfil antes de exportar.")
            return None
        return self.run_async(
            work=lambda: self.service.export(profile, exporter_name),
            on_done=lambda path: messagebox.showinfo("Sucesso!", f"{success_msg}: {path}"),
            on_error=lambda exc: messagebox.showerror("Erro!", f"Falha na exportação: {exc}"),
        )
