import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk, ImageOps, ImageDraw
from imageAnalizer.perspective import getFramePoints

root = tk.Tk()

class App:
    def __init__(self, root):
        self.root = root
        self.show_ui()
        self.next_frame = False
        self.step = "perspective"

    def load_image_on_ui(self, image):
        self.root_image = ImageTk.PhotoImage(image)
        self.image = image

        image_label = ttk.Label(root, image=self.root_image)
        image_label.grid(row=0, column=0, rowspan=400, padx=10, pady=10)

        image_label.bind("<Button-1>", getFramePoints)
        image_label.bind("<Motion>", self.on_motion)
        self.image_label = image_label

    def load_small_image_on_ui(self, image):
        self.small_image = ImageTk.PhotoImage(image)
        
        small_image_label = ttk.Label(root, image=self.small_image)
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
    
    def on_button_click(self, button_number):
        print(f"Botão {button_number} clicado")


    def show_ui(self):
        root.title("Interface com Imagem e Botões")

        image = Image.new('RGB', (500, 500), (0, 0, 0))
        self.load_image_on_ui(image)

        small_image = Image.new('RGB', (100, 100), (0, 0, 0))
        self.load_small_image_on_ui(small_image)
        
        buttons = []
        
        button = ttk.Button(root, text=f"Proximo Frame", command=lambda i=1: self.set_next_frame(True))
        button.grid(row=5, column=1, padx=10, pady=10)
        buttons.append(button)

    def show_finish_perspective_btn(self):
        button = ttk.Button(root, text=f"Finalizar perspectiva", command=lambda i="finish-perspective-btn": self.clear_screen())
        button.grid(row=6, column=1, padx=10, pady=10)

    def get_next_frame(self):
        return self.next_frame
    
    def set_next_frame(self, value):
        self.next_frame = value

    def run_loop(self):
        self.root.mainloop()

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

def show_ui():
    print("criado!")

def get_next_frame():
    return screen.get_next_frame()

def set_next_frame(value):
    return screen.set_next_frame(value)

def run_loop():
    root.mainloop()

def load_image_on_ui(imageCv):
        image = Image.fromarray(imageCv)
        screen.load_image_on_ui(image)

def getScreen():
    return screen
    


screen = App(root)