import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

from imageAnalizer.Perspective.perspective import getPerspectiveSize
from imageAnalizer.Route.routeAnalizer import route
from plot.plotRoute import plotInsectRouteOnGraph
from imageAnalizer.Perspective.processVideoPerspective import process_video

from imageAnalizer.GetData import getVideoData
from speedAnalizer.speedAnalizer import calculateSpeed
from utils.jsonUtils import exportDataToFile, importDataFromFile

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
        return importDataFromFile(self.configsPath)
    
    def load_selected_config(self, event):
        config_name = self.selected_config.get()
        
        if config_name != "Novo":
            config = self.configs[config_name]
            self.root.top_video_path.set(config.get("top_video_path", ""))
            self.root.side_video_path.set(config.get("side_video_path", ""))
            self.perspective_top_interface.framePerspectivePoints = (config.get("framePerspectivePointsTop", ""))
            self.perspective_side_interface.framePerspectivePoints = (config.get("framePerspectivePointsSide", ""))
            
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
        if not isinstance(self.root.top_video_path.get(), str) or not isinstance(self.root.side_video_path.get(), str) or not isinstance(self.perspective_top_interface.framePerspectivePoints, list) or not isinstance(self.perspective_side_interface.framePerspectivePoints, list):
            messagebox.showinfo("Configurações salvas", f"Configuração '{config_name}' salva com sucesso.")
               
        
        if config_name == "Novo":
            config_name = tk.simpledialog.askstring("Salvar configuração", "Digite o nome para a nova configuração:")
            if not config_name:
                return
            
        self.configs[config_name] = {
            "top_video_path": self.root.top_video_path.get(),
            "side_video_path": self.root.side_video_path.get(),
            "framePerspectivePointsTop": self.perspective_top_interface.framePerspectivePoints,
            "framePerspectivePointsSide": self.perspective_side_interface.framePerspectivePoints,
            "width_box_cm": self.width_box_cm.get(),
            "height_box_cm": self.height_box_cm.get(),
            "depth_box_cm": self.depth_box_cm.get()
        }
        with open(self.configsPath, "w") as f:
            json.dump(self.configs, f, indent=4)
        self.config_combobox.config(values=["Novo"] + list(self.configs.keys()))
        messagebox.showinfo("Configurações salvas", f"Configuração '{config_name}' salva com sucesso.")

    def Process(self):
        _, top_video, fps = process_video(
            framePoints=self.perspective_top_interface.framePerspectivePoints,
            inputVideoPath=self.root.top_video_path.get(),
            tempName="top",
        )
        
        _, side_video, _ = process_video(
            framePoints=self.perspective_side_interface.framePerspectivePoints,
            inputVideoPath=self.root.side_video_path.get(), 
            tempName="side",
        )
        
        fps, pixel_to_cm_ratio = getVideoData(
            width_box_cm = float(self.width_box_cm.get()),
            height_box_cm = float(self.height_box_cm.get()),
            depth_box_cm = float(self.depth_box_cm.get()),
            top_video= top_video,
            side_video = side_video
        )
        
        outputLocation = "C:/Projetos/Tcc-comportamento-abelhas/output/output_data.json"
        
        data = route(top_video, side_video, outputLocation)
        
        calculateSpeed(data, pixel_to_cm_ratio, fps)
        exportDataToFile(data, outputLocation)
        
        width, depth =  getPerspectiveSize(framePoints=self.perspective_top_interface.framePerspectivePoints)
        _, height =  getPerspectiveSize(framePoints=self.perspective_side_interface.framePerspectivePoints)

        xlim = (0, width)
        ylim = (0, height)
        zlim = (0, depth)


        plotInsectRouteOnGraph(outputLocation, xlim, ylim, zlim)
        


