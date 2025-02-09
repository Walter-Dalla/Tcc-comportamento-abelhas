import threading
import tkinter as tk

from src.Modules.InterfaceModule.recodWebCamVideo.recordWebcamVideoUI import RecordWebcamVideoUI
from src.Modules.InterfaceModule.borderUi import BorderUi
from src.Modules.InterfaceModule.configurationUI import MainConfigurationInterface
from src.Modules.InterfaceModule.perspectiveUi import PerspectiveUi
from src.utils.interfaceUtils import show_frame

class MainInterface:
    def __init__(self, root):
        self.root = root
        root.title("Ferramenta para a analise comportamental de insetos")
        root.side_video_path = ""
        root.top_video_path = ""
        
        window_width = 800  # Largura desejada da janela
        window_height = 800  # Altura desejada da janela

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x_coordinate = int((screen_width / 2) - (window_width / 2))
        y_coordinate = int((screen_height / 2) - (window_height / 2))

        root.geometry(f"{window_width}x{window_height}+{x_coordinate}+{y_coordinate}")
        root.pack_propagate(False)
        
        self.perspective_main_frame = tk.Frame(root)
        
        self.perspective_side_frame = tk.Frame(root)
        self.perspective_side_interface = PerspectiveUi(
            root=self.perspective_side_frame, 
            main_frame = self.perspective_main_frame
        )
        
        self.perspective_top_frame = tk.Frame(root)
        self.perspective_top_interface = PerspectiveUi(
            root=self.perspective_top_frame,
            main_frame = self.perspective_main_frame
        )
    
        self.border_config_top_frame = tk.Frame(root)
        self.border_config_top_interface = BorderUi(
            root=self.border_config_top_frame,
            main_frame = self.perspective_main_frame
        )
        
        self.border_config_side_frame = tk.Frame(root)
        self.border_config_side_interface = BorderUi(
            root=self.border_config_side_frame,
            main_frame = self.perspective_main_frame
        )
        
        self.sla = tk.Frame(root)
        self.record_webcam_frame = tk.Frame(root)
        self.record_webcam_interface = RecordWebcamVideoUI(
            root=self.record_webcam_frame,
            main_frame = self.perspective_main_frame
        )
    
        self.perspective_main_interface = MainConfigurationInterface(
            root= self.perspective_main_frame,
            showSideFrame= self.showFrameSide,
            showTopFrame= self.showFrameTop,
            showConfigBorderSide= self.showConfigBorderSide,
            showConfigBorderTop= self.showConfigBorderTop,
            perspective_top_interface= self.perspective_top_interface,
            perspective_side_interface= self.perspective_side_interface,
            border_config_top_interface= self.border_config_top_interface,
            border_config_side_interface= self.border_config_side_interface,
            showRecordWebcamFrame = self.showRecordWebcamFrame
        )
        
        show_frame(self.perspective_main_frame)
    
    def showMainFrame(self):
        show_frame(self.perspective_main_frame)
    
    def showFrameSide(self):
        show_frame(self.perspective_side_frame)
        self.run_background_tasks(self.perspective_side_interface, self.perspective_main_frame.side_video_path.get())
        
    def showFrameTop(self):
        show_frame(self.perspective_top_frame)
        self.run_background_tasks(self.perspective_top_interface, self.perspective_main_frame.top_video_path.get())
        
    def showConfigBorderTop(self):
        show_frame(self.border_config_top_frame)
        self.run_background_tasks(self.border_config_top_interface, self.perspective_main_frame.top_video_path.get())
        
    def showConfigBorderSide(self):
        show_frame(self.border_config_side_frame)
        self.run_background_tasks(self.border_config_side_interface, self.perspective_main_frame.side_video_path.get())
        
    def showRecordWebcamFrame(self):
        self.record_webcam_interface.initial_screen_state()
        show_frame(self.record_webcam_frame)
    
    def run_background_tasks(self, screen, videoPath):
        background_thread = threading.Thread(target=screen.startUp, args=[videoPath])
        background_thread.daemon = True
        background_thread.start()
    
    

def show_main_ui():
    root = tk.Tk()
    screen = MainInterface(root)

    return screen

def run_loop(screen):
    screen.root.mainloop()

