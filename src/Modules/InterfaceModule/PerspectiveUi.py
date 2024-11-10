import threading
import time
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps, ImageDraw
import cv2

from src.Modules.BasicModule.perspectiveModule import fix_perspective
from src.Modules.ExportModule.videoUtils import open_video
from src.utils.interfaceUtils import show_frame

class PerspectiveUi:
    def __init__(self, root, main_frame):
        self.root = root
        self.next_frame = False
        self.state = "perspective"
        self.main_frame = main_frame
        self.frame_perspective_points = []
        self.finished = False
        
        self.show_ui()

    def startUp(self, videoPath):
        print("Iniciando analise moldura")
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
        image_label.bind("<Motion>", self.on_motion)
        self.image_label = image_label
        

    def load_small_image_on_ui(self, image):
        self.small_image = ImageTk.PhotoImage(image)
        
        small_image_label = ttk.Label(self.root, image=self.small_image)
        small_image_label.grid(row=1, column=1, rowspan=400, padx=10, pady=10)
        self.small_image_label = small_image_label

    def on_motion(self, event):
        x, y = event.x, event.y

        crop_size = 100

        left = max(0, x - crop_size // 2)
        upper = max(0, y - crop_size // 2)
        right = min(self.root_image.width(), x + crop_size // 2)
        lower = min(self.root_image.height(), y + crop_size // 2)
        
        image = ImageTk.getimage(self.root_image)
        
        cropped_image = image.crop((left, upper, right, lower))
        
        border_left = max(0, crop_size // 2 - x)
        border_upper = max(0, crop_size // 2 - y)
        border_right = max(0, x + crop_size // 2 - self.root_image.width())
        border_lower = max(0, y + crop_size // 2 - self.root_image.height())

        expanded_image = ImageOps.expand(cropped_image, border=(border_left, border_upper, border_right, border_lower), fill='black')

        draw = ImageDraw.Draw(expanded_image)
        center = (crop_size // 2, crop_size // 2)
        radius = crop_size // 4
        
        draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline='red', width=2)

        line_length = 10
        draw.line((center[0] - line_length, center[1], center[0] + line_length, center[1]), fill='red', width=2)
        draw.line((center[0], center[1] - line_length, center[0], center[1] + line_length), fill='red', width=2)

        cropped_img_tk = ImageTk.PhotoImage(expanded_image)
        
        self.small_image_label.config(image=cropped_img_tk)
        self.small_image_label.image = cropped_img_tk

    def show_ui(self):
        #self.root.title("Interface com Imagem e Botões")

        image = Image.new('RGB', (500, 500), (0, 0, 0))
        self.load_image_on_ui_from_array(image)

        small_image = Image.new('RGB', (100, 100), (0, 0, 0))
        self.load_small_image_on_ui(small_image)
        
        button = ttk.Button(self.root, text=f"Voltar", command=self.finish_perspective_without_config)
        button.grid(row=8, column=1, padx=10, pady=10)
        

    def show_finish_perspective_btn(self):
        self.finished = True
        
        button = ttk.Button(self.root, text=f"Finalizar perspectiva", command=self.finish_perspective)
        button.grid(row=6, column=1, padx=10, pady=10)
        
        button = ttk.Button(self.root, text=f"Resetar perspectiva", command=self.reset_perspective)
        button.grid(row=7, column=1, padx=10, pady=10)

    def get_next_frame(self):
        return self.next_frame
    
    def set_next_frame(self, value):
        self.next_frame = value

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
