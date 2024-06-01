import cv2
import numpy as np

def add_moving_point_to_frame(frame, t, width, height):
    # Define the size and position of the square
    square_size = 100
    center_x, center_y = width // 2, height // 2
    half_size = square_size // 2

    # Calculate the position of the point (moving up and down)
    point_y = int(center_y + half_size * np.sin(2 * np.pi * t))
    point_x = center_x  # The x position remains constant

    # Draw the square (optional, can be uncommented if needed)
    # top_left = (center_x - half_size, center_y - half_size)
    # bottom_right = (center_x + half_size, center_y + half_size)
    # cv2.rectangle(frame, top_left, bottom_right, (255, 255, 255), 2)

    # Draw the moving point
    cv2.circle(frame, (point_x, point_y), 5, (0, 0, 0), -1)

    return frame

def process_video(input_video_path, output_video_path):
    cap = cv2.VideoCapture(input_video_path)
    if not cap.isOpened():
        print("Error: Could not open video.")
        return

    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    for frame_idx in range(frame_count):
        ret, frame = cap.read()
        if not ret:
            break

        t = (frame_idx % fps) / fps
        frame = add_moving_point_to_frame(frame, t, width, height)
        out.write(frame)

    cap.release()
    out.release()

# Exemplo de uso
input_video_path = "C:/Projetos/Tcc-comportamento-abelhas/resource/Frame.mp4"  # Substitua pelo caminho do seu vídeo de entrada
output_video_path = 'output_video.avi'  # Substitua pelo caminho do seu vídeo de saída
process_video(input_video_path, output_video_path)
