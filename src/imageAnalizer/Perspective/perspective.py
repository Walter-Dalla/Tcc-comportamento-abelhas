import cv2
import numpy as np

#framePoints = []
framePoints = [(25, 119), (444, 107), (23, 741), (472, 715)]

def perspective(frame):
    
    width, height = getPerspectiveSize()

    points1 = np.float32(framePoints[0:4])
    points2 = np.float32([(0,0), (width, 0), (0, height), (width, height)])

    matrix = cv2.getPerspectiveTransform(points1, points2)
    output = cv2.warpPerspective(frame, matrix, (width, height))

    return output


def fix_perspective(frame):
    #_framePoints = [(10, 99), (452, 99), (15, 751), (477, 728)]
    #framePoints = [(25, 119), (444, 107), (23, 741), (472, 715)]

    if len(framePoints) == 4:
        return True, perspective(frame)

    return False, 0


def getPerspectiveSize():
   width = framePoints[1][0] - framePoints[0][0]
   height = framePoints[2][1] - framePoints[0][1]
   
   return width, height

def getFramePoints(event):
    x, y = event.x, event.y
    if len(framePoints) >= 4:
        return
    
    framePoints.append((x, y))