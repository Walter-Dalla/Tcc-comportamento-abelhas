import cv2
import json

debug_mode = False

def analyze_frame(video_path):
    # Open the video file
    cap = cv2.VideoCapture(video_path)
    
    # Check if the video was successfully opened
    if not cap.isOpened():
        print(f"Error opening video file {video_path}")
        return

    frame_count = 0
    
    success, frame = cap.read()
    data = []

    while True:
         
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        
        
        if not debug_mode or cv2.waitKey(10) == 27: #esc
            success, frame = cap.read()

            if not success:
                break


            (darkest_pixel_value, maxVal, darkest_pixel_location, maxLoc) = cv2.minMaxLoc(gray_frame)



            data.append({
                'x': darkest_pixel_location[0],
                'y': darkest_pixel_location[1]
            })


            frame_count += 1

        if debug_mode:
            print(f"Darkest pixel value: {darkest_pixel_value} at location {darkest_pixel_location}")

            cv2.circle(gray_frame, darkest_pixel_location, 5, (0, 0, 255), 50)
            cv2.circle(frame, darkest_pixel_location, 5, (0, 0, 255), 1)

            cv2.imshow('Frame', frame)
            cv2.imshow('Gray Scale', gray_frame)

    print(data)
    output_path = "C:/Projetos/Tcc-comportamento-abelhas/output/output_data.json"
    
    with open(output_path, "a") as file:
        json.dump(data, file)
        print("Arquivo salvo")

    cap.release()
    cv2.destroyAllWindows()

