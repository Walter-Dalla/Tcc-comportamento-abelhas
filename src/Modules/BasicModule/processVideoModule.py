import concurrent.futures
import cv2
import time

from src.Modules.ExportModule.folderUtils import assert_dir_exists
from src.Modules.BasicModule.utils.getData import get_video_data
from src.Modules.BasicModule.routeAnalizer import route_module
from src.Modules.ExportModule.jsonUtils import export_data_to_file
from src.Modules.BasicModule.backgroundRemoveModule import remove_background
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
        debug_mode = False
        
        if(debug_mode):
            future_top = executor.submit(process_video, frame_perspective_points_top, top_video_path, False, debug_mode)
            top_success, top_frames, fps, position_top = future_top.result()
            
            future_side = executor.submit(process_video, frame_perspective_points_side, side_video_path, True, debug_mode)
            side_success, side_frames, fps, position_side = future_side.result()
        else:
            future_top = executor.submit(process_video, frame_perspective_points_top, top_video_path, False, debug_mode)
            future_side = executor.submit(process_video, frame_perspective_points_side, side_video_path, True, debug_mode)

            side_success, side_frames, fps, position_side = future_side.result()
            top_success, top_frames, fps, position_top = future_top.result()

    if not (top_success and side_success):
        print("Erro ocorreu durante o proces video")
        return False

    data = route_module(position_top, position_side)
    
    data = get_video_data(
        width_box_cm=float(width_box_cm),
        height_box_cm=float(height_box_cm),
        depth_box_cm=float(depth_box_cm),
        top_frames=top_frames,
        side_frames=side_frames,
        data= data
    )

    data["fps"] = fps
    data["frame_border_points_top"] = frame_border_points_top
    data["frame_border_points_side"] = frame_border_points_side
    
    data["frame_perspective_points_top"] = frame_perspective_points_top
    data["frame_perspective_points_side"] = frame_perspective_points_side
    
    assert_dir_exists("./cache/outputs/")
    output_location = f"./cache/outputs/{selected_config}.json"
    export_data_to_file(data, output_location)
    
    return True

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
    
    frames, position = remove_background(raw_warpped_frames, debug_mode, is_side)
    time_remove_background = time.time()

    if(debug_mode):
        print(f"Time to open video: {time_open_video - start_time:.4f} seconds")
        print(f"Time to get FPS: {time_get_fps - time_open_video:.4f} seconds")
        print(f"Time to process perspective: {time_process_perspective - time_get_fps:.4f} seconds")
        print(f"Time to remove background: {time_remove_background - time_process_perspective:.4f} seconds")
        print(f"Total time: {time_remove_background - start_time:.4f} seconds")

    success = True
    
    return success, frames, fps, position
