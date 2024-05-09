import cv2
import numpy as np


def perspective(framePoints, image_contours):
    width = framePoints[1][0] - framePoints[0][0]
    height = framePoints[2][1] - framePoints[0][1]
    points1 = np.float32(framePoints[0:4])
    points2 = np.float32([(0,0), (width, 0), (0, height), (width, height)])

    matrix = cv2.getPerspectiveTransform(points1, points2)
    output = cv2.warpPerspective(image_contours, matrix, (width, height))

    return output


def find_perspective(frame):
    if len(framePoints) == 4:
        cv2.destroyWindow('Definir Perspectiva')
    
    return fix_perspective(frame)

def fix_perspective(frame):
    
    if len(framePoints) == 4:
        return True, perspective(framePoints, frame)

    for index in framePoints:
        cv2.circle(frame, index, 10, (0, 0, 0), -1) #R
        
    cv2.imshow('Definir Perspectiva', frame)
    cv2.setMouseCallback('Definir Perspectiva', getFramePoints)
    

    return False, 0

framePoints = []
def getFramePoints(event, x, y, flags, params):
    if len(framePoints) >= 4:
        return
    if event == cv2.EVENT_LBUTTONDOWN:
        framePoints.append((x, y))