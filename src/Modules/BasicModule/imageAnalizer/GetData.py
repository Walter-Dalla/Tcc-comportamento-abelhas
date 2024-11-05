from numpy import median

def get_video_data(width_box_cm, height_box_cm, depth_box_cm, side_frames, top_frames):
    
    height_top, width_top = top_frames[0].shape
    height_side, width_side = side_frames[0].shape
    
    pixel_to_cm_ratio_height = height_side/height_box_cm
    pixel_to_cm_ratio_width = height_side/width_box_cm
    pixel_to_cm_ratio_depth = height_side/depth_box_cm
    
    pixel_to_cm_ratio = median([pixel_to_cm_ratio_height, pixel_to_cm_ratio_width, pixel_to_cm_ratio_depth])
    
    return pixel_to_cm_ratio