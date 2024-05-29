import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os

#from Ui.PerspectiveUi import PerspectiveUi

class ConfigApp:
    def __init__(self, root):

        self.configsPath = "cache/configs.json"

        self.root = root
        self.root.title("Configuração de Vídeo")
        
        self.configs = self.load_configs()
        self.selected_config = tk.StringVar(value="Novo")
        
        # Seleção de configurações
        self.label_config = tk.Label(root, text="Selecione configurações")
        self.label_config.pack(pady=5)
        
        self.config_combobox = ttk.Combobox(root, textvariable=self.selected_config, values=["Novo"] + list(self.configs.keys()))
        self.config_combobox.pack(pady=5)
        self.config_combobox.bind("<<ComboboxSelected>>", self.load_selected_config)
        
        # Seleção de arquivos de vídeo
        self.top_video_path = tk.StringVar()
        self.side_video_path = tk.StringVar()
        
        self.btn_select_top_video = tk.Button(root, text="Selecione o local do arquivo de video topo", command=self.select_top_video)
        self.btn_select_top_video.pack(pady=5)
        
        self.btn_config_top_edges = tk.Button(root, text="Configurar bordas (topo)", command=self.config_top_edges)
        self.btn_config_top_edges.pack(pady=5)
        
        self.btn_select_side_video = tk.Button(root, text="Selecione o local do arquivo de video lado", command=self.select_side_video)
        self.btn_select_side_video.pack(pady=5)
        
        self.btn_config_side_edges = tk.Button(root, text="Configurar bordas (lado)", command=self.config_side_edges)
        self.btn_config_side_edges.pack(pady=5)
        
        # Salvar configurações
        self.btn_save_config = tk.Button(root, text="Salvar configurações", command=self.save_config)
        self.btn_save_config.pack(pady=20)
    
    def load_configs(self):
        if os.path.exists(self.configsPath):
            with open(self.configsPath, "r") as f:
                return json.load(f)
        return {}
    
    def load_selected_config(self, event):
        config_name = self.selected_config.get()
        if config_name != "Novo":
            config = self.configs[config_name]
            self.top_video_path.set(config.get("top_video_path", ""))
            self.side_video_path.set(config.get("side_video_path", ""))
    
    def select_top_video(self):
        filepath = filedialog.askopenfilename(title="Selecione o arquivo de vídeo topo", filetypes=[("Video Files", "*.mp4;*.avi;*.mov")])
        if filepath:
            self.top_video_path.set(filepath)
    
    def config_top_edges(self):
        topVideoPath = "C:/Projetos/Tcc-comportamento-abelhas/resource/frame-with-incect.avi"
        sideVideoPath = "C:/Projetos/Tcc-comportamento-abelhas/resource/frame-with-incect.avi"
        
        #PerspectiveUi(root, topVideoPath, sideVideoPath)
        
        messagebox.showinfo("Configurar bordas", "Função para configurar bordas do vídeo topo.")
    
    def select_side_video(self):
        filepath = filedialog.askopenfilename(title="Selecione o arquivo de vídeo lado", filetypes=[("Video Files", "*.mp4;*.avi;*.mov")])
        if filepath:
            self.side_video_path.set(filepath)
    
    def config_side_edges(self):
        # Função para configurar bordas do vídeo lado
        messagebox.showinfo("Configurar bordas", "Função para configurar bordas do vídeo lado.")
    
    def save_config(self):
        config_name = self.selected_config.get()
        if config_name == "Novo":
            config_name = tk.simpledialog.askstring("Salvar configuração", "Digite o nome para a nova configuração:")
            if not config_name:
                return
            
        self.configs[config_name] = {
            "top_video_path": self.top_video_path.get(),
            "side_video_path": self.side_video_path.get()
        }
        with open(self.configsPath, "w") as f:
            json.dump(self.configs, f, indent=4)
        self.config_combobox.config(values=["Novo"] + list(self.configs.keys()))
        messagebox.showinfo("Configurações salvas", f"Configuração '{config_name}' salva com sucesso.")

if __name__ == "__main__":
    root = tk.Tk()
    app = ConfigApp(root)
    root.mainloop()
