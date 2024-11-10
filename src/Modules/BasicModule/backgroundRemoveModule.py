import cv2
import numpy as np

def remove_background(raw_warpped_frames):
    selected_random_frames = []
    
    frame_block = 500
    
    for index in range(0, len(raw_warpped_frames), frame_block):
        selected_random_frames.append(raw_warpped_frames[index])
        
    max_frame = np.max(selected_random_frames, axis=0).astype(np.uint8)
    
    frames = []
    minThreshold = 100
    for i, frame in enumerate(raw_warpped_frames):
        dif_frame = cv2.absdiff(max_frame, frame)
        
        _, diff = cv2.threshold(dif_frame, minThreshold, 255, cv2.THRESH_BINARY)
        _, binarizada = cv2.threshold(diff, 127, 255, cv2.THRESH_BINARY)
        
        contornos, _ = cv2.findContours(binarizada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if(len(contornos) > 0):
            maior_contorno = max(contornos, key=cv2.contourArea)
            cv2.drawContours(frame, [maior_contorno], -1, (0, 255, 0), 2)
        
        frames.append(diff)
        
    return frames