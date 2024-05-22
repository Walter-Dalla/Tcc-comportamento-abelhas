import cv2
import numpy as np


def contoursAnalizer(mask_red):
    kernel = np.ones((5, 5), np.uint8)
    mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_OPEN, kernel)
    mask_red = cv2.morphologyEx(mask_red, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask_red, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    print(len(contours))
    image_contours = mask_red.copy()
    
    return contours, image_contours


def contoursAnalizerHsv(image):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    
    # Nota: O vermelho pode ter duas partes devido à sua posição no espectro de cores HSV
    red_lower1 = np.array([0, 120, 70])
    red_upper1 = np.array([10, 255, 255])

    red_lower2 = np.array([150, 30, 70])
    red_upper2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, red_lower1, red_upper1)
    mask2 = cv2.inRange(hsv, red_lower2, red_upper2)

    mask_red = cv2.bitwise_or(mask1, mask2)
    
    contours, image_contours = contoursAnalizer(mask_red)
    
    y_line = [5, 644]
    x_line = [5, 440]


    countY = 0
    countX = 0
    for contour in contours:
        found= False
        for point in contour:
            x, y = point[0]
            if y in y_line:
                countY += 1
                found= True

            if x in x_line:  
                countX += 1
                found = True
                
            if found:
                break
            
    return contours, image_contours


   