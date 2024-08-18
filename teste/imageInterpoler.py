from PIL import Image
import cv2
import numpy as np

def open_video(video_path):
    video = cv2.VideoCapture(video_path)
    
    if not video.isOpened():
        print(f"Error opening video_top file {video_path}")
        return False, None
    
    return True, video


def getVideo(input_video_path):
    success, originalVideo = open_video(input_video_path)
    if not success:
        return
    
    success, frame = originalVideo.read()
    
    frames = []
    while True:
        
        success, frame = originalVideo.read()

        if not success:
            break
        
        frames.append(frame)
    
    sequence = np.stack(frames, axis=3)
    result = np.median(sequence, axis=3).astype(np.uint8)

    # Save to disk
    Image.fromarray(result).save('result.png')
    
    
    
getVideo("C:/Projetos/Tcc-comportamento-abelhas/resource/cima/teste02.mp4")