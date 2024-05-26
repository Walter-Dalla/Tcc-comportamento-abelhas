import cv2

def openVideo(video_path):
    video = cv2.VideoCapture(video_path)
    
    if not video.isOpened():
        print(f"Error opening video_top file {video_path}")
        return False, None
    
    return True, video
