import cv2

from src.Modules.BasicModule.backgroundRemoveModule import remove_background
from src.Modules.BasicModule.sideAnalizer import analyze_frame_side
from src.Modules.BasicModule.topAnalizer import analyze_frame_top
from src.Modules.BasicModule.perspectiveModule import process_perspective
from src.Modules.ExportModule.videoUtils import open_video

import cv2
import time

def process_video(frame_points, input_video_path, is_side, debug_mode):
    start_time = time.time()
    
    success, originalVideo = open_video(input_video_path)
    if not success:
        return False, None, None
    time_open_video = time.time()
    
    fps = int(originalVideo.get(cv2.CAP_PROP_FPS))
    time_get_fps = time.time()
    
    raw_warpped_frames = process_perspective(originalVideo, frame_points)
    time_process_perspective = time.time()
    
    frames = remove_background(raw_warpped_frames, debug_mode, is_side)
    time_remove_background = time.time()

    data = []
    if is_side:
        data = analyze_frame_side(frames)
    else:
        data = analyze_frame_top(frames)
    time_analyze_frames = time.time()

    if(debug_mode):
        print(f"Time to open video: {time_open_video - start_time:.4f} seconds")
        print(f"Time to get FPS: {time_get_fps - time_open_video:.4f} seconds")
        print(f"Time to process perspective: {time_process_perspective - time_get_fps:.4f} seconds")
        print(f"Time to remove background: {time_remove_background - time_process_perspective:.4f} seconds")
        print(f"Time to analyze frames: {time_analyze_frames - time_remove_background:.4f} seconds")
        print(f"Total time: {time_analyze_frames - start_time:.4f} seconds")

    success = True
    
    return success, frames, fps, data, raw_warpped_frames
