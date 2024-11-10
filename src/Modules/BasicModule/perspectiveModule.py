import cv2
import numpy as np

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
        
        gray_frame = cv2.cvtColor(warppedFrame, cv2.COLOR_BGR2GRAY)
        raw_warpped_frames.append(gray_frame)
    
    originalVideo.release()
    return raw_warpped_frames


def perspective(frame, frame_points):
    
    width, height = get_perspective_size(frame_points)

    points1 = np.float32(frame_points[0:4])
    points2 = np.float32([(0,0), (width, 0), (0, height), (width, height)])

    matrix = cv2.getPerspectiveTransform(points1, points2)
    output = cv2.warpPerspective(frame, matrix, (width, height))

    return output


def fix_perspective(frame, frame_points):
    if len(frame_points) == 4:
        return True, perspective(frame, frame_points)

    return False, 0


def get_perspective_size(frame_points):
   width = frame_points[1][0] - frame_points[0][0]
   height = frame_points[2][1] - frame_points[0][1]
   
   return width, height

def get_frame_points(event, frame_points):
    x, y = event.x, event.y
    
    x = x*2
    y = y*2
    
    if len(frame_points) >= 4:
        return
    
    frame_points.append((int(x), int(y)))