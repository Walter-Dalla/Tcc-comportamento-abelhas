import time
import cv2

from imageAnalizer.Perspective.perspective import fix_perspective
from Ui.PerspectiveUi import load_image_on_ui, show_ui
from imageAnalizer.videoHelper import OpenVideo


def get_frame_params(video_path, isDebugMode, screen):
    
    print("Iniciando analise moldura")
    video = OpenVideo(video_path)
    

    success, frame = video.read()
    if not success:
        return
    finishedPerspective = False

    load_image_on_ui(frame, screen)
    
    while not finishedPerspective:
        finishedPerspective, perspective_frame = fix_perspective(frame)
        time.sleep(0.01)
        #print(perspective_frame)
        if perspective_frame is not 0:
            load_image_on_ui(perspective_frame, screen)

            screen.show_finish_perspective_btn()
    
    video.release()

def detect_contours(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cv2.imshow('gray', gray)
    _, thresh = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours