import cv2
import numpy as np

from imageAnalizer.perspective import find_perspective, fix_perspective
from imageAnalizer.imageAnalizer import OpenVideo

def get_frame_params(video_path, isDebugMode):
    
    print("Iniciando analise moldura")
    video = OpenVideo(video_path)

    success, frame = video.read()
    image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    
    maxPointTopLeft = (0, 0)
    maxPointTopRight = (0, 0)
    maxPointBottonLeft = (0, 0)
    maxPointBottonRight = (0, 0)

    finishedPerspective = False

    while not finishedPerspective:
        finishedPerspective, perspective_frame = find_perspective(frame)
        if perspective_frame is not 0:
            frame = perspective_frame
        
        cv2.waitKey(10)

    while True:
        
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Definições para detecção de cores (vermelho e azul em RGB)
        red_lower = np.array([100, 0, 0])
        red_upper = np.array([255, 100, 100])

        mask_red = cv2.inRange(image_rgb, red_lower, red_upper)
        
        kernel = np.ones((5, 5), np.uint8)
        mask_red_cleaned = cv2.morphologyEx(mask_red, cv2.MORPH_OPEN, kernel)
        mask_red_cleaned = cv2.morphologyEx(mask_red_cleaned, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask_red_cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        print(contours)
        image_contours = image_rgb.copy()
        cv2.drawContours(image_contours, contours, -1, (0, 255, 0), 1)

        contour_info = []
        contour_dimensions = []
        
        if not isDebugMode or cv2.waitKey(10) == 27: #esc
            success, frame = video.read()
            _, frame = fix_perspective(frame)
            
            ## Frame analise
            x, y, width, height  = cv2.boundingRect(contours[0])

            maxPointBottonLeft = maxPointTopLeft = maxPointTopRight = maxPointBottonRight = (x, y)
            for contour in contours:
                x, y, width, height = cv2.boundingRect(contour)
                contour_dimensions.append((width, height))


                if x < maxPointTopLeft[0] and y < maxPointTopLeft[1]:
                    maxPointTopLeft = (x, y)
                    
                if x < maxPointBottonLeft[0] and y > maxPointBottonLeft[1]:
                    maxPointBottonLeft = (x, y)

                if x > maxPointTopRight[0] and y < maxPointTopRight[1]:
                    maxPointTopRight = (x, y)

                if x > maxPointBottonRight[0] and y > maxPointBottonRight[1]:
                    maxPointBottonRight = (x, y)

            print([
                maxPointBottonLeft,
                maxPointTopLeft,
                maxPointTopRight,
                maxPointBottonRight
            ])

            if not success:
                break

        
        if isDebugMode:
            cv2.circle(image_contours, maxPointBottonLeft, 10, (255, 0, 0), -1) #R
            cv2.circle(image_contours, maxPointTopLeft, 10, (0, 255, 0), -1)    #G
            cv2.circle(image_contours, maxPointBottonRight, 10, (0, 0, 255), -1)#B
            cv2.circle(image_contours, maxPointTopRight, 10, (0, 0, 0), -1)     #P

            cv2.imshow('image_contours', image_contours)

            
    video.release()
    cv2.destroyAllWindows()
    
    print("Fim da analise da moldura")

    print(contour_info)
