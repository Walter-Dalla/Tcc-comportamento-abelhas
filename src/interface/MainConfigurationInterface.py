import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from src.imageAnalizer.Perspective.perspective import get_perspective_size
from src.modules.borderModule import border_module
from src.modules.routeAnalizer import route_module
from src.plot.plotRoute import plot_insect_route_on_graph
from src.imageAnalizer.Perspective.processVideoPerspective import process_video

from src.imageAnalizer.GetData import get_video_data
from src.modules.speedModule import speed_module
from src.utils.jsonUtils import export_data_to_file, import_data_from_file

class MainConfigurationInterface:
    def __init__(self, root, showSideFrame, showTopFrame, perspective_top_interface, perspective_side_interface):

        self.perspective_top_interface = perspective_top_interface
        self.perspective_side_interface = perspective_side_interface

        self.configsPath = "cache/configs.json"

        self.root = root
        #self.root.title("Configuração de Vídeo")
        
        self.configs = self.load_configs()
        self.selected_config = tk.StringVar(value="Novo")
        
        # Seleção de configurações
        self.label_config = tk.Label(root, text="Selecione configurações")
        self.label_config.pack(pady=5)
        
        self.config_combobox = ttk.Combobox(root, textvariable=self.selected_config, values=["Novo"] + list(self.configs.keys()))
        self.config_combobox.pack(pady=5)
        self.config_combobox.bind("<<ComboboxSelected>>", self.load_selected_config)
        
        # Seleção de arquivos de vídeo
        self.root.top_video_path = tk.StringVar()
        self.root.side_video_path = tk.StringVar()
        
        self.btn_select_top_video = tk.Button(root, text="Selecione o local do arquivo de video topo", command=self.select_top_video)
        self.btn_select_top_video.pack(pady=5)
        
        self.btn_config_top_edges = tk.Button(root, text="Configurar bordas (topo)", command=showTopFrame)
        self.btn_config_top_edges.pack(pady=5)
        
        self.btn_select_side_video = tk.Button(root, text="Selecione o local do arquivo de video lado", command=self.select_side_video)
        self.btn_select_side_video.pack(pady=5)
        
        self.btn_config_side_edges = tk.Button(root, text="Configurar bordas (lado)", command=showSideFrame)
        self.btn_config_side_edges.pack(pady=5)
        
        self.label_height = tk.Label(root, text="Altura (cm)")
        self.label_height.pack(pady=5)
        
        self.height_box_cm = tk.Entry(root)
        self.height_box_cm.pack(pady=5)
        
        self.label_width = tk.Label(root, text="Largura (cm)")
        self.label_width.pack(pady=5)
        
        self.width_box_cm = tk.Entry(root)
        self.width_box_cm.pack(pady=5)
        
        self.label_depth = tk.Label(root, text="Profundidade (cm)")
        self.label_depth.pack(pady=5)
        
        self.depth_box_cm = tk.Entry(root)
        self.depth_box_cm.pack(pady=5)
        
        # Salvar configurações
        self.btn_save_config = tk.Button(root, text="Salvar configurações", command=self.save_config)
        self.btn_save_config.pack(pady=20)
        
        self.btn_config_side_edges = tk.Button(root, text="Processar", command=self.Process)
        self.btn_config_side_edges.pack(pady=5)
    
    def load_configs(self):
        return import_data_from_file(self.configsPath)
    
    def load_selected_config(self, event):
        config_name = self.selected_config.get()
        
        if config_name != "Novo":
            config = self.configs[config_name]
            self.root.top_video_path.set(config.get("top_video_path", ""))
            self.root.side_video_path.set(config.get("side_video_path", ""))
            self.perspective_top_interface.frame_perspective_points = (config.get("frame_perspective_points_top", ""))
            self.perspective_side_interface.frame_perspective_points = (config.get("frame_perspective_points_side", ""))
            
            self.width_box_cm.insert(0, config.get("width_box_cm", ""))
            self.height_box_cm.insert(0, config.get("height_box_cm", ""))
            self.depth_box_cm.insert(0, config.get("depth_box_cm", ""))
            
    
    def select_top_video(self):
        filepath = filedialog.askopenfilename(title="Selecione o arquivo de vídeo topo", filetypes=[("Video Files", "*.mp4;*.avi;*.mov")])
        if filepath:
            self.root.top_video_path.set(filepath)
    
    def select_side_video(self):
        filepath = filedialog.askopenfilename(title="Selecione o arquivo de vídeo lado", filetypes=[("Video Files", "*.mp4;*.avi;*.mov")])
        if filepath:
            self.root.side_video_path.set(filepath)
    
    def save_config(self):
        config_name = self.selected_config.get()
        if not isinstance(self.root.top_video_path.get(), str) or not isinstance(self.root.side_video_path.get(), str) or not isinstance(self.perspective_top_interface.frame_perspective_points, list) or not isinstance(self.perspective_side_interface.frame_perspective_points, list):
            messagebox.showinfo("Configurações salvas", f"Configuração '{config_name}' salva com sucesso.")
               
        
        if config_name == "Novo":
            config_name = tk.simpledialog.askstring("Salvar configuração", "Digite o nome para a nova configuração:")
            if not config_name:
                return
            
        self.configs[config_name] = {
            "top_video_path": self.root.top_video_path.get(),
            "side_video_path": self.root.side_video_path.get(),
            "frame_perspective_points_top": self.perspective_top_interface.frame_perspective_points,
            "frame_perspective_points_side": self.perspective_side_interface.frame_perspective_points,
            "width_box_cm": self.width_box_cm.get(),
            "height_box_cm": self.height_box_cm.get(),
            "depth_box_cm": self.depth_box_cm.get()
        }
        export_data_to_file(self.configs, self.configsPath)
        
        self.config_combobox.config(values=["Novo"] + list(self.configs.keys()))
        messagebox.showinfo("Configurações salvas", f"Configuração '{config_name}' salva com sucesso.")

    def Process(self):
        _, top_video, fps = process_video(
            frame_points=self.perspective_top_interface.frame_perspective_points,
            input_video_path=self.root.top_video_path.get(),
            temp_name="top",
        )
        
        _, side_video, _ = process_video(
            frame_points=self.perspective_side_interface.frame_perspective_points,
            input_video_path=self.root.side_video_path.get(), 
            temp_name="side",
        )
        
        fps, pixel_to_cm_ratio = get_video_data(
            width_box_cm = float(self.width_box_cm.get()),
            height_box_cm = float(self.height_box_cm.get()),
            depth_box_cm = float(self.depth_box_cm.get()),
            top_video= top_video,
            side_video = side_video
        )
        
        output_location = "C:/Projetos/Tcc-comportamento-abelhas/output/output_data.json"
        
        data = route_module(top_video, side_video)
        data["width_box_cm"] = float(self.width_box_cm.get())
        data["height_box_cm"] = float(self.height_box_cm.get())
        data["depth_box_cm"] = float(self.depth_box_cm.get())
        data["pixel_to_cm_ratio"] = pixel_to_cm_ratio
        data["fps"] = fps
        
        border_module(data)
        speed_module(data)
        export_data_to_file(data, output_location)
        
        width, depth =  get_perspective_size(frame_points=self.perspective_top_interface.frame_perspective_points)
        _, height =  get_perspective_size(frame_points=self.perspective_side_interface.frame_perspective_points)

        xlim = (0, width)
        ylim = (0, height)
        zlim = (0, depth)


        plot_insect_route_on_graph(output_location, xlim, ylim, zlim)
        


