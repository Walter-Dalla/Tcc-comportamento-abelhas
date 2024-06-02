import cv2
import numpy as np

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
    if len(frame_points) >= 4:
        return
    
    frame_points.append((x, y))