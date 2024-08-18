import threading
import tkinter as tk

from src.interface.BorderInterface import BorderInterface
from src.interface.PerspectiveUi import PerspectiveUi
from src.interface.MainConfigurationInterface import MainConfigurationInterface
from src.utils.interfaceUtils import show_frame

class MainInterface:
    def __init__(self, root):
        self.root = root
        root.title("Main Window")
        root.geometry("1400x1300")
        root.side_video_path = ""
        root.top_video_path = ""
        
        self.perspective_main_frame = tk.Frame(root)
        
        self.perspective_side_frame = tk.Frame(root)
        self.perspective_side_interface = PerspectiveUi(
            main_frame = self.perspective_main_frame,
            root=self.perspective_side_frame, 
        )
        
        self.perspective_top_frame = tk.Frame(root)
        self.perspective_top_interface = PerspectiveUi(
            main_frame = self.perspective_main_frame,
            root=self.perspective_top_frame,
        )
        
        self.border_interface_frame = tk.Frame(root)
        self.border_interface = BorderInterface(
            main_frame = self.perspective_main_frame,
            root=self.border_interface_frame,
        )
    
        self.perspective_main_interface = MainConfigurationInterface(
            root=self.perspective_main_frame,
            
            show_border_frame= self.show_border_frame,
            show_side_frame=self.show_frame_side,
            show_top_frame= self.show_frame_top,
            
            perspective_side_interface=self.perspective_side_interface,
            perspective_top_interface=self.perspective_top_interface,
            border_interface=self.border_interface,
        )
        
        show_frame(self.perspective_main_frame)
    
    def show_main_frame(self):
        print(self.perspective_main_frame)
        show_frame(self.perspective_main_frame)
    
    def show_frame_side(self):
        show_frame(self.perspective_side_frame)
        self.run_background_tasks(self.perspective_side_interface, [self.perspective_main_frame.side_video_path.get()])
        
    def show_border_frame(self):
        show_frame(self.border_interface_frame)
        self.run_background_tasks(self.border_interface, [self.perspective_main_frame.top_video_path.get(), self.perspective_main_frame.side_video_path.get()])
        
    def show_frame_top(self):
        show_frame(self.perspective_top_frame)
        self.run_background_tasks(self.perspective_top_interface, [self.perspective_main_frame.top_video_path.get()])
    
    def run_background_tasks(self, screen, args):
        background_thread = threading.Thread(target=screen.start_up, args=args)
        background_thread.daemon = True
        background_thread.start()
    
    

def show_main_ui():
    root = tk.Tk()
    screen = MainInterface(root)

    return screen

def run_loop(screen):
    screen.root.mainloop()

