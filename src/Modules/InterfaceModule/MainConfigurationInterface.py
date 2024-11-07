import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import concurrent.futures

import cv2

from src.Modules.BasicModule.imageAnalizer.Perspective.processVideoPerspective import process_video
from src.Modules.BasicModule.imageAnalizer.GetData import get_video_data
from src.Modules.BasicModule.imageAnalizer.Perspective.perspective import get_perspective_size
from src.Modules.BasicModule.routeAnalizer import route_module
from src.Modules.ExportModule import pdfFactory
from src.Modules.call_external_modules import execute_module_calls
from src.Modules.ExportModule.plotRoute import plot_insect_route_on_graph
from src.utils.jsonUtils import export_data_to_file, import_data_from_file

class MainConfigurationInterface:
    new_analises_profile = "Novo perfil de analise"
    
    def __init__(self, root, showSideFrame, showTopFrame, perspective_top_interface, perspective_side_interface):
        self.perspective_top_interface = perspective_top_interface
        self.perspective_side_interface = perspective_side_interface
        
        self.configsPath = "cache/configs.json"

        self.root = root
        #self.root.title("Configuração de Vídeo")
        
        self.configs = self.load_configs()
        
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
        
        self.btn_select_top_video = tk.Button(root, text="Selecione o local do arquivo de video topo", command=self.select_top_video)
        self.btn_select_top_video.pack(pady=5, anchor="center")
        
        self.btn_config_top_edges = tk.Button(root, text="Configurar bordas (topo)", command=showTopFrame)
        self.btn_config_top_edges.pack(pady=5, anchor="center")
        
        self.btn_select_side_video = tk.Button(root, text="Selecione o local do arquivo de video lado", command=self.select_side_video)
        self.btn_select_side_video.pack(pady=5, anchor="center")
        
        self.btn_config_side_edges = tk.Button(root, text="Configurar bordas (lado)", command=showSideFrame)
        self.btn_config_side_edges.pack(pady=5, anchor="center")
        
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
        self.btn_save_config = tk.Button(root, text="Salvar configurações", command=self.save_config)
        self.btn_save_config.pack(pady=20)
        
        self.btn_config_side_edges = tk.Button(root, text="Processar video e executar modulos", command=self.process_video)
        self.btn_config_side_edges.pack(pady=5, anchor="center")
        
        self.btn_config_side_edges = tk.Button(root, text="Exibir grafico de rota", command=self.process_output_data)
        self.btn_config_side_edges.pack(pady=5, anchor="center")
    
        self.btn_config_side_edges = tk.Button(root, text="Exportar para PDF", command=self.process_pdf)
        self.btn_config_side_edges.pack(pady=5, anchor="center")
        
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
        if not isinstance(self.root.top_video_path.get(), str) or not isinstance(self.root.side_video_path.get(), str) or not isinstance(self.perspective_top_interface.frame_perspective_points, list) or not isinstance(self.perspective_side_interface.frame_perspective_points, list):
            messagebox.showinfo("Configurações salvas", f"Configuração '{config_name}' salva com sucesso.")

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
            "depth_box_cm": self.depth_box_cm.get()
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
        if(self.is_video_valid()):
            return
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_top = executor.submit(process_video, self.perspective_top_interface.frame_perspective_points,self.root.top_video_path.get(), False)
            future_side = executor.submit(process_video, self.perspective_side_interface.frame_perspective_points, self.root.side_video_path.get(), True)

            side_success, side_frames, fps, side_data, side_raw_warpped_frames = future_side.result()
            top_success, top_frames, fps, top_data, top_raw_warpped_frames = future_top.result()
        
        if(not (top_success and side_success)):
            print("Erro ocorreu durante o proces video")
            return
        
        pixel_to_cm_ratio = get_video_data(
            width_box_cm = float(self.width_box_cm.get()),
            height_box_cm = float(self.height_box_cm.get()),
            depth_box_cm = float(self.depth_box_cm.get()),
            top_frames = top_frames,
            side_frames = side_frames
        )

        debug = False
        if debug:
            count = len(side_frames)
            for frame_index in range(count):
                cv2.imshow('top_frames', side_frames[frame_index])
                cv2.imshow('top_raw_warpped_frames', side_raw_warpped_frames[frame_index])
                
                cv2.waitKey(0)
        
        data = route_module(top_data, side_data)
        data["width_box_cm"] = float(self.width_box_cm.get())
        data["height_box_cm"] = float(self.height_box_cm.get())
        data["depth_box_cm"] = float(self.depth_box_cm.get())
        data["pixel_to_cm_ratio"] = pixel_to_cm_ratio
        data["fps"] = fps
        
        output_location = "./cache/outputs/"+self.selected_config.get()+".json"
        export_data_to_file(data, output_location)
    
    def process_output_data(self):
        output_location = "./cache/outputs/"+self.selected_config.get()+".json"
        
        data = import_data_from_file(output_location)
        execute_module_calls(data)
        export_data_to_file(data, output_location)
        
        width, depth =  get_perspective_size(frame_points=self.perspective_top_interface.frame_perspective_points)
        _, height =  get_perspective_size(frame_points=self.perspective_side_interface.frame_perspective_points)
        xlim = (0, width)
        ylim = (0, height)
        zlim = (0, depth)

        plot_insect_route_on_graph(output_location, xlim, ylim, zlim)
        
    def process_pdf(self):
        title = self.selected_config.get()
        output_location = "./cache/outputs/"+title
        data = import_data_from_file(output_location+ ".json")
        
        pdfFactory.GeneratePdf(data, output_location+".pdf", title)

