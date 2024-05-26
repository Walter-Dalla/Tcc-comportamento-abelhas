
import cv2

from imageAnalizer.Perspective.perspective import getPerspectiveSize, perspective
from utils.videoUtils import openVideo


def process_video(videoPath):

    success, originalVideo = openVideo(videoPath)
    if not success:
        return

    tempPath = 'C:/Projetos/Tcc-comportamento-abelhas/temp/top.mp4'
    
    fps =  int(originalVideo.get(cv2.CAP_PROP_FPS))
    fourcc =  int(cv2.VideoWriter().fourcc(*'mp4v') )
    width, height = getPerspectiveSize()

    output_stream  = cv2.VideoWriter(tempPath, fourcc, fps, (width, height))
    while True:
        success, frame = originalVideo.read()
        if not success:
            break
        
        warppedFrame = perspective(frame)
        
        output_stream.write(warppedFrame)
    
    output_stream.release()
    originalVideo.release()
    
    return openVideo(tempPath)
