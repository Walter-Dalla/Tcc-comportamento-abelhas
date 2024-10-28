import tkinter as tk
from tkinter import Canvas, filedialog
from PIL import Image, ImageTk

class ImageLineAdjuster:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Line Adjuster")
        
        # Cria um canvas para exibir a imagem
        self.canvas = Canvas(root, width=600, height=400)
        self.canvas.pack()

        # Carregar uma imagem
        self.load_image()

        # Inicializando as coordenadas das linhas
        self.line_top = self.canvas.create_line(0, 50, self.img_width, 50, fill="red", width=2)
        self.line_bottom = self.canvas.create_line(0, self.img_height - 50, self.img_width, self.img_height - 50, fill="red", width=2)
        self.line_left = self.canvas.create_line(50, 0, 50, self.img_height, fill="blue", width=2)
        self.line_right = self.canvas.create_line(self.img_width - 50, 0, self.img_width - 50, self.img_height, fill="blue", width=2)

        # Para armazenar a linha que será movida
        self.current_line = None

        # Eventos do mouse para mover as linhas
        self.canvas.tag_bind(self.line_top, '<B1-Motion>', self.move_line)
        self.canvas.tag_bind(self.line_bottom, '<B1-Motion>', self.move_line)
        self.canvas.tag_bind(self.line_left, '<B1-Motion>', self.move_line)
        self.canvas.tag_bind(self.line_right, '<B1-Motion>', self.move_line)

        # Captura a posição da linha
        self.canvas.bind("<ButtonRelease-1>", self.get_line_position)

    def load_image(self):
        # Aqui você pode carregar sua própria imagem
        file_path = filedialog.askopenfilename()
        self.image = Image.open(file_path)
        self.img_width, self.img_height = self.image.size

        # Redimensionar a imagem se necessário
        self.image = self.image.resize((600, 400), Image.ANTIALIAS)
        self.tk_image = ImageTk.PhotoImage(self.image)

        # Exibir a imagem no canvas
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

    def move_line(self, event):
        # Mover a linha baseada em qual linha está sendo arrastada
        if event.widget.find_withtag('current')[0] == self.line_top:
            self.canvas.coords(self.line_top, 0, event.y, self.img_width, event.y)
        elif event.widget.find_withtag('current')[0] == self.line_bottom:
            self.canvas.coords(self.line_bottom, 0, event.y, self.img_width, event.y)
        elif event.widget.find_withtag('current')[0] == self.line_left:
            self.canvas.coords(self.line_left, event.x, 0, event.x, self.img_height)
        elif event.widget.find_withtag('current')[0] == self.line_right:
            self.canvas.coords(self.line_right, event.x, 0, event.x, self.img_height)

    def get_line_position(self, event):
        # Obtém a posição da linha após o movimento
        top_coords = self.canvas.coords(self.line_top)
        bottom_coords = self.canvas.coords(self.line_bottom)
        left_coords = self.canvas.coords(self.line_left)
        right_coords = self.canvas.coords(self.line_right)

        print(f"Top Line Y: {top_coords[1]}")
        print(f"Bottom Line Y: {bottom_coords[1]}")
        print(f"Left Line X: {left_coords[0]}")
        print(f"Right Line X: {right_coords[0]}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ImageLineAdjuster(root)
    root.mainloop()
