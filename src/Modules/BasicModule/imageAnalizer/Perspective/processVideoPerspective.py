import cv2
import numpy as np

from src.Modules.BasicModule.sideAnalizer import analyze_frame_side
from src.Modules.BasicModule.topAnalizer import analyze_frame_top
from src.Modules.BasicModule.imageAnalizer.Perspective.perspective import perspective
from src.Modules.ExportModule.videoUtils import open_video

def process_video(frame_points, input_video_path, is_side):
    success, originalVideo = open_video(input_video_path)
    if not success:
        return False, None, None
    fps = int(originalVideo.get(cv2.CAP_PROP_FPS))
    raw_warpped_frames = process_perspective(originalVideo, frame_points)
    frames = remove_background(raw_warpped_frames)

    data = []
    
    if is_side:
        data = analyze_frame_side(frames)
    else:
        data = analyze_frame_top(frames)
    
    success = True
    
    return success, frames, fps, data, raw_warpped_frames

def process_perspective(originalVideo, frame_points):
    if(len(frame_points) != 4):
        video_width = int(originalVideo.get(cv2.CAP_PROP_FRAME_WIDTH))
        video_height = int(originalVideo.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        frame_points = [
            [0, 0],
            [video_width, 0],
            [0, video_height],
            [video_width, video_height]
        ]
    
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
    return raw_warpped_frames
    
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