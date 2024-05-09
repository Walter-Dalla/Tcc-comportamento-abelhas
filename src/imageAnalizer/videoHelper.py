import cv2

def OpenVideo(video_path):
    video = cv2.VideoCapture(video_path)
    
    if not video.isOpened():
        print(f"Error opening video file {video_path}")
        return
    return video