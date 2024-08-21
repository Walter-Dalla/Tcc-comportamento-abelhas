import cv2
import numpy as np

from src.imageAnalizer.Perspective.perspective import perspective
from src.utils.videoUtils import open_video

def process_video(frame_points, input_video_path):
    success, originalVideo = open_video(input_video_path)
    if not success:
        return False, None, None

    fps =  int(originalVideo.get(cv2.CAP_PROP_FPS))
    
    warppedFrames = []
    while True:
        success, frame = originalVideo.read()
        if not success:
            break
        
        warppedFrame = perspective(frame, frame_points)
        warppedFrames.append(warppedFrame)
    
    originalVideo.release()
    
    median = np.median(warppedFrames, axis=0).astype(np.uint8)
    median = cv2.cvtColor(median, cv2.COLOR_BGR2GRAY)
    
    frames = []
    for frame in warppedFrames:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dif_frame = cv2.absdiff(median, frame)
        threshold, diff = cv2.threshold(
            dif_frame, 100, 255, cv2.THRESH_BINARY)
        
        frames.append(diff)
    
    return success, frames, fps
