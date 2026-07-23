import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.Modules.ExportModule.folderUtils import assert_dir_exists
from src.Modules.ExportModule import pdfFactory
from src.Modules.MetadataModule.modulesInvoker import execute_metadata_module_calls
from src.Modules.ExportModule.plotRoute import plot_insect_route_on_graph_animated, plot_insect_route_on_graph_without_animation
from src.Modules.ExportModule.jsonUtils import export_data_to_file, import_data_from_file


def _get_perspective_size(frame_points):
    # Inlined do antigo perspectiveModule.get_perspective_size (apagado na Fase 3).
    # Ainda usado só pelos limites do gráfico 3D; o warp real vive em
    # src/stages/rectify. Removido de vez quando a GUI migrar (Fase 4).
    width = frame_points[1][0] - frame_points[0][0]
    height = frame_points[2][1] - frame_points[0][1]
    return width, height


class MainConfigurationInterface:
    new_analises_profile = "Novo perfil de analise"
    
    def __init__(self, root, showSideFrame, showTopFrame, perspective_top_interface, perspective_side_interface, border_config_top_interface, border_config_side_interface, showConfigBorderSide, showConfigBorderTop, showRecordWebcamFrame):
        self.perspective_top_interface = perspective_top_interface
        self.perspective_side_interface = perspective_side_interface
        self.border_config_top_interface = border_config_top_interface
        self.border_config_side_interface = border_config_side_interface
        
        
        self.configsPath = "cache/configs.json"

        self.root = root
        
        self.configs = self.load_configs()
        
        btn_capture_videos = tk.Button(root, text="Capturar videos", command=showRecordWebcamFrame)
        btn_capture_videos.pack(pady=5, anchor="center")

        # Seleção de configurações
        self.label_config = tk.Label(root, text="Selecione o perfil de analise")
        self.label_config.pack(pady=5, anchor="center")

        self.selected_config = tk.StringVar(value=self.new_analises_profile)
        self.config_combobox = ttk.Combobox(root, textvariable=self.selected_config, values=[self.new_analises_profile] + list(self.configs.keys()))
        self.config_combobox.pack(pady=5, anchor="center")
        self.config_combobox.bind("<<ComboboxSelected>>", self.load_selected_config)

        # Seleção de arquivos de vídeo
        self.root.top_video_path = tk.StringVar()
        self.root.side_video_path = tk.StringVar()

        btn_select_top_video = tk.Button(root, text="Selecione o local do arquivo de video topo", command=self.select_top_video)
        btn_select_top_video.pack(pady=5, anchor="center")

        btn_perspective_top = tk.Button(root, text="Configurar perspectiva (topo)", command=showTopFrame)
        btn_perspective_top.pack(pady=5, anchor="center")

        btn_border_top = tk.Button(root, text="Configurar bordas (topo)", command=showConfigBorderTop)
        btn_border_top.pack(pady=5, anchor="center")

        btn_select_side_video = tk.Button(root, text="Selecione o local do arquivo de video lado", command=self.select_side_video)
        btn_select_side_video.pack(pady=5, anchor="center")

        btn_perspective_side = tk.Button(root, text="Configurar perspectiva (lado)", command=showSideFrame)
        btn_perspective_side.pack(pady=5, anchor="center")

        btn_border_side = tk.Button(root, text="Configurar bordas (lado)", command=showConfigBorderSide)
        btn_border_side.pack(pady=5, anchor="center")

        self.label_height = tk.Label(root, text="Altura (cm)")
        self.label_height.pack(pady=5, anchor="center")
        
        self.height_box_cm = tk.Entry(root)
        self.height_box_cm.pack(pady=5, anchor="center")
        
        self.label_width = tk.Label(root, text="Largura (cm)")
        self.label_width.pack(pady=5, anchor="center")
        
        self.width_box_cm = tk.Entry(root)
        self.width_box_cm.pack(pady=5, anchor="center")
        
        self.label_depth = tk.Label(root, text="Profundidade (cm)")
        self.label_depth.pack(pady=5, anchor="center")
        
        self.depth_box_cm = tk.Entry(root)
        self.depth_box_cm.pack(pady=5, anchor="center")
        
        # Salvar configurações
        btn_save_config = tk.Button(root, text="Salvar configurações", command=self.save_config)
        btn_save_config.pack(pady=20)

        btn_process_video = tk.Button(root, text="Processar video (Módulos Basicos)", command=self.process_video)
        btn_process_video.pack(pady=5, anchor="center")

        btn_process_metadata = tk.Button(root, text="Executar módulos de metadados", command=self.process_metadata_modules)
        btn_process_metadata.pack(pady=5, anchor="center")

        btn_show_route_graph = tk.Button(root, text="Exibir grafico de rota", command=self.process_output_data)
        btn_show_route_graph.pack(pady=5, anchor="center")

        btn_export_pdf = tk.Button(root, text="Exportar para PDF", command=self.process_pdf)
        btn_export_pdf.pack(pady=5, anchor="center")
        
    def load_configs(self):
        return import_data_from_file(self.configsPath)
    
    def load_selected_config(self, event):
        config_name = self.selected_config.get()
        
        if config_name == self.new_analises_profile:
            config = {}
        else:
            config = self.configs[config_name]
            
        self.root.top_video_path.set(config.get("top_video_path", ""))
        self.root.side_video_path.set(config.get("side_video_path", ""))
        self.perspective_top_interface.frame_perspective_points = (config.get("frame_perspective_points_top", ""))
        self.perspective_side_interface.frame_perspective_points = (config.get("frame_perspective_points_side", ""))
        
        self.width_box_cm.delete(0, tk.END)
        self.height_box_cm.delete(0, tk.END)
        self.depth_box_cm.delete(0, tk.END)
        
        self.width_box_cm.insert(0, config.get("width_box_cm", ""))
        self.height_box_cm.insert(0, config.get("height_box_cm", ""))
        self.depth_box_cm.insert(0, config.get("depth_box_cm", ""))
        
        self.border_config_top_interface.frame_border_points = config.get("frame_border_points_top", None)
        self.border_config_side_interface.frame_border_points = config.get("frame_border_points_side", None)
    
    def select_top_video(self):
        filepath = filedialog.askopenfilename(title="Selecione o arquivo de vídeo topo", filetypes=[("Video Files", "*.mp4;*.avi;*.mov")])
        if filepath:
            self.root.top_video_path.set(filepath)
    
    def select_side_video(self):
        filepath = filedialog.askopenfilename(title="Selecione o arquivo de vídeo lado", filetypes=[("Video Files", "*.mp4;*.avi;*.mov")])
        if filepath:
            self.root.side_video_path.set(filepath)
    
    def save_config(self):
        if(self.is_video_valid()):
            return
        
        config_name = self.selected_config.get()

        if config_name == self.new_analises_profile:
            config_name = tk.simpledialog.askstring("Salvar o perfil de analise", "Digite o nome para o novo perfil de analise:")
            if not config_name:
                return
        
        self.configs[config_name] = {
            "top_video_path": self.root.top_video_path.get(),
            "side_video_path": self.root.side_video_path.get(),
            "frame_perspective_points_top": self.perspective_top_interface.frame_perspective_points,
            "frame_perspective_points_side": self.perspective_side_interface.frame_perspective_points,
            "width_box_cm": self.width_box_cm.get(),
            "height_box_cm": self.height_box_cm.get(),
            "depth_box_cm": self.depth_box_cm.get(),
            "frame_border_points_top": self.border_config_top_interface.frame_border_points,
            "frame_border_points_side": self.border_config_side_interface.frame_border_points
        }
        
        export_data_to_file(self.configs, self.configsPath)
        
        self.config_combobox.config(values=[self.new_analises_profile] + list(self.configs.keys()))
        messagebox.showinfo("Configurações salvas", f"Configuração '{config_name}' salva com sucesso.")
        self.update_config_name(config_name)

    def update_config_name(self, config_name):
        self.selected_config.set(config_name)
        self.load_selected_config(None)
        

    def is_video_valid(self):
        if(self.root.top_video_path.get() == "" or self.root.side_video_path.get() == ""):
            messagebox.showerror("Erro!", f"Video não configurado.")
            return True
        
        top_pespective_points_len = len(self.perspective_top_interface.frame_perspective_points)
        side_pespective_points_len = len(self.perspective_side_interface.frame_perspective_points)
        
        if(top_pespective_points_len != side_pespective_points_len or side_pespective_points_len != 4 ):
            messagebox.showerror("Erro!", f"Bordas não configuradas.")
            return True
        
        return False

    def process_video(self):
        # Fase 3: o pipeline de cálculo antigo (processVideoModule/perspectiveModule/
        # backgroundRemoveModule/routeAnalizer/getData) foi apagado e reescrito como
        # estágios streaming em `src/stages/*` (orquestrados por
        # `src.stages.orchestration.run_cpu_analysis`). A ligação da GUI a esse novo
        # pipeline depende da tela de Orientação de câmera/caixa (pré-requisito de
        # dado), que só chega na Fase 4 — até lá este botão fica desativado.
        messagebox.showinfo(
            "Migração em andamento",
            "O processamento foi migrado para o novo pipeline streaming (Fase 3).\n"
            "A ligação da interface a ele chega na Fase 4 (tela de orientação de câmera).",
        )
    
    def process_metadata_modules(self):
        data = execute_metadata_module_calls(self.selected_config.get())
        messagebox.showinfo("Sucesso!", f"Modulos de metadata executados!")
    
    def process_output_data(self):
        data_location = "./cache/outputs/"+self.selected_config.get()+".json"
        data = import_data_from_file(data_location)
        
        width, depth =  _get_perspective_size(self.perspective_top_interface.frame_perspective_points)
        _, height =  _get_perspective_size(self.perspective_side_interface.frame_perspective_points)
        xlim = (0, width)
        ylim = (0, depth)
        zlim = (0, height)

        plot_insect_route_on_graph_without_animation(data, xlim, ylim, zlim)
        
    def process_pdf(self):
        title = self.selected_config.get()
        output_location = "./cache/outputs/"+title
        
        assert_dir_exists("./cache/outputs/")
        
        data = import_data_from_file(output_location+ ".json")
        
        pdfFactory.GeneratePdf(data, output_location+".pdf", title)
        
        messagebox.showinfo("Sucesso!", f"Exportação concluida!")

