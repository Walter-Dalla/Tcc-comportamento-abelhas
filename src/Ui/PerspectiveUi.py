import time
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps, ImageDraw
from imageAnalizer.Perspective.perspective import fix_perspective, getFramePoints, getPerspectiveSize
from imageAnalizer.Route.routeAnalizer import route
from imageAnalizer.Perspective.processVideoPerspective import process_video
from plot.plotRoute import plotInsectRouteOnGraph
from imageAnalizer.videoHelper import OpenVideo

class PerspectiveUi:
    def __init__(self, root, topVideoPath, sideVideoPath):
        self.root = root
        self.next_frame = False
        self.state = "perspective"
        self.topVideoPath = topVideoPath
        self.sideVideoPath = sideVideoPath
        
        self.show_ui()

    def startUp(self):
        print("Iniciando analise moldura")
        video = OpenVideo(self.sideVideoPath)
        
        success, frame = video.read()
        if not success:
            return
        finishedPerspective = False

        self.loadImageOnUiFromCv2(frame)
        
        while not finishedPerspective:
            finishedPerspective, perspective_frame = fix_perspective(frame)
            time.sleep(0.01)
            if perspective_frame is not 0:
                self.loadImageOnUiFromCv2(perspective_frame)

                self.show_finish_perspective_btn()
        
        video.release()

    def loadImageOnUiFromArray(self, image):
        self.root_image = ImageTk.PhotoImage(image)
        self.image = image

        image_label = ttk.Label(self.root, image=self.root_image)
        image_label.grid(row=0, column=0, rowspan=400, padx=10, pady=10)

        image_label.bind("<Button-1>", getFramePoints)
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
        self.root.title("Interface com Imagem e Botões")

        image = Image.new('RGB', (500, 500), (0, 0, 0))
        self.loadImageOnUiFromArray(image)

        small_image = Image.new('RGB', (100, 100), (0, 0, 0))
        self.load_small_image_on_ui(small_image)
        

    def show_finish_perspective_btn(self):
        button = ttk.Button(self.root, text=f"Finalizar perspectiva", command=lambda i="finish-perspective-btn": self.finishPerspective())
        button.grid(row=6, column=1, padx=10, pady=10)

    def get_next_frame(self):
        return self.next_frame
    
    def set_next_frame(self, value):
        self.next_frame = value

    def run_loop(self):
        self.root.mainloop()

    def finishPerspective(self):
        _, top_video = process_video(inputVideoPath=self.topVideoPath, tempName="top")
        _, side_video = process_video(inputVideoPath=self.sideVideoPath, tempName="side")
        outputLocation = "C:/Projetos/Tcc-comportamento-abelhas/output/output_data.json"
        route(top_video, side_video, outputLocation)

        self.clear_screen()

        width, height =  getPerspectiveSize()

        xlim = (0, width)
        ylim = (0, height)
        zlim = (0, height)


        plotInsectRouteOnGraph(outputLocation, xlim, ylim, zlim)
    
    def loadImageOnUiFromCv2(self, imageCv):
        image = Image.fromarray(imageCv)
        self.loadImageOnUiFromArray(image)

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

def show_ui():
    topVideoPath = "C:/Projetos/Tcc-comportamento-abelhas/resource/frame-with-incect.avi"
    sideVideoPath = "C:/Projetos/Tcc-comportamento-abelhas/resource/frame-with-incect.avi"
    
    root = tk.Tk()
    screen = PerspectiveUi(root, topVideoPath, sideVideoPath)

    return screen

def run_loop(screen):
    screen.root.mainloop()


