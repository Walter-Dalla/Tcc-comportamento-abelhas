from tkinter import ttk, Canvas
from PIL import Image, ImageTk

from src.Modules.ExportModule.videoUtils import open_video
from src.utils.interfaceUtils import show_frame

class BorderUi:
    def __init__(self, root, main_frame):
        self.root = root
        self.main_frame = main_frame
        # Initial positions for frame border configuration points (corners of the box)
        self.frame_border_points = [[50, 50], [450, 50], [50, 450], [450, 450]]
        self.distances_to_border = [0, 0, 0, 0]  # Stores distances from border to each corner
        self.moving_corner = None  # To keep track of the currently dragged corner
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
        self.image_width = image.width  # Store width for distance calculation
        self.image_height = image.height  # Store height for distance calculation

        self.canvas = Canvas(self.root, width=image.width, height=image.height)
        self.canvas.grid(row=0, column=0, rowspan=400, padx=10, pady=10)
        self.canvas.create_image(0, 0, anchor="nw", image=self.root_image)

        # Draw draggable lines and corner points
        self.draw_lines()

        # Bind events for dragging lines
        self.canvas.bind("<ButtonPress-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.move_line)
        self.canvas.bind("<ButtonRelease-1>", self.stop_move)

    def draw_lines(self):
        # Clear old drawings
        self.canvas.delete("line")
        self.canvas.delete("corner")

        # Draw the red lines connecting the corners
        
        if(self.frame_border_points == None):
            self.frame_border_points = [[50, 50], [450, 50], [50, 450], [450, 450]]
        
        self.canvas.create_line(self.frame_border_points[0], self.frame_border_points[1], fill="red", width=2, tags="line")
        self.canvas.create_line(self.frame_border_points[1], self.frame_border_points[3], fill="red", width=2, tags="line")
        self.canvas.create_line(self.frame_border_points[3], self.frame_border_points[2], fill="red", width=2, tags="line")
        self.canvas.create_line(self.frame_border_points[2], self.frame_border_points[0], fill="red", width=2, tags="line")

        # Draw circles at each corner for easier dragging
        for i, (x, y) in enumerate(self.frame_border_points):
            self.canvas.create_oval(x - 5, y - 5, x + 5, y + 5, fill="blue", outline="blue", tags=("corner", f"corner_{i}"))

    def start_move(self, event):
        # Check if a corner point was clicked
        for i, (x, y) in enumerate(self.frame_border_points):
            if abs(event.x - x) < 10 and abs(event.y - y) < 10:
                self.moving_corner = i  # Store the index of the corner being moved
                break

    def move_line(self, event):
        # Update the position of the corner being moved
        if self.moving_corner is not None:
            # Enforce perpendicular movement based on the corner being moved
            if self.moving_corner == 0:  # Top-left corner
                self.frame_border_points[0][1] = event.y  # Move only vertically
                self.frame_border_points[1][1] = event.y  # Update top-right corner to align
            elif self.moving_corner == 1:  # Top-right corner
                self.frame_border_points[1][1] = event.y  # Move only vertically
                self.frame_border_points[0][1] = event.y  # Update top-left corner to align
            elif self.moving_corner == 2:  # Bottom-left corner
                self.frame_border_points[2][1] = event.y  # Move only vertically
                self.frame_border_points[3][1] = event.y  # Update bottom-right corner to align
            elif self.moving_corner == 3:  # Bottom-right corner
                self.frame_border_points[3][1] = event.y  # Move only vertically
                self.frame_border_points[2][1] = event.y  # Update bottom-left corner to align

            # For left or right movements
            if self.moving_corner == 0:  # Top-left corner
                self.frame_border_points[0][0] = event.x  # Move only horizontally
                self.frame_border_points[2][0] = event.x  # Update bottom-left corner to align
            elif self.moving_corner == 1:  # Top-right corner
                self.frame_border_points[1][0] = event.x  # Move only horizontally
                self.frame_border_points[3][0] = event.x  # Update bottom-right corner to align
            elif self.moving_corner == 2:  # Bottom-left corner
                self.frame_border_points[2][0] = event.x  # Move only horizontally
                self.frame_border_points[0][0] = event.x  # Update top-left corner to align
            elif self.moving_corner == 3:  # Bottom-right corner
                self.frame_border_points[3][0] = event.x  # Move only horizontally
                self.frame_border_points[1][0] = event.x  # Update top-right corner to align

            self.draw_lines()  # Redraw lines with updated points

    def stop_move(self, event):
        # Stop moving the corner
        self.moving_corner = None
        self.calculate_distances_to_border()
        print("Distances to border:", self.distances_to_border)

    def calculate_distances_to_border(self):
        # Calculate the distances from each corner to the nearest border
        self.distances_to_border = [
            self.frame_border_points[0][0],  # Distance to the left border
            self.frame_border_points[1][1],  # Distance to the top border
            self.image_width - self.frame_border_points[3][0],  # Distance to the right border
            self.image_height - self.frame_border_points[2][1]  # Distance to the bottom border
        ]

    def show_ui(self):
        image = Image.new('RGB', (500, 500), (0, 0, 0))
        self.load_image_on_ui_from_array(image)

        # "Finalizar" button to finalize border configuration
        finalize_button = ttk.Button(self.root, text="Finalizar", command=self.finish_border_config)
        finalize_button.grid(row=8, column=1, padx=10, pady=10)

        # "Resetar" button to reset border configuration 50px from the image border
        reset_button = ttk.Button(self.root, text="Resetar", command=self.reset_border_config)
        reset_button.grid(row=8, column=2, padx=10, pady=10)

    def finish_border_config(self):
        self.calculate_distances_to_border()
        print("Final distances to border:", self.distances_to_border)
        show_frame(self.main_frame)

    def reset_border_config(self):
        # Reset the corners to be 50px away from the image border
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
