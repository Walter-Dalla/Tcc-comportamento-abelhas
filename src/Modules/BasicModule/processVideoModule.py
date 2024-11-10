import cv2

from src.Modules.BasicModule.backgroundRemoveModule import remove_background
from src.Modules.BasicModule.sideAnalizer import analyze_frame_side
from src.Modules.BasicModule.topAnalizer import analyze_frame_top
from src.Modules.BasicModule.perspectiveModule import process_perspective
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