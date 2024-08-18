
import cv2
import numpy as np

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
    
    frames = []
    while True:
        success, frame = originalVideo.read()
        if not success:
            break
        
        warppedFrame = perspective(frame, frame_points)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,3))
        morphology_img = cv2.morphologyEx(warppedFrame, cv2.MORPH_OPEN, kernel,iterations=2)
        
        frames.append(morphology_img)
    
    sequence = np.stack(frames, axis=3)
    backgroundImage = np.median(sequence, axis=3).astype(np.uint8)
    
    for frame in frames:
        warppedFrame = cv2.subtract(frame, backgroundImage)
        
        black_pixels = np.where(
            (warppedFrame[:, :, 0] == 0) & 
            (warppedFrame[:, :, 1] == 0) & 
            (warppedFrame[:, :, 2] == 0)
        )

        # set those pixels to white
        warppedFrame[black_pixels] = [255, 255, 255]
        
        output_stream.write(warppedFrame)
    
    
    
    output_stream.release()
    originalVideo.release()
    
    success, video = open_video(tempPath)
    
    return success, video, fps
