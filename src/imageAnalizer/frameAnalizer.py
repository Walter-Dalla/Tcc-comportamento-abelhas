import time
from imageAnalizer.Perspective.perspective import fix_perspective
from imageAnalizer.videoHelper import OpenVideo

def get_frame_params(video_path, screen):
    
    print("Iniciando analise moldura")
    video = OpenVideo(video_path)
    
    success, frame = video.read()
    if not success:
        return
    finishedPerspective = False
    
    while not finishedPerspective:
        finishedPerspective, perspective_frame = fix_perspective(frame)
        time.sleep(0.01)
        if perspective_frame is not 0:
            screen.show_finish_perspective_btn()
    
    video.release()