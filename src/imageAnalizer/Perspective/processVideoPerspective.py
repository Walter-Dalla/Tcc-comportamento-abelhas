
import cv2

from src.imageAnalizer.Perspective.perspective import get_perspective_size, perspective
from src.utils.videoUtils import open_video

def process_video(input_video_path, temp_name, frame_points):

    success, originalVideo = open_video(input_video_path)
    if not success:
        return

    tempPath = 'C:/Projetos/Tcc-comportamento-abelhas/temp/'+temp_name+'.mp4'
    
    fps =  int(originalVideo.get(cv2.CAP_PROP_FPS))
    fourcc =  int(cv2.VideoWriter().fourcc(*'mp4v') )
    width, height = get_perspective_size(frame_points)

    output_stream  = cv2.VideoWriter(tempPath, fourcc, fps, (width, height))
    while True:
        success, frame = originalVideo.read()
        if not success:
            break
        
        warppedFrame = perspective(frame, frame_points)
        
        output_stream.write(warppedFrame)
    
    output_stream.release()
    originalVideo.release()
    
    success, video = open_video(tempPath)
    
    return success, video, fps
