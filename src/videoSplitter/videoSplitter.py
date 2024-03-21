import time
import pafy
import cv2

def getFramesFromVideo(url, imagesFolder, videoName, TIMER):

    # get video from youtube
    video = pafy.new(url)

    while success:

        # save frame as JPEG file
        cv2.imwrite("%s/frame%d.jpg" % (imagesFolder, count), image)
        success, image = vidcap.read()

        time.sleep(int(TIMER))