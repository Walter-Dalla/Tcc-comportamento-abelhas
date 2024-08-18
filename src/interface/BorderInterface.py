import tkinter as tk
from PIL import Image, ImageTk

from src.utils.videoUtils import open_video
from src.utils.interfaceUtils import show_frame

class BorderInterface:
    def __init__(self, root, main_frame):
        self.root = root
        self.main_frame = main_frame
        
        self.root_image = [None, None]
        self.image = [None, None]
        self.image_label = [None, None]
        
        self.label_height = tk.Label(root, text="Borda Altura (cm)")
        self.label_height.grid(row=1, column=1)
        
        self.height_border_cm = tk.Entry(root)
        self.height_border_cm.grid(row=1, column=2)
        
        self.label_width = tk.Label(root, text="Borda Largura (cm)")
        self.label_width.grid(row=2, column=1)
        
        self.width_border_cm = tk.Entry(root)
        self.width_border_cm.grid(row=2, column=2)
        
        self.label_depth = tk.Label(root, text="Borda Profundidade (cm)")
        self.label_depth.grid(row=3, column=1)
        
        self.depth_border_cm = tk.Entry(root)
        self.depth_border_cm.grid(row=3, column=2)
        
        self.show_ui()
        
    # enviar o frame já corrigido a perspectiva ao invez do path
    def start_up(self, top_video_path, side_video_path):
        print("Iniciando analise moldura")
        self.top_video_path = top_video_path
        self.side_video_path = side_video_path
        
        _, video_top = open_video(top_video_path)
        _, video_side = open_video(side_video_path)
        
        success, frame_top = video_top.read()
        success, frame_side = video_side.read()
        
        self.load_image_on_ui_from_cv2(frame_top, 0)
        self.load_image_on_ui_from_cv2(frame_side, 1)
        
        video_top.release()
        video_side.release()

    def load_image_on_ui_from_cv2(self, imageCv, row):
        image = Image.fromarray(imageCv)
        self.load_image_on_ui_from_array(image, row)
        
    def load_image_on_ui_from_array(self, image, row):
        self.root_image[row] = ImageTk.PhotoImage(image)
        self.image[row] = image

        image_label = tk.Label(self.root, image=self.root_image[row])
        image_label.grid(row=row, column=0, rowspan=1, padx=10, pady=10)

        self.image_label[row] = image_label
        

    def show_ui(self):
        image = Image.new('RGB', (500, 500), (0, 0, 0))
        self.load_image_on_ui_from_array(image, 0)
        self.load_image_on_ui_from_array(image, 1)
        

    def show_finish_perspective_btn(self):
        button = tk.Button(self.root, text=f"Finalizar perspectiva", command=self.finish_perspective)
        
        button.grid(row=6, column=1, padx=10, pady=10)

    def run_loop(self):
        self.root.mainloop()

    def finish_perspective(self):
        show_frame(self.main_frame)