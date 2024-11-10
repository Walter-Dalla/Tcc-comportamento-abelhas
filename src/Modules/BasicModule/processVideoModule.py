import concurrent.futures
import cv2

from src.Modules.BasicModule.routeAnalizer import route_module
from src.Modules.BasicModule.utils.GetData import get_video_data
from src.Modules.ExportModule.jsonUtils import export_data_to_file
from src.Modules.BasicModule.backgroundRemoveModule import remove_background
from src.Modules.BasicModule.sideAnalizer import analyze_frame_side
from src.Modules.BasicModule.topAnalizer import analyze_frame_top
from src.Modules.BasicModule.perspectiveModule import process_perspective
from src.Modules.ExportModule.videoUtils import open_video


def process_basic_modules(frame_perspective_points_top,
                  frame_perspective_points_side, 
                  top_video_path,
                  side_video_path,
                  width_box_cm, height_box_cm, depth_box_cm, 
                  selected_config,
                  frame_border_points_top,
                  frame_border_points_side
                  ):
    
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future_top = executor.submit(process_video, frame_perspective_points_top, top_video_path, False)
        future_side = executor.submit(process_video, frame_perspective_points_side, side_video_path, True)

        side_success, side_frames, fps, side_data, side_raw_warpped_frames = future_side.result()
        top_success, top_frames, fps, top_data, top_raw_warpped_frames = future_top.result()

    if not (top_success and side_success):
        print("Erro ocorreu durante o proces video")
        return False

    pixel_to_cm_ratio = get_video_data(
        width_box_cm=float(width_box_cm),
        height_box_cm=float(height_box_cm),
        depth_box_cm=float(depth_box_cm),
        top_frames=top_frames,
        side_frames=side_frames
    )

    data = route_module(top_data, side_data)
    data["width_box_cm"] = float(width_box_cm)
    data["height_box_cm"] = float(height_box_cm)
    data["depth_box_cm"] = float(depth_box_cm)
    data["pixel_to_cm_ratio"] = pixel_to_cm_ratio
    data["fps"] = fps
    data["frame_border_points_top"] = frame_border_points_top
    data["frame_border_points_side"] = frame_border_points_side
    
    output_location = f"./cache/outputs/{selected_config}.json"
    export_data_to_file(data, output_location)
    
    return True

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