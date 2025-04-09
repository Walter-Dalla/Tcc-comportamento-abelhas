from PIL import Image, ImageTk

from src.Modules.ExportModule.videoUtils import open_video

def get_firt_frame(videoPath):
    if(not videoPath):
        return
    
    success, video = open_video(videoPath)
    if(not success):
        return
    
    success, frame = video.read()
    if not success:
        return
    
    
    image = Image.fromarray(frame)
    imageTk = ImageTk.PhotoImage(image)
    
    return imageTk