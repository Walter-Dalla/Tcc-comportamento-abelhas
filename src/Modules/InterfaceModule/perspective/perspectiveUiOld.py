import threading
import time
from tkinter import ttk
from PIL import Image, ImageTk
import cv2

from src.Modules.BasicModule.perspectiveModule import perspective
from src.Modules.ExportModule.videoUtils import open_video
from src.utils.interfaceUtils import show_frame

class PerspectiveUi:
    def __init__(self, root, main_frame):
        self.root = root
        self.main_frame = main_frame
        self.frame_perspective_points = []
        self.finished = False
        
        self.show_ui()

    def startUp(self, videoPath):
        if(videoPath == ""):
            return
        
        self.videoPath = videoPath
        
        success, video = open_video(videoPath)
        if(not success):
            return
        
        self.video = video
        
        success, frame = video.read()
        if not success:
            return
        finished_perspective = False

        self.load_image_on_ui_from_cv2(frame)
        
        while not finished_perspective:
            finished_perspective, perspective_frame = fix_perspective(frame, self.frame_perspective_points)
            time.sleep(0.01)
            if perspective_frame is not 0:
                self.load_image_on_ui_from_cv2(perspective_frame)

                self.show_finish_perspective_btn()
        
        video.release()

    def load_image_on_ui_from_array(self, image):
        
        image_height, image_width = image.size
        
        image.thumbnail((image_height/2, image_width/2), Image.Resampling.LANCZOS)
        
        self.root_image = ImageTk.PhotoImage(image)
        self.image = image

        image_label = ttk.Label(self.root, image=self.root_image)
        image_label.grid(row=0, column=0, rowspan=400, padx=10, pady=10)

        image_label.bind("<Button-1>", lambda event: get_frame_points(event, self.frame_perspective_points))
        self.image_label = image_label

    def show_ui(self):
        image = Image.new('RGB', (500, 500), (0, 0, 0))
        self.load_image_on_ui_from_array(image)

        button = ttk.Button(self.root, text=f"Voltar", command=self.finish_perspective_without_config)
        button.grid(row=8, column=1, padx=10, pady=10)
        

    def show_finish_perspective_btn(self):
        self.finished = True
        
        button = ttk.Button(self.root, text=f"Finalizar perspectiva", command=self.finish_perspective)
        button.grid(row=6, column=1, padx=10, pady=10)
        
        button = ttk.Button(self.root, text=f"Resetar perspectiva", command=self.reset_perspective)
        button.grid(row=7, column=1, padx=10, pady=10)

    def run_loop(self):
        self.root.mainloop()

    def finish_perspective_without_config(self):
        if(not self.finished):
            video_width = int(self.video.get(cv2.CAP_PROP_FRAME_WIDTH))
            video_height = int(self.video.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            self.frame_perspective_points = [
                [0, 0],
                [video_width, 0],
                [0, video_height],
                [video_width, video_height]
            ]
        self.finish_perspective()

    def finish_perspective(self):
        show_frame(self.main_frame)
        
    def reset_perspective(self):
        self.frame_perspective_points = []
    
        background_thread = threading.Thread(target=self.startUp, args=[self.videoPath])
        background_thread.daemon = True
        background_thread.start()
        
    
    def load_image_on_ui_from_cv2(self, imageCv):
        image = Image.fromarray(imageCv)
        self.load_image_on_ui_from_array(image)

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

def fix_perspective(frame, frame_points):
    if len(frame_points) == 4:
        return True, perspective(frame, frame_points)

    return False, 0

def get_frame_points(event, frame_points):
    x, y = event.x, event.y
    
    x = x*2
    y = y*2
    
    if len(frame_points) >= 4:
        return
    
    frame_points.append((int(x), int(y)))
