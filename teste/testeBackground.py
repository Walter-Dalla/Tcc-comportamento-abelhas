import cv2 
import numpy as np

bolah = "C:/Projetos/Tcc-comportamento-abelhas/resource/frame-with-incect_circle.avi"
cima = "C:/Projetos/Tcc-comportamento-abelhas/resource/cima/teste01.mp4"
stream = cv2.VideoCapture(cima)



if not stream.isOpened():
    print("No stream :(")
    exit()

num_frames = stream.get(cv2.CAP_PROP_FRAME_COUNT)
frame_ids = np.random.uniform(size=20) * num_frames
frames = []
for fid in frame_ids:
    stream.set(cv2.CAP_PROP_POS_FRAMES, fid)
    ret, frame = stream.read()
    if not ret: # if no frames are returned
        print("SOMETHING WENT WRONG")
        exit()
    frames.append(frame)

# The median frame here is our background
median = np.median(frames, axis=0).astype(np.uint8)
median = cv2.cvtColor(median, cv2.COLOR_BGR2GRAY)

stream.set(cv2.CAP_PROP_POS_FRAMES, 0)
while True:
    ret, frame = stream.read()
    if not ret: # if no frames are returned
        print("No more stream :(")
        break
    
    # take out any pixel that is similar to our median frame
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    dif_frame = cv2.absdiff(median, frame)
    threshold, diff = cv2.threshold(dif_frame, 100, 255,
                    cv2.THRESH_BINARY)
    
    cv2.imshow("Video!", diff)
    cv2.waitKey(20)
    if cv2.waitKey(1) == ord('q'): # press "q" to quit
        break

stream.release()
cv2.destroyAllWindows() #!