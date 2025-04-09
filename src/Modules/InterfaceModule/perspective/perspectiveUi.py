from tkinter import ttk

from src.Modules.InterfaceModule.perspective.pespectiveController import get_firt_frame

class PerspectiveUi:
    def __init__(self, root, main_frame):
        self.root = root
        self.main_frame = main_frame
        
        self.buttons = {}
        self.labels = {}
        self.entry = {}
        self.cache = {}

    def initial_screen_state(self):
        image = get_firt_frame(self.cache["videoPath"])
        
        self.labels["side_image"] = ttk.Label(self.root)
        self.labels["side_image"].grid(row=3, column=1)
        
        self.labels["side_image"].config(image=image)