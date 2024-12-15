from tkinter import ttk, Canvas
from PIL import Image, ImageTk

from src.Modules.ExportModule.videoUtils import open_video
from src.utils.interfaceUtils import show_frame

class BorderUi:
    def __init__(self, root, main_frame):
        self.root = root
        self.main_frame = main_frame
        
        self.frame_border_points = [[50, 50], [450, 50], [50, 450], [450, 450]]
        self.distances_to_border = [0, 0, 0, 0] 
        self.moving_corner = None  
        self.show_ui()

    def startUp(self, videoPath):
        print("Iniciando analise da borda")
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

        self.load_image_on_ui_from_cv2(frame)
        
        video.release()

    def load_image_on_ui_from_array(self, image):
        image_height, image_width = image.size
        image.thumbnail((image_height / 2, image_width / 2), Image.Resampling.LANCZOS)
        
        self.root_image = ImageTk.PhotoImage(image)
        self.image = image
        self.image_width = image.width
        self.image_height = image.height

        self.canvas = Canvas(self.root, width=image.width, height=image.height)
        self.canvas.grid(row=0, column=0, rowspan=400, padx=10, pady=10)
        self.canvas.create_image(0, 0, anchor="nw", image=self.root_image)

        self.draw_lines()

        self.canvas.bind("<ButtonPress-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.move_line)
        self.canvas.bind("<ButtonRelease-1>", self.stop_move)

    def draw_lines(self):
        self.canvas.delete("line")
        self.canvas.delete("corner")
        
        if(self.frame_border_points == None):
            self.frame_border_points = [[50, 50], [450, 50], [50, 450], [450, 450]]
        
        self.canvas.create_line(self.frame_border_points[0], self.frame_border_points[1], fill="red", width=2, tags="line")
        self.canvas.create_line(self.frame_border_points[1], self.frame_border_points[3], fill="red", width=2, tags="line")
        self.canvas.create_line(self.frame_border_points[3], self.frame_border_points[2], fill="red", width=2, tags="line")
        self.canvas.create_line(self.frame_border_points[2], self.frame_border_points[0], fill="red", width=2, tags="line")

        for i, (x, y) in enumerate(self.frame_border_points):
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="blue", outline="blue", tags=("corner", f"corner_{i}"))

    def start_move(self, event):
        for i, (x, y) in enumerate(self.frame_border_points):
            if abs(event.x - x) < 10 and abs(event.y - y) < 10:
                self.moving_corner = i  
                break

    def move_line(self, event):
        if self.moving_corner is not None:
            if self.moving_corner == 0:  
                self.frame_border_points[0][1] = event.y  
                self.frame_border_points[1][1] = event.y  
            elif self.moving_corner == 1:  
                self.frame_border_points[1][1] = event.y  
                self.frame_border_points[0][1] = event.y  
            elif self.moving_corner == 2:  
                self.frame_border_points[2][1] = event.y
                self.frame_border_points[3][1] = event.y
            elif self.moving_corner == 3:  
                self.frame_border_points[3][1] = event.y
                self.frame_border_points[2][1] = event.y

            if self.moving_corner == 0:  
                self.frame_border_points[0][0] = event.x  
                self.frame_border_points[2][0] = event.x  
            elif self.moving_corner == 1: 
                self.frame_border_points[1][0] = event.x  
                self.frame_border_points[3][0] = event.x  
            elif self.moving_corner == 2:  
                self.frame_border_points[2][0] = event.x  
                self.frame_border_points[0][0] = event.x  
            elif self.moving_corner == 3: 
                self.frame_border_points[3][0] = event.x  
                self.frame_border_points[1][0] = event.x  

            self.draw_lines()  

    def stop_move(self, event):
        self.moving_corner = None
        self.calculate_distances_to_border()
        print("Distances to border:", self.distances_to_border)

    def calculate_distances_to_border(self):
        self.distances_to_border = [
            self.frame_border_points[0][0],
            self.frame_border_points[1][1],
            self.image_width - self.frame_border_points[3][0], 
            self.image_height - self.frame_border_points[2][1]
        ]

    def show_ui(self):
        image = Image.new('RGB', (500, 500), (0, 0, 0))
        self.load_image_on_ui_from_array(image)

        finalize_button = ttk.Button(self.root, text="Finalizar", command=self.finish_border_config)
        finalize_button.grid(row=8, column=1, padx=10, pady=10)

        reset_button = ttk.Button(self.root, text="Resetar", command=self.reset_border_config)
        reset_button.grid(row=8, column=2, padx=10, pady=10)

    def finish_border_config(self):
        self.calculate_distances_to_border()
        print("Final distances to border:", self.distances_to_border)
        show_frame(self.main_frame)

    def reset_border_config(self):
        self.frame_border_points = [
            [50, 50],
            [self.image_width - 50, 50],
            [50, self.image_height - 50],
            [self.image_width - 50, self.image_height - 50]
        ]
        self.draw_lines()

    def load_image_on_ui_from_cv2(self, imageCv):
        image = Image.fromarray(imageCv)
        self.load_image_on_ui_from_array(image)
