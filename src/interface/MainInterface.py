import threading
import tkinter as tk

from interface.PerspectiveUi import PerspectiveUi
from interface.MainConfigurationInterface import MainConfigurationInterface
from utils.interfaceUtils import show_frame

#from Ui.PerspectiveUi import PerspectiveUi

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
            root=self.perspective_side_frame, 
            mainFrame = self.perspective_main_frame
        )
        
        self.perspective_top_frame = tk.Frame(root)
        self.perspective_top_interface = PerspectiveUi(
            root=self.perspective_top_frame,
            mainFrame = self.perspective_main_frame
        )
    
        self.perspective_main_interface = MainConfigurationInterface(
            root=self.perspective_main_frame,
            showSideFrame=self.showFrameSide,
            showTopFrame= self.showFrameTop,
            perspective_top_interface=self.perspective_top_interface,
            perspective_side_interface=self.perspective_side_interface
        )
        
        show_frame(self.perspective_main_frame)
    
    def showMainFrame(self):
        print(self.perspective_main_frame)
        show_frame(self.perspective_main_frame)
    
    def showFrameSide(self):
        show_frame(self.perspective_side_frame)
        self.run_background_tasks(self.perspective_side_interface, self.perspective_main_frame.side_video_path)
        
    def showFrameTop(self):
        show_frame(self.perspective_top_frame)
        self.run_background_tasks(self.perspective_top_interface, self.perspective_main_frame.top_video_path)
    
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

