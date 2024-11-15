import cv2
import numpy as np

def remove_background(raw_warpped_frames, debug_mode, is_side):
    global clicked_position
    resume_debug_mode = False
    selected_random_frames = []
    
    frame_block = 500
    
    for index in range(0, len(raw_warpped_frames), frame_block):
        selected_random_frames.append(raw_warpped_frames[index])
        
    max_frame = np.max(selected_random_frames, axis=0).astype(np.uint8)
    
    frames = []
    minThreshold = 80
    contour_positions = []
    for i, frame in enumerate(raw_warpped_frames):
        dif_frame = cv2.absdiff(max_frame, frame)
        
        _, diff = cv2.threshold(dif_frame, minThreshold, 255, cv2.THRESH_BINARY)
        _, binarizada = cv2.threshold(diff, 127, 255, cv2.THRESH_BINARY)
        frames.append(diff)
        
        contornos, _ = cv2.findContours(binarizada, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        contour_position = (-1, -1)
        if len(contornos) > 0:
            max_contour = max(contornos, key=cv2.contourArea)
            max_contour_pos = cv2.moments(max_contour)
            
            if max_contour_pos["m00"] != 0:
                cx = int(max_contour_pos["m10"] / max_contour_pos["m00"])
                cy_from_top = int(max_contour_pos["m01"] / max_contour_pos["m00"])
                frame_height = diff.shape[0]
                cy_from_bottom = frame_height - cy_from_top
                contour_position = (cx, cy_from_bottom)

            if debug_mode:
                cv2.drawContours(frame, [max_contour], -1, (0, 255, 0), 2)
            
        contour_positions.append(contour_position)
        
        if debug_mode and not resume_debug_mode:
            frame_name = 'side' if is_side else 'top'
            
            # Set mouse callback to capture click position
            
            cv2.imshow(frame_name+"_dif_frame", dif_frame)
            cv2.imshow(frame_name+"_diff", diff)
            cv2.imshow(frame_name+"_frame", frame)
            
            key = cv2.waitKey(1) & 0xFF
               
            if key == ord('n'):  # 'n' key
                continue
            elif key == 27:  # ESC key
                cv2.destroyAllWindows()
                resume_debug_mode = True
        
    return frames, contour_positions
