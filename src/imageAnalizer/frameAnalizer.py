import time
import cv2
import numpy as np

from imageAnalizer.Perspective.perspective import fix_perspective
from imageAnalizer.movimentAnalizer import OpenVideo
from imageAnalizer.contoursAnalizer import contoursAnalizerHsv
from Ui.PerspectiveUi import get_next_frame, getScreen, load_image_on_ui, set_next_frame


def get_frame_params(video_path, isDebugMode):
    
    print("Iniciando analise moldura")
    video = OpenVideo(video_path)

    success, frame = video.read()

    finishedPerspective = False

    load_image_on_ui(frame)
    i=0
    while not finishedPerspective:
        finishedPerspective, perspective_frame = fix_perspective(frame)
        i +=1
        time.sleep(0.01)
        if perspective_frame is not 0:
            load_image_on_ui(perspective_frame)

            getScreen().show_finish_perspective_btn()

    analizedContours = False
    return
    has_att = True

    while True:
        if not analizedContours:
            contours, image_contours = contoursAnalizerHsv(frame)
            analizedContours = True
        
        if not isDebugMode or cv2.waitKey(10) == 27 or get_next_frame(): #esc

            set_next_frame(False)
            
            has_att = True
            success, frame = video.read()
            analizedContours = False
            _, frame = fix_perspective(frame)
            

            frame2 = frame.copy()
            cv2.imshow('frame2', frame2)
            contornos2 = detect_contours(frame2)
            cv2.drawContours(frame2, contornos2, -1, (0, 255, 0), 1)
            cv2.imshow('image_contours_2', frame2)

            cv2.drawContours(frame, contours, -1, (0, 255, 0), 1)
            cv2.imshow('image_contours', frame)

            if not success:
                break

    video.release()
    cv2.destroyAllWindows()
    
    print("Fim da analise da moldura")

def detect_contours(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cv2.imshow('gray', gray)
    _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours