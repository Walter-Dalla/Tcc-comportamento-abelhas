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

    fps =  int(originalVideo.get(cv2.CAP_PROP_FPS))
    
    raw_warpped_frames = []
    while True:
        success, frame = originalVideo.read()
        if not success:
            break
        
        warppedFrame = perspective(frame, frame_points)
        raw_warpped_frames.append(warppedFrame)
    
    originalVideo.release()
    
    median = np.median(raw_warpped_frames, axis=0).astype(np.uint8)
    median = cv2.cvtColor(median, cv2.COLOR_BGR2GRAY)
    
    frames = []
    for frame in raw_warpped_frames:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        dif_frame = cv2.absdiff(median, frame)
        threshold, diff = cv2.threshold(
            dif_frame, 40, 255, cv2.THRESH_BINARY)
        
        frames.append(diff)
    
    data = []
    
    if(is_side):
        data = analyze_frame_side(frames)
    else:
        data = analyze_frame_top(frames)
    
    return success, frames, fps, data, raw_warpped_frames
