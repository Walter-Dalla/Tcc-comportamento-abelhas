import cv2
from numpy import median

def get_video_data(width_box_cm, height_box_cm, depth_box_cm, top_video, side_video):
    
    fps_top =  int(top_video.get(cv2.CAP_PROP_FPS))
    height_top =  int(top_video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width_top =  int(top_video.get(cv2.CAP_PROP_FRAME_WIDTH))
    
    
    fps_side =  int(side_video.get(cv2.CAP_PROP_FPS))
    height_side =  int(side_video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width_side =  int(side_video.get(cv2.CAP_PROP_FRAME_WIDTH))
    
    pixel_to_cm_ratio_height = height_side/height_box_cm
    pixel_to_cm_ratio_width = height_side/width_box_cm
    pixel_to_cm_ratio_depth = height_side/depth_box_cm
    
    pixel_to_cm_ratio = median([pixel_to_cm_ratio_height, pixel_to_cm_ratio_width, pixel_to_cm_ratio_depth])
    
    return fps_top, pixel_to_cm_ratio