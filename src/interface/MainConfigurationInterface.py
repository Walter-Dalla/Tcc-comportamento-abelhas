import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json

from imageAnalizer.Perspective.perspective import getPerspectiveSize
from imageAnalizer.Route.routeAnalizer import route
from plot.plotRoute import plotInsectRouteOnGraph
from imageAnalizer.Perspective.processVideoPerspective import process_video
from utils.jsonUtils import importDataFromFile

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
            self.root.top_video_path = config.get("top_video_path", "")
            self.root.side_video_path = config.get("side_video_path", "")
            self.perspective_top_interface.framePerspectivePoints = config.get("framePerspectivePointsTop", "")
            self.perspective_side_interface.framePerspectivePoints = config.get("framePerspectivePointsSide", "")
    
    def select_top_video(self):
        filepath = filedialog.askopenfilename(title="Selecione o arquivo de vídeo topo", filetypes=[("Video Files", "*.mp4;*.avi;*.mov")])
        if filepath:
            self.root.top_video_path = filepath
    
    def select_side_video(self):
        filepath = filedialog.askopenfilename(title="Selecione o arquivo de vídeo lado", filetypes=[("Video Files", "*.mp4;*.avi;*.mov")])
        if filepath:
            self.root.side_video_path = filepath
    
    def save_config(self):
        config_name = self.selected_config.get()
        if not isinstance(self.root.top_video_path, str) or not isinstance(self.root.side_video_path, str) or not isinstance(self.perspective_top_interface.framePerspectivePoints, list) or not isinstance(self.perspective_side_interface.framePerspectivePoints, list):
            messagebox.showinfo("Configurações salvas", f"Configuração '{config_name}' salva com sucesso.")
               
        
        if config_name == "Novo":
            config_name = tk.simpledialog.askstring("Salvar configuração", "Digite o nome para a nova configuração:")
            if not config_name:
                return
            
        self.configs[config_name] = {
            "top_video_path": self.root.top_video_path,
            "side_video_path": self.root.side_video_path,
            "framePerspectivePointsTop": self.perspective_top_interface.framePerspectivePoints,
            "framePerspectivePointsSide": self.perspective_side_interface.framePerspectivePoints
        }
        with open(self.configsPath, "w") as f:
            json.dump(self.configs, f, indent=4)
        self.config_combobox.config(values=["Novo"] + list(self.configs.keys()))
        messagebox.showinfo("Configurações salvas", f"Configuração '{config_name}' salva com sucesso.")

    def Process(self):
        
        _, top_video = process_video(inputVideoPath=self.root.top_video_path, tempName="top", framePoints=self.perspective_top_interface.framePerspectivePoints)
        _, side_video = process_video(inputVideoPath=self.root.side_video_path, tempName="side", framePoints=self.perspective_side_interface.framePerspectivePoints)
        
        outputLocation = "C:/Projetos/Tcc-comportamento-abelhas/output/output_data.json"
        
        #top_video = self.perspective_top_interface.videoProcessed
        #side_video = self.perspective_side_interface.videoProcessed
        
        route(top_video, side_video, outputLocation)

        width, depth =  getPerspectiveSize(framePoints=self.perspective_top_interface.framePerspectivePoints)
        sla, height =  getPerspectiveSize(framePoints=self.perspective_side_interface.framePerspectivePoints)

        print(self.root.top_video_path, self.perspective_top_interface.framePerspectivePoints)
        print(self.root.side_video_path, self.perspective_side_interface.framePerspectivePoints)
        print(width, depth, height, sla)
    
        xlim = (0, width)
        ylim = (0, height)
        zlim = (0, depth)


        plotInsectRouteOnGraph(outputLocation, xlim, ylim, zlim)
        


