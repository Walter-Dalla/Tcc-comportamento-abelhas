import cv2
import numpy as np

from src.internalModules.routeModuleAddons.sideAnalizer import analyze_frame_side
from src.internalModules.routeModuleAddons.topAnalizer import analyze_frame_top
from src.imageAnalizer.Perspective.perspective import perspective
from src.utils.videoUtils import open_video

def process_video(frame_points, input_video_path, is_side):
    success, originalVideo = open_video(input_video_path)
    if not success:
        return False, None, None

    fps = int(originalVideo.get(cv2.CAP_PROP_FPS))
    
    raw_warpped_frames = []
    while True:
        success, frame = originalVideo.read()
        if not success:
            break
        
        warppedFrame = perspective(frame, frame_points)
        #blur_warpped_frame = cv2.blur(warppedFrame, ksize=(5, 5))
        
        gray_frame = cv2.cvtColor(warppedFrame, cv2.COLOR_BGR2GRAY)
        raw_warpped_frames.append(gray_frame)
    
    originalVideo.release()
    
    selected_random_frames = []
    
    frame_block = 50
    
    for index in range(0, len(raw_warpped_frames), frame_block):
        selected_random_frames.append(raw_warpped_frames[index])
        
    max_frame = np.max(selected_random_frames, axis=0).astype(np.uint8)
    
    #median_frames = [cv2.cvtColor(median_frame, cv2.COLOR_BGR2GRAY) for median_frame in median_frames]
    
    frames = []
    for i, frame in enumerate(raw_warpped_frames):
        gray_frame = frame# cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        #gray_frame = denoise_image(gray_frame)
        
        median_index = i // frame_block
        dif_frame = cv2.absdiff(max_frame, gray_frame)
        
        minThreshold = 100
        
        threshold, diff = cv2.threshold(dif_frame, minThreshold, 255, cv2.THRESH_BINARY)
        
        _, binarizada = cv2.threshold(diff, 127, 255, cv2.THRESH_BINARY)
        # Encontrar os contornos
        contornos, _ = cv2.findContours(binarizada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if(len(contornos) > 0):
            # Identificar o maior contorno baseado na área
            maior_contorno = max(contornos, key=cv2.contourArea)

            # Desenhar o maior contorno na imagem original (opcional)
            cv2.drawContours(frame, [maior_contorno], -1, (0, 255, 0), 2)
        
        frames.append(diff)
    
    data = []
    
    if is_side:
        data = analyze_frame_side(frames)
    else:
        data = analyze_frame_top(frames)
    
    success = True
    
    return success, frames, fps, data, raw_warpped_frames



def denoise_image(frame):
    
    # Define a kernel size for morphological operations
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))

    # Apply opening to remove small objects
    opening = cv2.morphologyEx(frame, cv2.MORPH_OPEN, kernel)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(opening, connectivity=8)

    # Initialize output image
    output = frame.copy()

    # Remove small objects based on the area (threshold of 180 pixels)
    for i in range(1, num_labels):  # Skipping the background (label 0)
        if stats[i, cv2.CC_STAT_AREA] <= 1:
            output[labels == i] = 0
    
    return output